import hashlib
import time
from datetime import datetime

from app.config import SCHEMA_VERSION
from app.db import SessionLocal, seed
from app.models import LoginSession, Roadmap, User
from app.payload import default_payload
from app.security import hash_password, needs_rehash, verify_password


def _payload(**overrides):
    p = default_payload()
    p.update(overrides)
    return p


def _create(client, headers, name="Тест", payload=None):
    r = client.post("/api/roadmaps", headers=headers,
                    json={"name": name, "payload": payload or _payload()})
    assert r.status_code == 200, r.text
    return r.json()


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Roadmap Builder" in r.text
    assert "/static/css/style.css" in r.text
    assert "/static/js/app.js" in r.text


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "Strict-Transport-Security" in r.headers


def test_login_too_long_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "x" * 1000})
    assert r.status_code == 422


def test_seed_rotates_password_when_env_changes(client):
    session = SessionLocal()
    user = session.query(User).filter_by(username="admin").first()
    original = user.password_hash
    user.password_hash = hash_password("custom-pass-456")
    session.commit()
    session.close()

    try:
        seed()
        session = SessionLocal()
        user = session.query(User).filter_by(username="admin").first()
        assert verify_password("admin-pass-123", user.password_hash)
        session.close()
    finally:
        session = SessionLocal()
        user = session.query(User).filter_by(username="admin").first()
        user.password_hash = original
        session.commit()
        session.close()


def test_seed_idempotent_keeps_hash(client):
    session = SessionLocal()
    user = session.query(User).filter_by(username="admin").first()
    original = user.password_hash
    session.close()

    seed()

    session = SessionLocal()
    assert session.query(User).filter_by(username="admin").first().password_hash == original
    session.close()


def test_legacy_hash_verified_and_upgraded():
    salt = "ab" * 16
    digest = hashlib.pbkdf2_hmac("sha256", b"admin-pass-123", bytes.fromhex(salt), 100_000).hex()
    legacy = f"{salt}${digest}"
    assert verify_password("admin-pass-123", legacy)
    assert needs_rehash(legacy)

    fresh = hash_password("admin-pass-123")
    assert verify_password("admin-pass-123", fresh)
    assert not needs_rehash(fresh)
    assert verify_password("wrong", fresh) is False


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_roadmaps_require_auth(client):
    assert client.get("/api/roadmaps").status_code == 401


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_observer_can_read_but_not_write(client, observer_headers):
    assert client.get("/api/roadmaps", headers=observer_headers).status_code == 200
    r = client.post("/api/roadmaps", headers=observer_headers,
                    json={"name": "x", "payload": _payload()})
    assert r.status_code == 403


