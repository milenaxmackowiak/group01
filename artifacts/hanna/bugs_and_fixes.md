# Bugs and fixes

## Bugs in Tatou

| # | Bug | Found via | Fix | Test | Commit |
|---|---|---|---|---|---|
| 1 | `read_secret` took all text after the tag as the token. Text added after the watermark broke decryption for some secret lengths (base64 `=` padding). An attacker could block attribution by adding text. | `read_secret__mutmut_20` | Read only the first word after the tag (`split()[0]`), in both the text and metadata branch | `test_read_secret_survives_text_after_watermark` (3 secret lengths; `"x" * 40` failed before the fix) | `7c21ebe` |
| 2 | `RMAP_WATERMARK_KEY` fails open: falls back to a default published in our public repo, unlike `SECRET_KEY` | Triaging config mutants in `create_app` | Not fixed. Verified the key is set on the live server. Recommendation: same check as `SECRET_KEY` | – | – |
| 3 | Delete error message reveals the server's absolute storage path | Running the delete test | Not fixed (minor) | – | – |

## Bugs in the test suite

| # | Bug | Fix | Commit |
|---|---|---|---|
| 4 | Delete test passed for the wrong reason: the inserted row was still in an uncommitted transaction, so the server never found the document | Commit before the request; assert on the response so it cannot pass by accident | `7c21ebe` |
| 5 | Two tests opened `test_sample.pdf` with a relative path, which broke under mutmut's sandbox | Moved the file to `test/`, used `Path(__file__).parent` | `dd0b187` |
| 6 | Most tests use a shared `app` built at import, so mutants in `create_app` are never activated | Not fixed. Recommendation: build the app in a pytest fixture via `create_app()` | – |

## New tests

| Test | File | Targets |
|---|---|---|
| `test_rejects_missing_secret_key` | `test/test_api.py` | mutants 5, 7, 10 |
| `test_rejects_default_secret_key` | `test/test_api.py` | default-secret check |
| `test_token_ttl_read_from_env` | `test/test_api.py` | TTL env-var name mutant |
| `test_delete_document_not_escape_storage_root` | `test/test_api.py` | path guard (268/269) |
| `test_read_secret_falls_back_to_metadata` | `test/test_hanna_watermark.py` | mutant 30 |
| `test_read_secret_survives_text_after_watermark` | `test/test_hanna_watermark.py` | bug 1 |
| `test_hanna_round_trip` | `test/test_hanna_watermark.py` | writer + reader together |
| `test_hanna_writes_watermark_to_metadata` | `test/test_hanna_watermark.py` | metadata copy written |
| `test_hanna_wrong_key_rejected` | `test/test_hanna_watermark.py` | wrong key raises `InvalidKeyError` |

All new tests are in commit `7c21ebe`.
