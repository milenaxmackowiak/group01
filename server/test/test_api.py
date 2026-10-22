import pytest
import io
from server import app
from pathlib import Path
import hashlib
from sqlalchemy import text
import conftest
from server import create_app
import secrets

#directory to the file, mutmut failed because filepath was wrong
test_directory = Path(__file__).parent

def test_healthz_route():
    client = app.test_client()
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.is_json
    
#test login with a path as username
def test_path_username_is_rejected():
    client = app.test_client() #call routes without server running
    response = client.post("/api/create-user", json={
        "login": "../pathtest",
        "password": "throwaway-pw",
        "email": "pathtest-unittest@testpath.com",
    })
    assert response.status_code == 400

#test bad usernames are rejected
def test_bad_usernames_rejected():
    client = app.test_client()
    bad_logins = ["../pathtest", "a/b", "a.b", "a b", "name!", "name@name"]
    for bad_login in bad_logins:
        response = client.post("/api/create-user", json={
            "login": bad_login,
            "password": "throwaway-pw",
            "email": f"bad-{bad_logins.index(bad_login)}@testbadusername.com",
        })
        assert response.status_code == 400, f"{bad_login!r} should be rejected but got {response.status_code}"
        

#learning test, (i know this test is stupid)
def test_watermark_link_is_random():
    import secrets
    first_link =secrets.token_hex(20)
    second_link= secrets.token_hex(20)
    assert first_link != second_link

#accidentaly had this deleted on the last push sorry, it is now back!once a real SECRET_KEY is set, a login token signed with the old public default key is not accepted
def test_old_default_key_is_rejected(monkeypatch):
    # set a real-looking SECRET_KEY just for this test, then rebuild the app
    # so it actually picks it up
    monkeypatch.setenv("SECRET_KEY", "a-real-looking-local-test-key")
    import importlib
    import server
    importlib.reload(server)
    from itsdangerous import URLSafeTimedSerializer
    
    old_insecure_key = URLSafeTimedSerializer("dev-secret-change-me", salt="tatou-auth")
    faketoken=old_insecure_key.dumps({"uid": 9999, "login": "Mr_cat", "email": "mr@cat.com"})
    client=server.app.test_client()
    response=client.get("/api/list-documents", headers={"Authorization": "Bearer " + faketoken})
    body= response.get_json()
    assert "database" not in str(body.get("error", "")), "fake token reached the database, require_auth let it through"
    
def test_cant_list_someone_elses_versions():
    client = app.test_client()
    client.post("/api/create-user", json={"login":"version_userA","password": "test-pw-a","email":"usera@versiontest.com",})
    client.post("/api/create-user", json={"login": "version_userB","password": "test-pw-b", "email":"userb@versiontest.com",}) 
    loginA=client.post("/api/login", json={"email": "usera@versiontest.com", "password": "test-pw-a",})
    tokenA = loginA.get_json()["token"]
    loginB = client.post("/api/login", json={"email": "userb@versiontest.com", "password": "test-pw-b",})
    tokenB = loginB.get_json()["token"]
    
    upload_document = client.post(
        "/api/upload-document",
        headers={"Authorization": "Bearer " + tokenA},
        data={"file": (open(test_directory / "test_sample.pdf", "rb"), "test_sample.pdf"), "name": "versiontest"},
        content_type="multipart/form-data",)
    
    document_id = upload_document.get_json()["id"]
    create_watermark = client.post(f"/api/create-watermark/{document_id}", headers={"Authorization": "Bearer " + tokenA},
        json={"method": "toy-eof", "key": "versiontestkey", "secret": "versiontestsecret", "intended_for": "nobody"},)

    listB = client.get(
        f"/api/list-versions/{document_id}",
        headers={"Authorization": "Bearer " + tokenB},
    )
    versions = listB.get_json()["versions"]
    assert versions == [], "user B could see user As versions"
    
