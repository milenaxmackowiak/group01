import os

from hypothesis import given, settings, HealthCheck, strategies as st

from server import app

VALID = {"login": "fuzzuser", "password": "fuzz-pw"}

#any json value that is not a string (123, 1.5, None, True, lists, dicts)
non_string_json = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False),
    lambda children: st.lists(children, max_size=3) | st.dictionaries(st.text(max_size=5), children, max_size=3),
    max_leaves=5,
)
#strings without an @ can never be a valid email
strings_without_at = st.text(max_size=100).filter(lambda s: "@" not in s)


def post_user(body):
    return app.test_client().post("/api/create-user", json=body)


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(email=non_string_json)
def test_non_string_email_rejected(email):
    response = post_user({**VALID, "email": email})
    assert response.status_code == 400, f"{email!r} gave {response.status_code}"


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(email=strings_without_at)
def test_email_without_at_rejected(email):
    response = post_user({**VALID, "email": email})
    assert response.status_code == 400, f"{email!r} gave {response.status_code}"

#check that a actual well formatted email is accepted, but it may be a duplicate so 409 is also ok
#without a mysql db (like on laptop) it gives 503, the email still passed validation so the test is still useful to check that the email validation code does not crash

#INFO REGARDING 503 STATUS CODE: 
# added 503 to the OK_CODES when DB_USER is not in the environment. Will work normally in the production environment
# Beacuse in the case when running tests without a mysql db, legit took 20 minutes for 3 lines of code to run beacuse the test wont fail in a resoble time, 
# wating for a mysql connection that was never going to happen, so now it will pass with 503 instead of failing with 500
OK_CODES = (201, 409) if "DB_USER" in os.environ else (201, 409, 503)

@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(email=st.emails())
def test_valid_email_accepted(email):
    response = post_user({**VALID, "email": email})
    assert response.status_code in OK_CODES, f"{email!r} gave {response.status_code}"


@settings(max_examples=100)
@given(body=non_string_json)
def test_non_object_body_rejected(body):
    #a body like [1, 2] or 123 used to crash on payload.get
    response = post_user(body)
    assert response.status_code == 400, f"{body!r} gave {response.status_code}"
