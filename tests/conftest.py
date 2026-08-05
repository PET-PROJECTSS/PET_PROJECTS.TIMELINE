import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="timeline_tests_")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(_TMP_DIR, "test.db").replace("\\", "/"))
os.environ["ENV"] = "prod"
os.environ["TIMELINE_ADMIN_PASSWORD"] = "admin-pass-123"
os.environ["TIMELINE_OBSERVER_PASSWORD"] = "observer-pass-123"
os.environ["TIMELINE_LOGIN_MAX_ATTEMPTS"] = "100"
os.environ["TIMELINE_LOGIN_LOCKOUT_SECONDS"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.db import engine, run_migrations, seed
from app.main import app as fastapi_app


@pytest.fixture(scope="session", autouse=True)
def _schema():
    run_migrations()
    seed()
    yield
    engine.dispose()


@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture()
def admin_headers(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def observer_headers(client):
    r = client.post("/api/auth/login", json={"username": "observer", "password": "observer-pass-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
