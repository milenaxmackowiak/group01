from typing import Final
import base64
import hashlib
import json
import time

import pymupdf  # PyMuPDF, python library for manipulation of pdf
from cryptography.fernet import Fernet, InvalidToken

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingError,
    WatermarkingMethod,
    load_pdf_bytes,
)

_CATALOG_KEY: Final[str] = "NWatermark"  #custom key in the catalog that points to object


class NiclasWatermark(WatermarkingMethod):
    name: Final[str] = "niclas-watermark"

    @staticmethod
    def get_usage() -> str:
        return ("Stores a Fernet-encrypted blob (identity, SHA-256 of the original PDF, "
                "timestamp) in a non-rendered PDF object. Position is ignored.")

    #Return right byte format for fernet
    def _return_fernet_key(self, key: str) -> bytes:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def add_watermark(self, pdf, secret: str, key: str, position: str | None = None) -> bytes:
        if not secret:
            raise ValueError("Secret must not be empty")
        if not key:
            raise ValueError("Key must not be empty")

        pdf_bytes = load_pdf_bytes(pdf)

        #payload: who it was issued to, which document it was made from, and when
        payload = {
            "id": secret,
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "ts": int(time.time()),
        }
        fernet = Fernet(self._return_fernet_key(key))
        blob = fernet.encrypt(json.dumps(payload).encode("utf-8"))

        pdf_document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            #create a new stream object holding the blob
            xref = pdf_document.get_new_xref()
            pdf_document.update_object(xref, "<<>>")
            pdf_document.update_stream(xref, blob)
            #reference it from the catalog so it survives garbage collection but is never drawn
            pdf_document.xref_set_key(pdf_document.pdf_catalog(), _CATALOG_KEY, f"{xref} 0 R")
            return pdf_document.write()
        finally:
            pdf_document.close()

    #Return the full decrypted payload (id, sha256, ts)
    def read_payload(self, pdf, key: str) -> dict:
        if not key:
            raise ValueError("Key must not be empty")

        pdf_document = pymupdf.open(stream=load_pdf_bytes(pdf), filetype="pdf")
        try:
            kind, value = pdf_document.xref_get_key(pdf_document.pdf_catalog(), _CATALOG_KEY)
            if kind != "xref":
                raise SecretNotFoundError("Watermark not found")
            blob = pdf_document.xref_stream(int(value.split()[0]))
        finally:
            pdf_document.close()

        if not blob:
            raise SecretNotFoundError("Watermark object is empty")

        fernet = Fernet(self._return_fernet_key(key))
        try:
            decrypted = fernet.decrypt(blob)
        except InvalidToken as exc:
            raise InvalidKeyError("Given key failed to decrypt the watermark") from exc

        #authenticated, but still check the shape so callers only ever see WatermarkingError types
        try:
            payload = json.loads(decrypted)
        except ValueError as exc:  #JSONDecodeError and UnicodeDecodeError are both ValueErrors
            raise WatermarkingError("Watermark payload is not valid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise WatermarkingError("Watermark payload is malformed")
        return payload

    def read_secret(self, pdf, key: str) -> str:
        return self.read_payload(pdf, key)["id"]

    def is_watermark_applicable(self, pdf, position: str | None = None) -> bool:
        pdf_document = pymupdf.open(stream=load_pdf_bytes(pdf), filetype="pdf")
        has_pages = pdf_document.page_count > 0
        pdf_document.close()
        return has_pages
