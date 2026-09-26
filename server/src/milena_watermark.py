import pymupdf
import re
from typing import Final
from cryptography.fernet import Fernet
import hashlib
import base64

from watermarking_method import (
    WatermarkingMethod,
    InvalidKeyError,
    SecretNotFoundError,
    load_pdf_bytes,
)

pattern_td = re.compile(r'(-?\d+\.?\d*)\s+-?\d+\.?\d*\s+Td')


class WatermarkMilena(WatermarkingMethod):
    name: Final[str] = "watermark-milena"

    @staticmethod
    def get_usage() -> str:
        return "Embeds encrypted secret into text line gaps within the PDF content-stream."

    @staticmethod
    def _extract_gaps(split_stream: str):
        gaps = []
        for match in pattern_td.finditer(split_stream):
            gaps.append({
                'start': match.start(1),
                'end': match.end(1),
                'value': float(match.group(1))
            })
        return gaps

    @staticmethod
    def _return_fernet_key(key_str: str) -> bytes:
        digest = hashlib.sha256(key_str.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    @staticmethod
    def _bits_to_bytes(bit_string: str) -> bytes:
        length = (len(bit_string) // 8) * 8
        bit_string = bit_string[:length]
        if not bit_string:
            return b""
        return bytes(int(bit_string[i:i+8], 2) for i in range(0, len(bit_string), 8))

    @staticmethod
    def _bytes_to_bits(data: bytes) -> str:
        return ''.join(f"{byte:08b}" for byte in data)

    @staticmethod
    def _rebuild_line_with_watermark(line: str, gaps: list, bit_stream: str, bit_idx: int) -> tuple[str, int]:
        last_pos = 0
        new_line_text = ""
        num_gaps = len(gaps)

        for i, gap in enumerate(gaps):
            is_data_gap = (i % 2 == 0) and (i >= 2) and (i + 1 < num_gaps)

            if is_data_gap and bit_idx < len(bit_stream):
                left = gaps[i - 1]['value']
                right = gaps[i + 1]['value']
                baseline = (left + right) / 2.0

                current_bit = bit_stream[bit_idx]
                new_val = baseline * 1.02 if current_bit == '1' else baseline * 0.98
                new_val_str = f"{new_val:.6f}"

                new_line_text += line[last_pos:gap['start']] + new_val_str
                last_pos = gap['end']
                bit_idx += 1

        new_line_text += line[last_pos:]
        return new_line_text, bit_idx

    def add_watermark(self, pdf, secret: str, key: str, position: str | None = None) -> bytes:
        if not secret:
            raise ValueError("Secret cannot be empty.")
        if not key:
            raise ValueError("Key cannot be empty.")

        pdf_bytes = load_pdf_bytes(pdf)
        fernet_key = self._return_fernet_key(key)
        f = Fernet(fernet_key)

        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        encrypted_payload = f.encrypt(secret_bytes)

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            page = doc[0]
            stream = page.read_contents().decode("latin-1")

            bit_stream = self._bytes_to_bits(encrypted_payload)
            bit_idx = 0
            modified_stream = ""

            lines = re.split(r'(\d[\d\.\-\s]*Tm)', stream)

            for line in lines:
                if not line.strip():
                    modified_stream += line
                    continue

                gaps = self._extract_gaps(line)
                if len(gaps) < 3:
                    modified_stream += line
                    continue

                new_line, bit_idx = self._rebuild_line_with_watermark(line, gaps, bit_stream, bit_idx)
                modified_stream += new_line

            if bit_idx < len(bit_stream):
                raise ValueError("PDF content stream does not have enough gaps to fit the entire encrypted secret.")

            xref = doc.get_new_xref()
            doc.update_object(xref, "<<>>")
            doc.update_stream(xref, modified_stream.encode("latin-1"))
            page.set_contents(xref)

            return doc.tobytes()
        finally:
            doc.close()

    def read_secret(self, pdf, key: str) -> str:
        if not key:
            raise ValueError("Key cannot be empty.")

        pdf_bytes = load_pdf_bytes(pdf)
        fernet_key = self._return_fernet_key(key)
        f = Fernet(fernet_key)

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            page = doc[0]
            stream = page.read_contents().decode("latin-1")
        finally:
            doc.close()

        lines = re.split(r'(\d[\d\.\-\s]*Tm)', stream)
        extracted_bits = []

        for line in lines:
            if not line.strip():
                continue

            gaps = self._extract_gaps(line)
            num_gaps = len(gaps)

            if num_gaps < 3:
                continue

            for i, gap in enumerate(gaps):
                is_data_gap = (i % 2 == 0) and (i >= 2) and (i + 1 < num_gaps)

                if is_data_gap:
                    left = gaps[i - 1]['value']
                    right = gaps[i + 1]['value']
                    baseline = (left + right) / 2.0

                    if baseline == 0:
                        continue

                    actual_val = gap['value']
                    ratio = actual_val / baseline

                    if abs(ratio - 1.02) < abs(ratio - 0.98):
                        extracted_bits.append("1")
                    else:
                        extracted_bits.append("0")

                    # Attempt Fernet decryption when we have enough bits for a standard token
                    if len(extracted_bits) % 8 == 0 and len(extracted_bits) >= 576:
                        candidate_bytes = self._bits_to_bytes("".join(extracted_bits))
                        try:
                            decrypted_bytes = f.decrypt(candidate_bytes)
                            return decrypted_bytes.decode('utf-8')
                        except Exception:
                            continue

        if not extracted_bits:
            raise SecretNotFoundError("No watermark found in document.")

        raise InvalidKeyError("Failed to decrypt watermark with the provided key or payload was corrupted.")

    def is_watermark_applicable(self, pdf, position: str | None = None) -> bool:
        pdf_bytes = load_pdf_bytes(pdf)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            if doc.page_count == 0:
                return False
            page = doc[0]
            stream = page.read_contents().decode("latin-1")
            lines = re.split(r'(\d[\d\.\-\s]*Tm)', stream)
            for line in lines:
                if not line.strip():
                    continue
                gaps = self._extract_gaps(line)
                if len(gaps) >= 3:
                    return True
            return False
        finally:
            doc.close()
