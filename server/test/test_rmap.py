import pytest
from pathlib import Path
from server import app
from rmap import RMAPClient

test_directory = Path(__file__).parent


def test_rmap_handshake_returns_link():
    client = app.test_client()
    rmap_client = RMAPClient(
        identity="rmaptestclient",
        client_private_key_path=test_directory.parent / "rmaptestclient_priv.asc",
        server_public_key_path=test_directory.parent / "server_pub.asc",
    )

    msg1 = rmap_client.build_msg1()
    resp1 = client.post("/api/rmap-initiate", json=msg1)
    assert resp1.status_code == 200

    rmap_client.process_resp1(resp1.get_json())
    msg2 = rmap_client.build_msg2()

    resp2 = client.post("/api/rmap-get-link", json=msg2)
    assert resp2.status_code == 200

    link = rmap_client.process_resp2(resp2.get_json())
    assert link
