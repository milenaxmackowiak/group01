# Tests for HannaWatermark, written during my mutation testing (Hannas specialization)
# Each test targets a gap revealed by surviving mutmut mutants in hanna_watermark.py
import pytest
import pymupdf
from cryptography.fernet import Fernet
from hanna_watermark import HannaWatermark, _WATER_MARKER_TAG
from watermarking_method import InvalidKeyError

#Helper! returns an empty pdf
def _blank_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()

#The watermark must still be readable when the text copy has been stripped
#Kills mutant "read_secret__mutmut_30", which disabled the metadata lookup
def test_read_secret_falls_back_to_metadata():
    method = HannaWatermark()
    key = "testkey"
    secret = "secret-only-meta"

    # build a PDF where the watermark exists ONLY in metadata (text watermark "stripped")
    token = Fernet(method._return_fernet_key(key)).encrypt(secret.encode()).decode()
    doc = pymupdf.open()
    doc.new_page()
    doc.set_metadata({"keywords": _WATER_MARKER_TAG + token})
    pdf_bytes = doc.tobytes()

    assert method.read_secret(pdf_bytes, key) == secret

#Text added after the watermark must not break reading it.
#test for a real bug found via mutant "read_secret__mutmut_20". Read my specilization report for explanation.
@pytest.mark.parametrize("secret", ["group-01", "x" * 20, "x" * 40])
def test_read_secret_survives_text_after_watermark(secret):
    method = HannaWatermark()
    key="testkey"
    token= Fernet(method._return_fernet_key(key)).encrypt(secret.encode()).decode()
    print("Token ends with:", token[-3:])

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((20, 50), _WATER_MARKER_TAG + token, fontsize=4)
    # Simulate attacker adding text after the watermark
    page.insert_text((20, 100), "Attacked.", fontsize=10)
    pdf_bytes = doc.tobytes()

    assert method.read_secret(pdf_bytes, key) == secret

#A secret written by add_watermark can be read back by read_secret
def test_hanna_round_trip():
    method = HannaWatermark()
    watermarked = method.add_watermark(_blank_pdf(), secret="group-01", key="testkey")
    assert method.read_secret(watermarked, "testkey") == "group-01"

#add_watermark must write the backup copy into the metadata
def test_hanna_writes_watermark_to_metadata():
    method = HannaWatermark()
    watermarked = method.add_watermark(_blank_pdf(), secret="group-01", key="testkey")
    doc = pymupdf.open(stream=watermarked, filetype="pdf")
    assert doc.metadata["keywords"].startswith(_WATER_MARKER_TAG)

#Reading with the wrong key must fail with InvalidKeyError
def test_hanna_wrong_key_rejected():
    method = HannaWatermark()
    watermarked = method.add_watermark(_blank_pdf(), secret="group-01", key="testkey")
    with pytest.raises(InvalidKeyError):
        method.read_secret(watermarked, "wrongkey")