def test_admin_crud(client, admin_headers):
    created = _create(client, admin_headers)
    assert created["version"] == 0
    rid = created["id"]

    lst = client.get("/api/roadmaps", headers=admin_headers)
    assert lst.status_code == 200
    assert any(t["id"] == rid for t in lst.json())

    got = client.get(f"/api/roadmaps/{rid}", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["name"] == "Тест"
    assert got.json()["version"] == 0

    upd = client.put(f"/api/roadmaps/{rid}", headers=admin_headers,
                     json={"name": "Тест2", "payload": _payload(), "base_version": 0})
    assert upd.status_code == 200
    assert upd.json()["version"] == 1

    dele = client.delete(f"/api/roadmaps/{rid}", headers=admin_headers)
    assert dele.status_code == 200
    assert client.get(f"/api/roadmaps/{rid}", headers=admin_headers).status_code == 404


def test_update_conflict_409(client, admin_headers):
    rid = _create(client, admin_headers)["id"]
    r = client.put(f"/api/roadmaps/{rid}", headers=admin_headers,
                   json={"name": "A", "payload": _payload(), "base_version": 99})
    assert r.status_code == 409
    got = client.get(f"/api/roadmaps/{rid}", headers=admin_headers).json()
    assert got["version"] == 0


def test_update_conflict_via_frontend_contract(client, admin_headers):
    rid = _create(client, admin_headers)["id"]

    def body(version):
        return {"name": "A", "payload": _payload(), "base_version": version}

    first = client.put(f"/api/roadmaps/{rid}", headers=admin_headers, json=body(0))
    assert first.status_code == 200
    assert first.json()["version"] == 1
    stale = client.put(f"/api/roadmaps/{rid}", headers=admin_headers, json=body(0))
    assert stale.status_code == 409
    got = client.get(f"/api/roadmaps/{rid}", headers=admin_headers).json()
    assert got["version"] == 1


def test_update_bumps_updated_at(client, admin_headers):
    rid = _create(client, admin_headers)["id"]
    before = datetime.fromisoformat(
        client.get(f"/api/roadmaps/{rid}", headers=admin_headers).json()["updated_at"]
    )
    time.sleep(1.1)
    r = client.put(f"/api/roadmaps/{rid}", headers=admin_headers,
                   json={"name": "Обновлено", "payload": _payload(), "base_version": 0})
    assert r.status_code == 200
    after = datetime.fromisoformat(
        client.get(f"/api/roadmaps/{rid}", headers=admin_headers).json()["updated_at"]
    )
    assert after > before


def test_payload_duplicate_node_ids(client, admin_headers):
    p = _payload()
    p["nodes"] = [p["nodes"][0], dict(p["nodes"][0])]
    r = client.post("/api/roadmaps", headers=admin_headers,
                    json={"name": "bad", "payload": p})
    assert r.status_code == 422


def test_payload_broken_link(client, admin_headers):
    p = _payload()
    p["links"] = [{"id": "zz", "from": "ghost", "to": "node-1", "label": ""}]
    r = client.post("/api/roadmaps", headers=admin_headers,
                    json={"name": "bad", "payload": p})
    assert r.status_code == 422


def test_payload_bad_node_type(client, admin_headers):
    p = _payload()
    p["nodes"][0]["type"] = "Mile"
    r = client.post("/api/roadmaps", headers=admin_headers,
                    json={"name": "bad", "payload": p})
    assert r.status_code == 422


def test_payload_too_large(client, admin_headers):
    p = _payload()
    p["nodes"][0]["note"] = "x" * (3 * 1024 * 1024)
    r = client.post("/api/roadmaps", headers=admin_headers,
                    json={"name": "big", "payload": p})
    assert r.status_code == 413


def test_payload_too_large_without_content_length():
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from app.main import limit_payload_size

    async def receive():
        return {"type": "http.request", "body": b"x" * (3 * 1024 * 1024), "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/roadmaps",
        "raw_path": b"/api/roadmaps",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("1.2.3.4", 123),
    }

    async def call_next(request):
        await request.body()
        return Response("ok")

    async def run():
        return await limit_payload_size(Request(scope, receive), call_next)

    assert asyncio.run(run()).status_code == 413


def test_payload_ok_without_content_length():
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from app.main import limit_payload_size

    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/roadmaps",
        "raw_path": b"/api/roadmaps",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("1.2.3.4", 123),
    }

    async def call_next(request):
        await request.body()
        return Response("ok")

    async def run():
        return await limit_payload_size(Request(scope, receive), call_next)

    assert asyncio.run(run()).body == b"ok"


def test_migrates_old_format(client, admin_headers):
    old = {
        "schema_version": 1,
        "nodes": [
            {"id": "n1", "x": 0, "y": 0, "width": 320, "height": 200,
             "title": "Первый", "type": "path", "desc": "Старое описание", "months": "3"},
            {"id": "n2", "x": 100, "y": 100, "width": 320, "height": 200,
             "title": "Цель", "type": "Goal", "desc": "", "months": ""},
        ],
        "edges": [{"id": "e1", "from": "n1", "to": "n2", "months": "1"}],
        "viewport": {"x": 10, "y": 20, "scale": 1.5},
    }
    session = SessionLocal()
    rm = Roadmap(name="Старый", payload=old, version=0)
    session.add(rm)
    session.commit()
    rid = rm.id
    session.close()

    seed()

    got = client.get(f"/api/roadmaps/{rid}", headers=admin_headers)
    assert got.status_code == 200
    p = got.json()["payload"]
    assert p["schema_version"] == SCHEMA_VERSION
    n1 = next(n for n in p["nodes"] if n["id"] == "n1")
    assert n1["note"] == "Старое описание"
    assert n1["duration"] == "3"
    assert "desc" not in n1 and "months" not in n1
    assert p["links"][0]["from"] == "n1"
    assert p["links"][0]["to"] == "n2"
    assert p["links"][0]["label"] == "1"
    assert p["viewport"] == {"panX": 10, "panY": 20, "scale": 1.5}


