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


    
    
    