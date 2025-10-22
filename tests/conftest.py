# tests/conftest.py
import pathlib, pytest, os
from dotenv import load_dotenv

@pytest.fixture(scope="session", autouse=True)
def _load_test_env():
    load_dotenv(pathlib.Path(__file__).parent / ".env.test", override=True)

@pytest.fixture(scope="session", autouse=True)
def _init_db():
    from app.store import init_db
    init_db()

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
