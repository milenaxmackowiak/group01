import os
from urllib import response
import conftest
from sqlalchemy import text
import uuid

from pymysql import NULL
import pytest

from server import app

VALID = {"login": "regressionuser", "password": "regression-pw"}

#Again added a 500 status code as OK as without a mysql db a valid email gives 503, it still passed validation
OK_CODES = (201, 409) if "DB_USER" in os.environ else (201, 409, 503)


def post_user(body):
    return app.test_client().post("/api/create-user", json=body)


#non-string emails used to crash on strip() with a 500
@pytest.mark.parametrize("email", [123, 0, 1.5, None, True, False, [], ["a@b.com"], {}, {"email": "a@b.com"}])
def test_non_string_email_rejected(email):
    response = post_user({**VALID, "email": email})
    assert response.status_code == 400, f"{email!r} gave {response.status_code}"


#strings without an @ can never be a valid email
@pytest.mark.parametrize("email", ["", " ", "plainaddress", "user.example.com", "\x00", "ü" * 100, "user at example.com", "0"])
def test_email_without_at_rejected(email):
    response = post_user({**VALID, "email": email})
    assert response.status_code == 400, f"{email!r} gave {response.status_code}"


#only the email from the fuzzer gets checked, the login is unique so it never causes a 409
#the email itself stays fixed, so from the second run on a real db gives 409 (email exists), that is still ok
FOUND_EMAIL_CODES = (201, 409) if "DB_USER" in os.environ else (503,)

#both login and email are new every run, so with a real db it must be created
UNIQUE_CODES = (201,) if "DB_USER" in os.environ else (503,)


#Regression test for found fuzzing emails that need to stay static
# meaning that well formatted emails must get past validation, '_@A.Gy' was a shrink value found by the fuzzer
@pytest.mark.parametrize("email", ["_@A.Gy", "user@example.com", "first.last+tag@sub.example.org"])
def test_valid_email_accepted(email):
    unique_login = f"regression_{uuid.uuid4().hex}"     

    response = post_user({"login": unique_login, "password": "regression-pw", "email": email})  
    assert response.status_code in FOUND_EMAIL_CODES, f"{email!r} gave {response.status_code}"


# added unique login and semi unique emails as they are will be built based of the orginal found to avoid duplicate errors, as the first test only runs found emails
@pytest.mark.parametrize("email", ["_@A.Gy", "user@example.com", "first.last+tag@sub.example.org"])
def test_unique_valid_email_accepted(email):
    unique = uuid.uuid4().hex                    
    local, domain = email.split("@")
    unique_email = f"{unique}{local}@{domain}"   
    unique_login = f"regression_{unique}"        

    response = post_user({"login": unique_login, "password": "regression-pw", "email": unique_email})
    assert response.status_code in UNIQUE_CODES, f"{unique_email!r} gave {response.status_code}"



#a body like [1, 2] or 123 used to crash on payload.get
#no body tests 
@pytest.mark.parametrize("body", [[1, 2], [], 123, 1.5, None , True, "just a string"]) #The None value is a regression test for a raw JSON null body; as json=None would send no body at all, which is not the same as sending a null body. 
def test_non_object_body_rejected(body):
    response = post_user(body)
    assert response.status_code == 400, f"{body!r} gave {response.status_code}"

#Small test for a raw JSON null body; as json=None would send no body at all, which is not the same as sending a null body.  
def test_null_body_rejected():   
    response = app.test_client().post(
        "/api/create-user",
        data="null",
        content_type="application/json"
    )
    assert response.status_code == 400, f"null body gave {response.status_code}"
    assert "error" in response.get_json()
