import asyncio
import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from app.analysis.stats import analyse
from app.analysis.verdict import VerdictError, generate_demo, generate_live
from app.config import get_settings

from .helpers import authenticate
from app.llm.base import LLMError
from app.personas.definitions import PERSONAS_BY_KEY
from app.schemas import ReactionOut

SEGS = [
    {"id": 1, "label": "Paragraph 1", "text": "The lighthouse had been dark for eleven years."},
    {"id": 2, "label": "Paragraph 2", "text": "Mara climbed anyway, one hundred and twelve steps."},
]


def reactions():
    out = []
    table = {1: {"doom": 8, "critic": 7, "fan": 8, "newbie": 7}, 2: {"doom": 2, "critic": 4, "fan": 9, "newbie": 3}}
    for seg, d in table.items():
        for p, s in d.items():
            out.append(ReactionOut(
                persona=p, persona_name=PERSONAS_BY_KEY[p].name, segment_id=seg, status="ok",
                engagement_score=s, emotion="curious", inner_thought="hm", would_continue=s > 3,
                evidence=SEGS[seg - 1]["text"][:20], evidence_verified=True, reason=f"{p} reason {seg}."))
    return out


def analysis(rs):
    return analyse("r1", "completed", SEGS, rs, 8)


class FakeClient:
    name = "fake:model"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    async def complete_json(self, system, user):
        self.calls.append(user)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


def good(evidence="Mara climbed anyway"):
    return {
        "overall": "Mixed.", "strongest_why": "Hook.", "weakest_why": "Slow.",
        "persona_takes": [{"persona": p, "liked": "a", "disliked": "b"} for p in PERSONAS_BY_KEY],
        "polarising_note": None,
        "suggestions": [{"title": f"t{i}", "segment_ids": [2], "problem": "p", "action": "a",
                         "evidence": evidence if i == 0 else None} for i in range(3)],
    }


def run(client, rs=None):
    rs = rs or reactions()
    return asyncio.run(generate_live(client, run_id="r1", title="T", content_type="story",
                                     segments=SEGS, reactions=rs, analysis=analysis(rs)))


def test_live_happy_path_uses_computed_numbers_not_model_numbers():
    v = run(FakeClient([good()]))
    assert v.mode == "live" and v.model == "fake:model"
    assert v.strongest.segment_id == 1 and v.weakest.segment_id == 2   # from stats, not the model
    assert len(v.suggestions) == 3 and v.suggestions[0].evidence == "Mara climbed anyway"
    assert [t.persona for t in v.persona_takes] == ["doom", "critic", "fan", "newbie"]


def test_prompt_contains_computed_facts_and_forbids_rewrites():
    c = FakeClient([good()])
    run(c)
    assert "Strongest segment: 1" in c.calls[0] and "Collision at segment 2" in c.calls[0]
    from app.analysis.verdict import SYSTEM
    assert "NOT a co-writer" in SYSTEM and "never write replacement" in SYSTEM


def test_invalid_reply_is_retried_with_correction():
    bad = good(); bad["suggestions"] = bad["suggestions"][:2]
    c = FakeClient([bad, good()])
    v = run(c)
    assert len(c.calls) == 2 and "rejected" in c.calls[1] and "exactly 3" in c.calls[1]
    assert len(v.suggestions) == 3


def test_nonexistent_segment_id_is_rejected_until_fixed():
    bad = good(); bad["suggestions"][1]["segment_ids"] = [99]
    c = FakeClient([bad, good()])
    assert len(run(c).suggestions) == 3 and "do not exist" in c.calls[1]


def test_fabricated_evidence_is_retried_then_dropped_never_kept():
    fake = good("This sentence is not in the draft at all")
    c = FakeClient([fake, fake, fake])
    v = run(c)
    assert len(c.calls) == 3
    assert all(s.evidence is None for s in v.suggestions)


def test_gives_up_with_a_clear_error():
    with pytest.raises(VerdictError):
        run(FakeClient(["not json"] * 3))


def test_llm_errors_propagate():
    with pytest.raises(LLMError):
        run(FakeClient([LLMError("down")]))


def test_demo_verdict_is_labelled_and_grounded():
    rs = reactions()
    v = generate_demo(run_id="r1", model="demo", segments=SEGS, reactions=rs, analysis=analysis(rs))
    assert v.mode == "demo" and "not by an AI audience" in v.overall
    assert 1 <= len(v.suggestions) <= 3 and v.polarising_note
    for s in v.suggestions:
        seg = next(x for x in SEGS if x["id"] == s.segment_ids[0])
        assert s.evidence is None or s.evidence in seg["text"]


# --- through the API ---------------------------------------------------------------
BODY = {"title": "T", "content_type": "story", "content": (
    "The lighthouse had been dark for eleven years, and nobody in Port Ellery talked about why.\n\n"
    "\"Don't go up there,\" the ferryman told her. \"Not after what happened to Old Tom!\"\n\n"
    "Mara climbed anyway, one hundred and twelve steps, lantern shaking in her hand.")}


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close()
    monkeypatch.setenv("DATABASE_PATH", tmp.name)
    monkeypatch.setenv("LLM_API_KEY", ""); monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()
    from app.main import app
    with TestClient(app) as c:
        authenticate(c)
        yield c
    get_settings.cache_clear()
    for ext in ("", "-wal", "-shm"):
        try: os.unlink(tmp.name + ext)
        except FileNotFoundError: pass


def finished_run(client):
    sub = client.post("/api/submissions", json=BODY).json()
    run = client.post(f"/api/submissions/{sub['id']}/runs", json={"mode": "demo"}).json()
    end = time.time() + 15
    while time.time() < end:
        if client.get(f"/api/runs/{run['id']}").json()["status"] == "completed":
            return run["id"]
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_analysis_endpoint(client):
    rid = finished_run(client)
    a = client.get(f"/api/runs/{rid}/analysis").json()
    assert a["status"] == "completed" and not a["partial"]
    assert len(a["segments"]) == 3 and len(a["personas"]) == 4
    assert a["strongest_segment_id"] is not None


def test_verdict_roundtrip_in_demo_mode(client):
    rid = finished_run(client)
    assert client.get(f"/api/runs/{rid}/verdict").status_code == 404
    r = client.post(f"/api/runs/{rid}/verdict")
    assert r.status_code == 200 and r.json()["mode"] == "demo"
    assert client.get(f"/api/runs/{rid}/verdict").json()["overall"] == r.json()["overall"]


def test_verdict_errors(client):
    assert client.get("/api/runs/nope/analysis").status_code == 404
    assert client.post("/api/runs/nope/verdict").status_code == 404
    assert client.get("/api/runs/nope/verdict").status_code == 404
