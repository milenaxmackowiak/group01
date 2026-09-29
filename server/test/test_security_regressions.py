# Regression tests for the two vulnerabilities that were exploited to steal our flag.
# Neither fix was committed with a test here are test these make sure they still work.
from __future__ import annotations
 
import os
import subprocess
from pathlib import Path
 
import pytest
 
from unsafe_bash_bridge_append_eof import UnsafeBashBridgeAppendEOF
 
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
 
 
@pytest.fixture()
def pdf_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    p.write_bytes(PDF_BYTES)
    return p
 
 
def _injection_secrets(marker: Path) -> list[str]:
    """Secrets that would create `marker` if they ever reached a shell."""
    return [
        f"'; touch {marker} #",
        f"\"; touch {marker} #",
        f"$(touch {marker})",
        f"`touch {marker}`",
        f"x && touch {marker}",
        f"x | touch {marker}",
    ]
 
 
# command injection
def test_bash_bridge_never_spawns_a_process(pdf_path, monkeypatch):
    """add_watermark and read_secret must not call a shell or subprocess at all."""
 
    def boom(*args, **kwargs):
        raise AssertionError(f"bash-bridge-eof spawned a process: {args!r}")
 
    monkeypatch.setattr(subprocess, "Popen", boom)  # subprocess.run/call/check_* all use Popen
    monkeypatch.setattr(os, "system", boom)
    monkeypatch.setattr(os, "popen", boom)
 
    wm = UnsafeBashBridgeAppendEOF()
    out = wm.add_watermark(pdf_path, secret="harmless", key="k")
    marked = pdf_path.with_name("marked.pdf")
    marked.write_bytes(out)
    wm.read_secret(marked, key="k")
 
 
def test_bash_bridge_secret_with_shell_metacharacters_is_inert(pdf_path, tmp_path):
    """Shell payloads in the secret are stored and read back as plain text, never executed."""
    marker = tmp_path / "pwned"
    wm = UnsafeBashBridgeAppendEOF()
 
    for secret in _injection_secrets(marker):
        out = wm.add_watermark(pdf_path, secret=secret, key="k")
        marked = tmp_path / "marked.pdf"
        marked.write_bytes(out)
 
        assert wm.read_secret(marked, key="k") == secret, f"secret altered: {secret!r}"
        assert not marker.exists(), f"command executed via secret: {secret!r}"
 
 
# pickle endpoint
def test_load_plugin_endpoint_stays_removed():
    """The endpoint that unpickled uploaded files (RCE) must not come back"""
    from server import app

    plugin_routes = [r.rule for r in app.url_map.iter_rules() if "plugin" in r.rule]
    assert not plugin_routes, f"plugin-loading route is registered again: {plugin_routes}"
 