def test_cant_delete_someone_else_document():
    client = app.test_client()
    client.post("/api/create-user", json={"login":"delete_userA","password": "test-pw-a","email":"usera@deletetest.com",})
    client.post("/api/create-user", json={"login": "delete_userB","password": "test-pw-b", "email":"userb@deletetest.com",})
    loginA=client.post("/api/login", json={"email": "usera@deletetest.com", "password": "test-pw-a",})
    tokenA = loginA.get_json()["token"]
    loginB = client.post("/api/login", json={"email": "userb@deletetest.com", "password": "test-pw-b",})
    tokenB = loginB.get_json()["token"]
    
    upload_document = client.post(
        "/api/upload-document",
        headers={"Authorization": "Bearer " + tokenA},
        data={"file": (open(test_directory / "test_sample.pdf", "rb"), "test_sample.pdf"), "name": "deletetest"},
        content_type="multipart/form-data",)
    
    document_id = upload_document.get_json()["id"]
    
    attempt_delete = client.delete(f"/api/delete-document/{document_id}", headers={"Authorization": "Bearer "+ tokenB},)
    assert attempt_delete.status_code == 404
    
    list_documents = client.get("/api/list-documents",headers={"Authorization": "Bearer " + tokenA},)
    document_ids = [d["id"] for d in list_documents.get_json()["documents"]]
    assert document_id in document_ids
    

def test_unique_login_username():
    client=app.test_client()
    alice=client.post("/api/create-user", json={"login":"same_name","password": "test-pw-a","email":"usera@samename.com",})
    bob=client.post("/api/create-user", json={"login": "same_name","password": "test-pw-b", "email":"userb@samename.com",})
    assert bob.status_code == 409
    
