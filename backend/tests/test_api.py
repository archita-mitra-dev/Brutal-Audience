import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("DATABASE_PATH", tmp.name)
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
    os.unlink(tmp.name)


BODY = {
    "title": "The Dark Lighthouse",
    "content_type": "story",
    "content": "First paragraph with enough words to stand alone happily.\n\nSecond paragraph, equally long enough to be its own segment.",
}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "llm_configured" in r.json()
    assert "key" not in str(r.json()).lower().replace("llm_configured", "")


def test_segment_preview(client):
    r = client.post("/api/segment", json={"content": BODY["content"], "content_type": "story"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["segments"]) == 2
    assert data["segments"][0]["id"] == 1


def test_submission_roundtrip_preserves_content(client):
    r = client.post("/api/submissions", json=BODY)
    assert r.status_code == 201
    sub = r.json()
    assert sub["content"] == BODY["content"]  # byte-exact
    got = client.get(f"/api/submissions/{sub['id']}").json()
    assert got["content"] == BODY["content"]
    assert [s["id"] for s in got["segments"]] == [1, 2]
    assert len(client.get("/api/submissions").json()) == 1
    assert client.delete(f"/api/submissions/{sub['id']}").status_code == 204
    assert client.get(f"/api/submissions/{sub['id']}").status_code == 404


def test_empty_content_rejected(client):
    r = client.post("/api/submissions", json={**BODY, "content": "   \n\n  "})
    assert r.status_code == 422


def test_upload_txt(client):
    r = client.post("/api/upload", files={"file": ("a.txt", b"hello\n\nworld", "text/plain")})
    assert r.status_code == 200
    assert r.json()["text"] == "hello\n\nworld"


def test_upload_unsupported(client):
    r = client.post("/api/upload", files={"file": ("a.exe", b"x", "application/octet-stream")})
    assert r.status_code == 400
