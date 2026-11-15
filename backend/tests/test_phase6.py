"""Phase 6: arrival order for the Live Audience Theatre, and the Blind Audience Test."""
import asyncio
import json

from app.personas.definitions import PERSONAS
from app.personas.prompts import build_user_prompt
from app.simulation.engine import run_simulation

from .test_engine import Recorder, TEXTS, submission
from .test_runs_api import BODY, client, wait_done  # noqa: F401  (client is a pytest fixture)


def _run(blind, sub=None):
    rec = Recorder()
    asyncio.run(run_simulation(
        submission=sub or submission(), personas=PERSONAS, backend=rec,
        on_reaction=lambda r: None, stop=asyncio.Event(), max_retries=0, blind=blind,
    ))
    return rec


# ---- Blind Audience Test ------------------------------------------------------------------
def test_blind_run_withholds_the_title_from_every_prompt():
    sub = submission()
    sub["title"] = "The Twist Is He Was Dead All Along"
    rec = _run(True, sub)
    prompts = [build_user_prompt(r) for r in rec.requests]
    assert prompts and all("Twist" not in p and "Dead All Along" not in p for p in prompts)
    assert all("WORK: Untitled" in p for p in prompts)


def test_non_blind_run_still_shows_the_title():
    sub = submission()
    sub["title"] = "The Dark Lighthouse"
    prompts = [build_user_prompt(r) for r in _run(False, sub).requests]
    assert all('WORK: "The Dark Lighthouse"' in p for p in prompts)


def test_blind_run_never_shows_unread_text_or_the_ending():
    rec = _run(True)
    for req in rec.requests:
        prompt = build_user_prompt(req)
        later = TEXTS[req.current.id:]                      # everything after the current segment
        assert not any(t in prompt for t in later)
    first = [r for r in rec.requests if r.current.id == 1][0]
    assert "DELTA ending" not in build_user_prompt(first)


def test_prompts_carry_no_author_identity(client):          # noqa: F811
    me = client.get("/api/auth/me").json()
    sub = client.post("/api/submissions", json=BODY).json()
    rec = _run(True, {"title": sub["title"], "content_type": "story", "segments": sub["segments"]})
    blob = " ".join(build_user_prompt(r) for r in rec.requests)
    assert me["email"] not in blob and me["display_name"] not in blob


def test_run_api_defaults_to_blind_and_records_it(client):   # noqa: F811
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    assert run["blind"] is True
    assert wait_done(client, run["id"])["blind"] is True


def test_blind_can_be_turned_off(client):                    # noqa: F811
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo", "blind": False}).json()
    assert run["blind"] is False


# ---- Live Audience Theatre: arrival order ---------------------------------------------------
def test_reactions_get_a_unique_increasing_arrival_sequence(client):   # noqa: F811
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    d = wait_done(client, run["id"])
    seqs = sorted(r["seq"] for r in d["reactions"])
    assert seqs == list(range(1, len(d["reactions"]) + 1))
    # one persona's own reactions arrive in reading order
    for key in {r["persona"] for r in d["reactions"]}:
        mine = sorted((r for r in d["reactions"] if r["persona"] == key), key=lambda r: r["seq"])
        assert [r["segment_id"] for r in mine] == sorted(r["segment_id"] for r in mine)


def test_analysis_endpoint_includes_the_meter(client):       # noqa: F811
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    wait_done(client, run["id"])
    a = client.get(f"/api/runs/{run['id']}/analysis").json()
    assert a["meter"]["document"]["level"] in {"holds", "mixed", "shaky", "brutal"}
    assert len(a["meter"]["segments"]) == len(sub["segments"])
    assert "strong_mean" in a["meter"]["thresholds"]
