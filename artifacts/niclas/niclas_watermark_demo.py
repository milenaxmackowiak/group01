# Demo of niclas-watermark behaviour, output saved in niclas_watermark_demo_output.txt
# Run from server/:  python ../artifacts/niclas/niclas_watermark_demo.py
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2] / "server"
sys.path.insert(0, str(SERVER / "src"))

import pymupdf
from niclas_watermark import NiclasWatermark, _CATALOG_KEY
from watermarking_method import InvalidKeyError, SecretNotFoundError

wm = NiclasWatermark()
original = (SERVER / "test" / "test_sample.pdf").read_bytes()
KEY = "demo-key"


def page_text(pdf_bytes):
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "".join(page.get_text() for page in doc)


def expect(label, fn, exc):
    try:
        fn()
        print(f"[FAIL] {label}: no exception")
    except exc as e:
        print(f"[OK]   {label}: {type(e).__name__}: {e}")


print("usage:", wm.get_usage())
print("applicable to test_sample.pdf:", wm.is_watermark_applicable(original))

marked = wm.add_watermark(original, secret="recipient-alice", key=KEY)
print(f"\nsize original={len(original)} B, watermarked={len(marked)} B")

payload = wm.read_payload(marked, KEY)
print("decrypted payload:", payload)
print("read_secret:", wm.read_secret(marked, KEY))
import hashlib
print("payload sha256 matches original PDF:", payload["sha256"] == hashlib.sha256(original).hexdigest())

print("\nvisible text unchanged:", page_text(original) == page_text(marked))
with pymupdf.open(stream=marked, filetype="pdf") as doc:
    kind, value = doc.xref_get_key(doc.pdf_catalog(), _CATALOG_KEY)
    print(f"catalog /{_CATALOG_KEY} -> {kind} {value}")
    print("raw stream starts with (Fernet token, not readable):", doc.xref_stream(int(value.split()[0]))[:40])

print("\nerror paths:")
expect("wrong key", lambda: wm.read_secret(marked, "wrong-key"), InvalidKeyError)
expect("unwatermarked PDF", lambda: wm.read_secret(original, KEY), SecretNotFoundError)
expect("empty secret", lambda: wm.add_watermark(original, secret="", key=KEY), ValueError)
expect("empty key", lambda: wm.add_watermark(original, secret="x", key=""), ValueError)

# tamper with the encrypted blob: Fernet's HMAC must reject it
with pymupdf.open(stream=marked, filetype="pdf") as doc:
    xref = int(doc.xref_get_key(doc.pdf_catalog(), _CATALOG_KEY)[1].split()[0])
    blob = bytearray(doc.xref_stream(xref))
    blob[50] ^= 0x01
    doc.update_stream(xref, bytes(blob))
    tampered = doc.write()
expect("tampered blob", lambda: wm.read_secret(tampered, KEY), InvalidKeyError)

# a re-save (e.g. by a PDF tool doing garbage collection) should keep the watermark
with pymupdf.open(stream=marked, filetype="pdf") as doc:
    resaved = doc.write(garbage=4, deflate=True)
print("\nsurvives re-save with garbage=4, deflate:", wm.read_secret(resaved, KEY) == "recipient-alice")
