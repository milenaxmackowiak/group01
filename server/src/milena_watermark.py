import base64
import hashlib
import re
from typing import Final

import pymupdf
from cryptography.fernet import Fernet, InvalidToken

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingMethod,
    load_pdf_bytes,
)

_XMP_TAG_OPEN: Final[str] = "<tatou:watermark>"
_XMP_TAG_CLOSE: Final[str] = "</tatou:watermark>"


class WatermarkMilena(WatermarkingMethod):
    name: Final[str] = "watermark-milena"

    @staticmethod
    def get_usage() -> str:
        return "Embeds an encrypted secret inside the document's XMP XML metadata package."

    @staticmethod
    def _return_fernet_key(key: str) -> bytes:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def add_watermark(self, pdf, secret: str, key: str, position: str | None = None) -> bytes:
        if not secret:
            raise ValueError("Secret must not be empty")
        if not key:
            raise ValueError("Key must not be empty")

        pdf_bytes = load_pdf_bytes(pdf)
        fernet = Fernet(self._return_fernet_key(key))
        token = fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            if doc.page_count == 0:
                raise ValueError("PDF has no pages")

            # Retrieve existing XMP XML or create a minimal envelope if none exists
            current_xmp = doc.get_xml_metadata() or "<x:xmpmeta></x:xmpmeta>"

            # Remove previous tag if re-watermarking
            current_xmp = re.sub(
                rf"{re.escape(_XMP_TAG_OPEN)}.*?{re.escape(_XMP_TAG_CLOSE)}",
                "",
                current_xmp,
                flags=re.DOTALL,
            )

            # Insert tag with encrypted payload
            custom_block = f"{_XMP_TAG_OPEN}{token}{_XMP_TAG_CLOSE}"
            if "</x:xmpmeta>" in current_xmp:
                new_xmp = current_xmp.replace("</x:xmpmeta>", f"{custom_block}</x:xmpmeta>")
            else:
                new_xmp = f"{current_xmp}\n{custom_block}"

            doc.set_xml_metadata(new_xmp)
            return doc.tobytes()
        finally:
            doc.close()

    def read_secret(self, pdf, key: str) -> str:
        if not key:
            raise ValueError("Key must not be empty")

        pdf_bytes = load_pdf_bytes(pdf)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            xmp = doc.get_xml_metadata() or ""
        finally:
            doc.close()

        start_idx = xmp.find(_XMP_TAG_OPEN)
        end_idx = xmp.find(_XMP_TAG_CLOSE)

        if start_idx == -1 or end_idx == -1:
            raise SecretNotFoundError("Watermark tag not found in document XMP metadata")

        token = xmp[start_idx + len(_XMP_TAG_OPEN):end_idx].strip()
        if not token:
            raise SecretNotFoundError("Watermark tag found but payload is empty")

        fernet = Fernet(self._return_fernet_key(key))
        try:
            decrypted = fernet.decrypt(token.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken as exc:
            raise InvalidKeyError("Invalid key for decrypting watermark") from exc

    def is_watermark_applicable(self, pdf, position: str | None = None) -> bool:
        pdf_bytes = load_pdf_bytes(pdf)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        valid = doc.page_count > 0
        doc.close()
        return valid