def test_logout_invalidates_token(client, admin_headers):
    assert client.get("/api/auth/me", headers=admin_headers).status_code == 200
    r = client.post("/api/auth/logout", headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=admin_headers).status_code == 401


def test_expired_session(client, admin_headers):
    token = admin_headers["Authorization"].removeprefix("Bearer ")
    session = SessionLocal()
    session.query(LoginSession).filter(LoginSession.token == token).update(
        {"expires_at": "2000-01-01T00:00:00+00:00"}, synchronize_session=False
    )
    session.commit()
    session.close()
    assert client.get("/api/auth/me", headers=admin_headers).status_code == 401


def test_substeps_roundtrip(client, admin_headers):
    p = _payload()
    p["nodes"][0]["substeps"] = [
        {"id": "s1", "title": "Собрать документы", "done": False},
        {"id": "s2", "title": "Оформить загранпаспорт", "done": True},
    ]
    rid = _create(client, admin_headers, payload=p)["id"]
    got = client.get(f"/api/roadmaps/{rid}", headers=admin_headers).json()
    node = next(n for n in got["payload"]["nodes"] if n["id"] == p["nodes"][0]["id"])
    assert node["substeps"] == [
        {"id": "s1", "title": "Собрать документы", "done": False},
        {"id": "s2", "title": "Оформить загранпаспорт", "done": True},
    ]


def test_substeps_rejected_on_goal(client, admin_headers):
    p = _payload()
    goal = next(n for n in p["nodes"] if n["type"] == "Goal")
    goal["substeps"] = [{"id": "s1", "title": "Недопустимо", "done": False}]
    r = client.post("/api/roadmaps", headers=admin_headers,
                    json={"name": "bad", "payload": p})
    assert r.status_code == 422


def test_substeps_duplicate_ids_rejected(client, admin_headers):
    p = _payload()
    p["nodes"][0]["substeps"] = [
        {"id": "s1", "title": "Первый", "done": False},
        {"id": "s1", "title": "Дубликат", "done": False},
    ]
    r = client.post("/api/roadmaps", headers=admin_headers,
                    json={"name": "bad", "payload": p})
    assert r.status_code == 422


def test_migrates_v2_payload_with_substeps(client, admin_headers):
    old = {
        "schema_version": 2,
        "nodes": [
            {"id": "n1", "x": 0, "y": 0, "width": 320, "height": 200,
             "title": "Документы", "type": "Path", "done": False,
             "note": "", "due": "", "duration": "",
             "substeps": [
                 {"id": "a", "title": "Загранпаспорт", "done": 1},
                 {"id": "b", "title": "Апостиль", "done": 0},
                 {"id": "b", "title": "Дубликат", "done": False},
                 {"title": "Без id", "done": False},
                 "мусор",
             ]},
            {"id": "n2", "x": 100, "y": 100, "width": 320, "height": 200,
             "title": "Купить квартиру", "type": "Goal", "done": False,
             "note": "", "due": "", "duration": "",
             "substeps": [{"id": "x", "title": "Должно быть удалено", "done": False}]},
        ],
        "links": [],
        "viewport": {"panX": 0, "panY": 0, "scale": 1},
        "uid": 2,
    }
    session = SessionLocal()
    rm = Roadmap(name="Старый", payload=old, version=0)
    session.add(rm)
    session.commit()
    rid = rm.id
    session.close()

    seed()

    got = client.get(f"/api/roadmaps/{rid}", headers=admin_headers).json()
    p = got["payload"]
    assert p["schema_version"] == SCHEMA_VERSION
    nodes = {n["id"]: n for n in p["nodes"]}
    assert nodes["n1"]["substeps"] == [
        {"id": "a", "title": "Загранпаспорт", "done": True},
        {"id": "b", "title": "Апостиль", "done": False},
        {"id": "step-3", "title": "Без id", "done": False},
    ]
    assert nodes["n2"]["substeps"] == []
