from server import app

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
        "email": "pathtest-unittest@example.com",
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
            "email": f"bad-{bad_logins.index(bad_login)}@example.com",
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
        data={"file": (open("test_sample.pdf", "rb"), "test_sample.pdf"), "name": "versiontest"},
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
    
    
    
    

    
    
    