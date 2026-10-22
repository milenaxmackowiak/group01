# Niclas: fuzzing, regression tests and watermark

All runs below are local (`venv`, Python 3.14), no MySQL running (`DB_USER` unset), so valid sign-ups return 503 instead of 201/409.
"Before" runs use the **current** test files against **old** server code checked out from git, to show the tests catch the original bugs.

## Bugs in Tatou found by fuzzing `/api/create-user`

| # | Bug | Found via (minimal example from Hypothesis) | Fix | Commit |
|---|---|---|---|---|
| 1 | Non-string `email`/`login`/`password` crashed on `.strip()` → 500 | `test_non_string_email_rejected`, `email=1` → `AttributeError: 'int' object has no attribute 'strip'` | Reject non-strings with 400 | `f27787a` |
| 2 | No email validation: any string reached the database | `test_email_without_at_rejected`, `email='0'` → 503 (got to the DB) | Regex `[^@\s]+@[^@\s]+\.[^@\s]+` and max length 254 → 400 | `f27787a` |
| 3 | A JSON body that is not an object (`true`, `[1,2]`, `123`, `"str"`) crashed on `payload.get` → 500 | `test_non_object_body_rejected`, `body=True` → 500 | `if not isinstance(payload, dict)` → 400 | `f27787a` |
| 4 | No request size limit | Review while fixing the above | `MAX_CONTENT_LENGTH` 20 MB + JSON 413 handler | `f27787a` |

Results: `fuzz_create_user_email_before_fix.txt` (3 failed) → `fuzz_create_user_email_after_fix.txt` (3 passed), and
`create_user_email_regression_before_fix.txt` (16 failed / 16 passed) → `create_user_email_regression_after_fix.txt` (32 passed).
`fuzz_valid_email_after_fix.txt`: 300 Hypothesis-generated valid emails all pass the new validation (1 passed, 19 min 56 s without a DB). Not run before the fix, since the old code accepted any string.

Also changed in `f27787a`: the versions listing query now filters on `d.ownerid = :uid` (user id) instead of joining on `login`.

## Security regression tests (`test_security_regressions.py`, commit `f7514d9`)

The two vulnerabilities used to steal our flag were fixed (`b8047f5`, `661736d`) without tests. These tests make sure they stay fixed.

| Test | Guards against | Before fix (`b8047f5^`) | HEAD |
|---|---|---|---|
| `test_bash_bridge_never_spawns_a_process` | `bash-bridge-eof` running a shell | FAILED: spawned `cat ... && printf "harmless"` | PASSED |
| `test_bash_bridge_secret_with_shell_metacharacters_is_inert` | Command injection through the secret | FAILED: secret `"; touch .../pwned #` came back as `''` | PASSED |
| `test_load_plugin_endpoint_stays_removed` | Pickle RCE endpoint coming back | FAILED: `/api/load-plugin` registered | PASSED |

Files: `security_regressions_before_fix.txt`, `security_regressions_after.txt`.

Related hardening after the flag 2 incident (`dbdde34`): DB on an internal-only Docker network, phpMyAdmin bound to `127.0.0.1`, flag no longer echoed in `entrypoint.sh`, leftover `pickle`/`dill` import removed.

## niclas-watermark (`src/niclas_watermark.py`, commit `c88fc58`)

Fernet-encrypted JSON `{id, sha256 of original PDF, ts}` in a stream object referenced from the catalog key `/NWatermark`: never drawn, but survives garbage collection.

| Check | Result | File |
|---|---|---|
| Shared method tests (applicable, add, round trip) | 3 passed | `niclas_watermark_tests.txt` |
| Visible text unchanged, payload sha256 matches original | yes | `niclas_watermark_demo_output.txt` |
| Wrong key / tampered blob | `InvalidKeyError` (Fernet HMAC) | same |
| Unwatermarked PDF | `SecretNotFoundError` | same |
| Re-save with `garbage=4, deflate` | watermark survives | same |
| Line coverage (from `common/coverage_report.txt`) | 83%, missing lines are the error paths, which the demo exercises | – |

Design choices from the exploration scripts (`niclas_watermark_exploration.txt`):
- `xref_get_key` on a missing key returns `('null', 'null')` and does not raise, so the reader checks `kind != "xref"`.
- Fernet's `InvalidToken` has an empty message, so it is wrapped in `InvalidKeyError` with a readable message.

Limitation: a wrong key and a tampered blob give the same error (Fernet cannot tell them apart). Removing `/NWatermark` from the catalog removes the watermark.

## Bugs in the test setup

| # | Bug | Fix |
|---|---|---|
| 5 | Without a DB, every valid sign-up waited for the MySQL connection and the fuzz run took ~20 min before failing with 500 | Accept 503 when `DB_USER` is unset (`OK_CODES`), still proves validation passed |
| 6 | Fixed regression emails give 409 on the second run against a real DB | Unique login per run, plus a second test with unique emails that must give 201 |
| 7 | `json=None` in the test client sends no body, not a JSON `null` | Separate `test_null_body_rejected` sending `data="null"` |

## Other

- CI workflow `.github/workflows/test.yml` (`1459873`): runs the pytest suite on every push and PR.
