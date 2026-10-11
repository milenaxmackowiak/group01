import os
import pytest
from sqlalchemy import create_engine, text
#creat database that is used for testing so we don't have so many new accounts in the database
def testing_db():
    url = (f"mysql+pymysql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ.get('DB_HOST', '127.0.0.1')}:{os.environ.get('DB_PORT', '3306')}"
        f"/{os.environ.get('DB_NAME', 'tatou')}?charset=utf8mb4")
    return create_engine(url)


#clean up old data
@pytest.fixture(autouse=True, scope="session")
def clean_up_test_data():
    if "DB_USER" not in os.environ:
        print("no database to clean up")
        return  # no real database here (like when running on laptop)
    engine = testing_db()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM Users WHERE email LIKE '%@deletetest.com' OR email LIKE '%@versiontest.com' OR email LIKE '%@samename.com' OR email LIKE '%@testpath.com' OR email LIKE '%@testbadusername.com'"))