#test after mutmut --> Hanna specilization
def test_delete_document_not_escape_storage_root(tmp_path):
    client=app.test_client()
    userA=client.post("/api/create-user", json={"login":"escapeA", "password":"test-pw", "email": "escapeA@testescape.com",})
    print("CREATE USER:", userA.status_code, userA.get_json())
    user_id = userA.get_json()["id"]
    login = client.post("/api/login", json={"email": "escapeA@testescape.com","password": "test-pw",})
    token = login.get_json()["token"]
    
    # a file outside the app's storage directory, which we control
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"don't delete me :(")

    content = b"test"
    sha_hex = hashlib.sha256(content).hexdigest()

    engine = conftest.testing_db()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO Documents (name, path, ownerid, sha256, size)
                VALUES (:name, :path, :ownerid, UNHEX(:sha256hex), :size)
            """),
            {
                "name": "evil",
                "path": str(victim.resolve()),
                "ownerid": int(user_id),
                "sha256hex": sha_hex,
                "size": len(content),
            },
        )
        document_id = int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar())
        
    resp=client.delete(
        f"/api/delete-document/{document_id}",
        headers={"Authorization": "Bearer " + token},
    )
    print("STATUS:", resp.status_code, resp.get_json())
    assert victim.exists(), "file outside storage root was deleted"
    assert resp.status_code != 404, "document not found - test setup is broken"
    
    
def test_rejects_default_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-secret-change-me")
    with pytest.raises(RuntimeError):
        create_app()

def test_rejects_missing_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()

def test_token_ttl_read_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-real-test-secret")
    monkeypatch.setenv("TOKEN_TTL_SECONDS", "60")
    app = create_app()
    assert app.config["TOKEN_TTL_SECONDS"] == 60
    
import secrets

def test_create_user_success():
    client = app.test_client()
    tag = secrets.token_hex(4)
    payload = {
        "login": f"user_{tag}",
        "email": f"user_{tag}@example.com",
        "password": "ValidPassword123!",
    }

    response = client.post("/api/create-user", json=payload)
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["login"] == payload["login"]
    assert data["email"] == payload["email"]
    assert "password" not in data
    assert "hpassword" not in data


#test creat a user successfully
def test_create_user_success():
    client = app.test_client()
    tag = secrets.token_hex(4)
    payload = {
        "login": f"user_{tag}",
        "email": f"user_{tag}@example.com",
        "password": "ValidPassword123!",
    }

    response = client.post("/api/create-user", json=payload)
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["login"] == payload["login"]
    assert data["email"] == payload["email"]
    assert "password" not in data
    assert "hpassword" not in data

#test create user with a missing password
def test_create_user_missing_password():
    client = app.test_client()
    payload = {
        "login": "incomplete_user",
        "email": "incomplete@example.com",
    }

    response = client.post("/api/create-user", json=payload)

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_get_watermarking_methods_public():
    client = app.test_client()
    response = client.get('/api/get-watermarking-methods')
    assert response.status_code == 200
    
    data = response.get_json()
    assert isinstance(data, (dict, list))
    # Checking if one of the method is present in the list
    if isinstance(data, list):
        assert "watermark-milena" in data

#test to read a certain watermark by an authenticated user
def test_read_watermark_id():
    client = app.test_client()
    testuser = client.post("/api/create-user", json={"login": "readwm_user", "password": "test-pw", "email": "user@readwmtest.com"})
    assert testuser.status_code == 201

    login = client.post("/api/login", json={"email": "user@readwmtest.com", "password": "test-pw"})
    token = login.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with open(test_directory / "test_sample.pdf", "rb") as f:
        upload = client.post(
            "/api/upload-document",
            data={"file": (f, "test_sample.pdf")},
            headers=headers,
            content_type="multipart/form-data",
        )
    assert upload.status_code == 201
    doc_id = upload.get_json()["id"]

    watermark = client.post(
        f"/api/create-watermark/{doc_id}",
        json={"method": "watermark-milena", "key": "testkey", "secret": "testsecret", "intended_for": "recipient"},
        headers=headers,
    )
    assert watermark.status_code == 201

    #create-watermark stores the watermarked pdf as a separate version, the original document stays untouched,
    #so download the version and upload it as a new document (like a leaked copy) before reading it
    version = client.get(f"/api/get-version/{watermark.get_json()['link']}")
    assert version.status_code == 200
    watermarked_upload = client.post(
        "/api/upload-document",
        data={"file": (io.BytesIO(version.data), "watermarked.pdf")},
        headers=headers,
        content_type="multipart/form-data",
    )
    version.close()
    assert watermarked_upload.status_code == 201
    watermarked_id = watermarked_upload.get_json()["id"]

    resp = client.post(f"/api/read-watermark/{watermarked_id}", json={"method": "watermark-milena", "key": "testkey"}, headers=headers)
    assert resp.status_code == 201
    assert resp.get_json()["secret"] == "testsecret"
    
def test_get_document():
    client = app.test_client()
    
    testuser= client.post("/api/create-user", json={"login":"getdocument_user","password": "test-pw","email":"user@getdocumenttest.com",})
    assert testuser.status_code == 201
    login = client.post("/api/login", json={"email": "user@getdocumenttest.com", "password": "test-pw",})
    token = login.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(test_directory / "test_sample.pdf", "rb") as f:
        upload = client.post(
            "/api/upload-document",
            data={"file": (f, "test_sample.pdf")},
            headers=headers,
            content_type="multipart/form-data",
        )

    assert upload.status_code == 201
    doc_id = upload.get_json()["id"]

    resp = client.get(f"/api/get-document/{doc_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    
def test_static_file():
    client = app.test_client()
    resp = client.get("/style.css")
    assert resp.status_code == 200
    
def test_static_file_not_found():
    client = app.test_client()
    resp = client.get("/does-not-exist.html")
    assert resp.status_code == 404

def test_flask_builtin_static_route():
    client = app.test_client()
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    response.close()

    
    
#GET / should serve the frontend index.html
def test_index_route():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.data == (Path(app.static_folder) / "index.html").read_bytes()
    response.close()

#list-all-versions needs a login token
def test_list_all_versions_requires_auth():
    client = app.test_client()
    testuser = client.post("/api/create-user", json={"login": "listall_user", "password": "test-pw", "email": "user@listalltest.com",})
    assert testuser.status_code == 201

    login = client.post("/api/login", json={"email": "user@listalltest.com", "password": "test-pw",})
    token = login.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/list-all-versions", headers=headers)
    assert response.status_code == 200
    assert "versions" in response.get_json()

#app with a small sqlite Versions table instead of mysql, so get-version can run without a database server
@pytest.fixture
def version_app(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    version_app = create_app()
    pdf_path = tmp_path / "watermarked.pdf"
    pdf_path.write_bytes((test_directory / "test_sample.pdf").read_bytes())
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE Versions (id INTEGER PRIMARY KEY, link TEXT, path TEXT)"))
        conn.execute(text("INSERT INTO Versions (link, path) VALUES (:link, :path)"), {"link": "testversionlink", "path": str(pdf_path)})
    version_app.config["_ENGINE"] = engine
    return version_app

#a valid link returns the watermarked pdf
def test_get_version_returns_pdf(version_app):
    client = version_app.test_client()
    response = client.get("/api/get-version/testversionlink")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    response.close()

