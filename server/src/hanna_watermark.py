#hanna_watermark.py
#Encrypts the secret and embeds it as invisible text on the PDF's first page using PyMuPDF.

from typing import Final
import pymupdf  # PyMuPDF, python library for manipulation of pdf
from cryptography.fernet import Fernet
import base64
import hashlib

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingMethod,
    load_pdf_bytes,
)

_WATER_MARKER_TAG: Final[str] = "WATERMARKSTART"  #constant so that read_secret() can find Watermark


class HannaWatermark(WatermarkingMethod):
    name: Final[str] = "hanna-watermark"

    @staticmethod
    def get_usage() -> str:
        return "Embeds encrypted secret as invisible text in PDF."

    #Return right byte format for fernet
    def _return_fernet_key(self, key: str) -> bytes:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def add_watermark(self, pdf, secret: str, key: str, position: str | None = None) -> bytes:
        if not secret:
            raise ValueError("Secret must not be empty")
        if not key:
            raise ValueError("Key must not be empty")
        
        #Call helper method to change key to fernet key format
        fernet_key = self._return_fernet_key(key)
        #create fernet object
        fernet = Fernet(fernet_key)
        #changes secret to bytes and encrypts them
        enc_secret = fernet.encrypt(secret.encode("utf-8"))
        #get the pdf bytes
        pdf_bytes = load_pdf_bytes(pdf)
        #open pdf with PyMuPDF so that I can edit pdf
        pdf_document = pymupdf.open(stream = pdf_bytes, filetype = "pdf")
        
        if pdf_document.page_count== 0:
            pdf_document.close()
            raise ValueError("Document does not have pages")
        
        #get the first page
        page_one=pdf_document[0]
        #get the constant and the secret and add together as a string
        watermark_text = _WATER_MARKER_TAG + enc_secret.decode("utf-8")
        #insert text
        page_one.insert_text((10,10),watermark_text, fontsize=1, render_mode=3,)
        #write it to document and close it and return it
        result=pdf_document.write()
        pdf_document.close()
        return result       
           

    def read_secret(self, pdf, key: str) -> str:
        if not key:
            raise ValueError("Key must not be empty")
        #get pdf bytes and open with pymupdf
        pdf_bytes = load_pdf_bytes(pdf)
        pdf_document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        #get the first page
        page_one = pdf_document[0]
        page_text = page_one.get_text()
        
        #find where watermark starts
        wm_index = page_text.find(_WATER_MARKER_TAG)
        if wm_index==-1:
            raise ValueError("Watermark not found")
        #remove the tag and just return the secret
        wm_start= wm_index+len(_WATER_MARKER_TAG)
        encrypted_part = page_text[wm_start:].strip()
        
        #Call helper method to change key to fernet key format
        fernet_key = self._return_fernet_key(key)
        #create fernet object
        fernet = Fernet(fernet_key)
        
        #decrypt into original secret
        try:
            decrypt_bytes = fernet.decrypt(encrypted_part.encode("utf-8"))
        except Exception as exc:
            raise InvalidKeyError("Given key failed to decrypt the watermark") from exc
        
        pdf_document.close()
        return decrypt_bytes.decode("utf-8")
        
        

    def is_watermark_applicable(self, pdf, position: str | None = None) -> bool:
        pdf_bytes = load_pdf_bytes(pdf)
        pdf_document = pymupdf.open(stream= pdf_bytes, filetype="pdf")
        has_pages = pdf_document.page_count > 0
        pdf_document.close()
        return has_pages
    
    
    
    