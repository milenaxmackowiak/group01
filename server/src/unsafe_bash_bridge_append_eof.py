"""unsafe_bash_bridge_append_eof.py

Toy watermarking method that appends an authenticated payload *after* the
PDF's final EOF marker but by calling a bash command. Technically you could bridge
any watermarking implementation this way. Don't, unless you know how to sanitize user inputs.

"""
from __future__ import annotations

from typing import Final
import subprocess

from watermarking_method import (
    InvalidKeyError,
    SecretNotFoundError,
    WatermarkingError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class UnsafeBashBridgeAppendEOF(WatermarkingMethod):
    """Toy method that appends a watermark record after the PDF EOF.

    """

    name: Final[str] = "bash-bridge-eof"

    # ---------------------
    # Public API overrides
    # ---------------------
    
    @staticmethod
    def get_usage() -> str:
        return "Toy method that appends a watermark record after the PDF EOF. Position and key are ignored."

    def add_watermark(
        self,
        pdf,
        secret: str,
        key: str,
        position: str | None = None,
    ) -> bytes:
        """Return a new PDF with a watermark record appended.

        The ``position`` and ``key`` parameters are accepted for API compatibility but
        ignored by this method.
        """ 
	#Hanna: I changed these three rows below
        data = load_pdf_bytes(pdf)
        super_secret = secret.encode("utf-8")
        return data + super_secret
        
    def is_watermark_applicable(
        self,
        pdf: PdfSource,
        position: str | None = None,
    ) -> bool:
        return True
    

    def read_secret(self, pdf, key: str) -> str:
        """Extract the secret if present.
           Prints whatever there is after %EOF
        """
        #Hanna: Changed this as well, the old code is commented out.
        data = load_pdf_bytes(pdf)
        index = data.rfind(b"%%EOF")
        if index == -1:
            return ""
        after_eof = data[index + len(b"%%EOF"):]
        return after_eof.decode("utf-8", errors="replace").strip()
    
        #cmd = "sed -n '1,/^\(%%EOF\|.*%%EOF\)$/!p' " + str(pdf.resolve())
         
        #res = subprocess.run(cmd, shell=True, check=True, encoding="utf-8", capture_output=True)
       

        #return res.stdout



__all__ = ["UnsafeBashBridgeAppendEOF"]

