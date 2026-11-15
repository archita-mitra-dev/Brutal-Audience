import os
import sqlite3
import tempfile
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.security import throttle

from .helpers import authenticate

BODY = {"title": "Mine", "content_type": "story",
        "content": "First paragraph with enough words to stand alone happily.\n\nSecond paragraph, equally long enough to be its own segment."}
PW = "correct horse battery"


@pytest.fixture()
def env(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close()
    monkeypatch.setenv("DATABASE_PATH", tmp.name)
    monkeypatch.setenv("JWT_SECRET", "test-secret-test-secret-test-secret-123")
    monkeypatch.setenv("LLM_API_KEY", ""); monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear(); throttle.reset()
    yield tmp.name
    get_settings.cache_clear()
    for ext in ("", "-wal", "-shm"):
        try: os.unlink(tmp.name + ext)
        except FileNotFoundError: pass


@pytest.fixture()
def client(env):
    from app.main import app
    with TestClient(app) as c:
        yield c


def fresh(client_app=None):
    from app.main import app
    return TestClient(app)


def register(c, email="a@example.com", password=PW, **kw):
    return c.post("/api/auth/register", json={"email": email, "password": password, **kw})


# --- register / login / me -----------------------------------------------------------------
def test_register_login_me_roundtrip(client):
    r = register(client, " A@Example.com ", display_name="Ana")
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "a@example.com" and body["user"]["display_name"] == "Ana"
    assert "password" not in str(body).lower().replace("password_hash", "")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]
    lg = client.post("/api/auth/login", json={"email": "A@EXAMPLE.com", "password": PW})
    assert lg.status_code == 200 and lg.json()["user"]["id"] == body["user"]["id"]


def test_display_name_defaults_to_email_prefix(client):
    assert register(client, "sam@example.com").json()["user"]["display_name"] == "sam"


def test_password_is_stored_hashed(client, env):
    register(client)
    row = sqlite3.connect(env).execute("SELECT password_hash FROM users").fetchone()[0]
    assert row.startswith("scrypt$") and PW not in row


@pytest.mark.parametrize("payload,status", [
    ({"email": "not-an-email", "password": PW}, 422),
    ({"email": "a@example.com", "password": "short"}, 422),
    ({"email": "a@example.com", "password": "x" * 129}, 422),
    ({"password": PW}, 422),
])
def test_register_validation(client, payload, status):
    assert client.post("/api/auth/register", json=payload).status_code == status


def test_duplicate_email_conflicts_case_insensitively(client):
    assert register(client, "a@example.com").status_code == 201
    assert register(client, "A@EXAMPLE.COM").status_code == 409


