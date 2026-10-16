# Interesting mutants

| Mutant | Change | Why it survived | Type | Action |
|---|---|---|---|---|
| `read_secret__mutmut_30` | `metadata.get("keywords")` → `metadata.get(None)` | No test used the metadata fallback | Weak test | Added `test_read_secret_falls_back_to_metadata` |
| `read_secret__mutmut_20` | `find` → `rfind` (watermark tag) | No test had text after the watermark | Real bug | Fixed token extraction (`split()[0]`), added `test_read_secret_survives_text_after_watermark` |
| `read_secret__mutmut_10` | `filetype="pdf"` → `filetype=None` | PyMuPDF detects the type from the content | Equivalent | None needed |
| `read_secret__mutmut_2`, `_45`, `_60` | Error message text changed | Tests check the exception type, not the wording | Not targeted | None (deliberate) |
| `create_app__mutmut_10` (also 5, 7) | `os.environ.get("SECRET_KEY", "")` → `("SECRET_KEY", "XXXX")` | Every test set `SECRET_KEY`, so the default was never used | Weak test (security) | Added `test_rejects_missing_secret_key` and `test_rejects_default_secret_key`; 5 and 10 killed in re-run |
| `create_app` TTL mutant | `os.environ.get("TOKEN_TTL_SECONDS")` → `("token_ttl_seconds")` | No test checked that the setting is read | Weak test | Added `test_token_ttl_read_from_env`; verified by hand |
| `create_app__mutmut_258` | `if not fp.is_absolute()` → `if fp.is_absolute()` | `Path("/storage") / "/tmp/x"` gives `/tmp/x`, so no difference for absolute paths | Equivalent | None needed |
| `create_app__mutmut_268`, `_269` | `if not fp.is_relative_to(storage_root)` → `if fp.is_relative_to(...)` / `(None)` | Test uses the shared `app` built at import, so the mutant is never active | Unreachable by mutmut | Added `test_delete_document_not_escape_storage_root`; recommend app fixture |
| `_sha256_file` sentinel | `iter(..., b"")` → `iter(..., None)` | Should loop forever, but no timeout: the mutated code never ran | Anomaly (shared `app`) | Explained by main finding |
