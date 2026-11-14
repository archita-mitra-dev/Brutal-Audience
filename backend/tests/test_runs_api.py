import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings

BODY = {
    "title": "The Dark Lighthouse",
    "content_type": "story",
    "content": (
        "The lighthouse had been dark for eleven years, and nobody in Port Ellery talked about why.\n\n"
        "\"Don't go up there,\" the ferryman told her. \"Not after what happened to Old Tom!\"\n\n"
        "Mara climbed anyway, one hundred and twelve steps, lantern shaking in her hand."
    ),
}


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("DATABASE_PATH", tmp.name)
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
    for ext in ("", "-wal", "-shm"):
        try:
            os.unlink(tmp.name + ext)
        except FileNotFoundError:
            pass


def wait_done(client, run_id, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        d = client.get(f"/api/runs/{run_id}").json()
        if d["status"] in {"completed", "failed", "cancelled"}:
            return d
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_health_reports_demo_default_without_key(client):
    h = client.get("/api/health").json()
    assert h["llm_configured"] is False and h["mode_default"] == "demo"
    assert h["phase"] == 4


def test_full_demo_run(client):
    sub = client.post("/api/submissions", json=BODY).json()
    r = client.post(f"/api/submissions/{sub['id']}/runs", json={})
    assert r.status_code == 201
    run = r.json()
    assert run["mode"] == "demo" and "not AI" in run["model"]
    assert run["total_steps"] == 4 * len(sub["segments"])

    done = wait_done(client, run["id"])
    assert done["status"] == "completed"
    assert done["done_steps"] == done["total_steps"]
    assert len(done["reactions"]) == done["total_steps"]
    assert {x["persona"] for x in done["reactions"]} == {"doom", "critic", "fan", "newbie"}

    seg_text = {s["id"]: s["text"] for s in done["segments"]}
    for x in done["reactions"]:
        assert 0 <= x["engagement_score"] <= 10
        assert x["evidence"] in seg_text[x["segment_id"]]


def test_live_mode_without_key_is_refused(client):
    sub = client.post("/api/submissions", json=BODY).json()
    r = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "live"})
    assert r.status_code == 400 and "LLM_API_KEY" in r.json()["detail"]


def test_unknown_submission_and_run(client):
    assert client.post("/api/submissions/nope/runs", json={}).status_code == 404
    assert client.get("/api/runs/nope").status_code == 404
    assert client.post("/api/runs/nope/cancel").status_code == 404


def test_cancel_finished_run_is_conflict(client):
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    wait_done(client, run["id"])
    assert client.post(f"/api/runs/{run['id']}/cancel").status_code == 409


def test_deleting_submission_deletes_its_runs(client):
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={}).json()
    wait_done(client, run["id"])
    assert client.delete(f"/api/submissions/{sub['id']}").status_code == 204
    assert client.get(f"/api/runs/{run['id']}").status_code == 404