def test_wrong_password_and_unknown_user_look_identical(client):
    register(client)
    a = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    b = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "wrong-password"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_throttle(client, monkeypatch):
    register(client)
    bad = {"email": "a@example.com", "password": "nope-nope"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    r = client.post("/api/auth/login", json=bad)
    assert r.status_code == 429 and "Retry-After" in r.headers
    # even the right password is refused while throttled
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 429


def test_registration_can_be_closed(env, monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "false"); get_settings.cache_clear()
    from app.main import app
    with TestClient(app) as c:
        assert register(c).status_code == 403


# --- tokens ----------------------------------------------------------------------------------------
def test_protected_routes_need_a_token(client):
    for method, path in [("get", "/api/submissions"), ("post", "/api/submissions"), ("post", "/api/segment"),
                         ("get", "/api/runs/x"), ("get", "/api/runs/x/analysis"), ("post", "/api/runs/x/verdict"),
                         ("get", "/api/auth/me")]:
        r = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 401, (path, r.status_code)
    assert client.get("/api/health").status_code == 200   # health stays public


def test_garbage_tampered_and_expired_tokens_are_rejected(client):
    uid = register(client).json()["user"]["id"]
    h = lambda t: {"Authorization": f"Bearer {t}"}
    assert client.get("/api/auth/me", headers=h("garbage")).status_code == 401
    forged = jwt.encode({"sub": uid, "exp": time.time() + 600}, "some-other-secret-some-other-secret", algorithm="HS256")
    assert client.get("/api/auth/me", headers=h(forged)).status_code == 401
    expired = jwt.encode({"sub": uid, "exp": time.time() - 5}, "test-secret-test-secret-test-secret-123", algorithm="HS256")
    assert client.get("/api/auth/me", headers=h(expired)).status_code == 401
    unsigned = jwt.encode({"sub": uid, "exp": time.time() + 600}, key=None, algorithm="none")
    assert client.get("/api/auth/me", headers=h(unsigned)).status_code == 401


# --- ownership ---------------------------------------------------------------------------------------
def make_two_users(client):
    ana = authenticate(client, "ana@example.com")
    tok_a = client.headers["Authorization"]
    client.headers.pop("Authorization")
    ben = authenticate(client, "ben@example.com")
    tok_b = client.headers["Authorization"]
    return ana, {"Authorization": tok_a}, ben, {"Authorization": tok_b}


def test_users_cannot_see_or_touch_each_others_work(client):
    _, A, _, B = make_two_users(client)
    sub = client.post("/api/submissions", json=BODY, headers=A).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}, headers=A).json()
    end = time.time() + 15
    while client.get(f"/api/runs/{run['id']}", headers=A).json()["status"] != "completed" and time.time() < end:
        time.sleep(0.1)
    assert client.post(f"/api/runs/{run['id']}/verdict", headers=A).status_code == 200

    # owner can reach everything
    assert client.get(f"/api/submissions/{sub['id']}", headers=A).status_code == 200
    # the other user gets 404 (not 403) everywhere, so existence isn't revealed
    for method, path in [("get", f"/api/submissions/{sub['id']}"), ("delete", f"/api/submissions/{sub['id']}"),
                         ("post", f"/api/submissions/{sub['id']}/runs"), ("get", f"/api/runs/{run['id']}"),
                         ("post", f"/api/runs/{run['id']}/cancel"), ("get", f"/api/runs/{run['id']}/analysis"),
                         ("get", f"/api/runs/{run['id']}/verdict"), ("post", f"/api/runs/{run['id']}/verdict")]:
        r = getattr(client, method)(path, headers=B, **({"json": {"mode": "demo"}} if path.endswith("/runs") else {}))
        assert r.status_code == 404, (method, path, r.status_code)
    assert client.get("/api/submissions", headers=B).json() == []
    assert [s["id"] for s in client.get("/api/submissions", headers=A).json()] == [sub["id"]]
    # still intact after B's attempted delete
    assert client.get(f"/api/submissions/{sub['id']}", headers=A).status_code == 200


# --- account deletion ----------------------------------------------------------------------------------
def test_deleting_account_removes_everything_and_invalidates_token(client, env):
    authenticate(client, "ana@example.com")
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    end = time.time() + 15
    while client.get(f"/api/runs/{run['id']}").json()["status"] != "completed" and time.time() < end:
        time.sleep(0.1)
    client.post(f"/api/runs/{run['id']}/verdict")
    assert client.delete("/api/auth/me").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    con = sqlite3.connect(env)
    for table in ("users", "submissions", "segments", "runs", "reactions", "verdicts"):
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse battery"}).status_code == 401


# --- migrating a pre-accounts database ----------------------------------------------------------------------
def test_old_database_is_upgraded_and_legacy_rows_are_orphaned(env):
    con = sqlite3.connect(env)
    con.executescript("""
        CREATE TABLE submissions (id TEXT PRIMARY KEY, title TEXT NOT NULL, content_type TEXT NOT NULL,
                                  content TEXT NOT NULL, created_at TEXT NOT NULL);
        INSERT INTO submissions VALUES ('old1', 'Old draft', 'story', 'x', '2026-01-01T00:00:00+00:00');
    """)
    con.commit(); con.close()
    from app.main import app
    with TestClient(app) as c:
        authenticate(c, "ana@example.com")
        assert c.get("/api/submissions").json() == []                 # legacy draft is not visible to anyone
        assert c.get("/api/submissions/old1").status_code == 404
        assert c.post("/api/submissions", json=BODY).status_code == 201   # new writes work on the upgraded table
