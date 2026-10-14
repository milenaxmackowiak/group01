import pymupdf
from pathlib import Path

HERE = Path(__file__).resolve().parent
pdf_path = HERE / "Group_1.pdf"

doc = pymupdf.open(str(pdf_path))

try:
    kind, value = doc.xref_get_key(doc.pdf_catalog(), "NWatermark")
    print("No exception raised.")
    print("kind =", kind)
    print("value =", value)
except Exception as e:
    print("Exception raised instead:", type(e).__name__, ":", e)

doc.close()