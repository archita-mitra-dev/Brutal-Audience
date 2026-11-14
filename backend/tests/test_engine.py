import asyncio
import json

from app.llm.base import FatalLLMError, LLMError
from app.personas.definitions import PERSONAS, PERSONAS_BY_KEY
from app.personas.prompts import build_system_prompt, build_user_prompt
from app.schemas import Segment
from app.simulation.backends import DemoBackend
from app.simulation.engine import react_with_retries, run_simulation
from app.simulation.types import ReactionRequest

TEXTS = [
    "ALPHA opening: the lighthouse had been dark for eleven years, and nobody talked about why.",
    "BRAVO middle: Mara arrived on the ferry with one suitcase and a letter she had not opened.",
    "CHARLIE later: the keeper's cottage smelled of salt, paper and something burnt and old.",
    "DELTA ending: the lamp lit itself at midnight and the whole harbour held its breath.",
]


def make_segments():
    out, pos = [], 0
    for i, t in enumerate(TEXTS, start=1):
        out.append({"id": i, "label": f"Paragraph {i}", "text": t, "char_start": pos, "char_end": pos + len(t)})
        pos += len(t) + 2
    return out


def submission():
    return {"title": "Test", "content_type": "story", "segments": make_segments()}


def good_reply(req: ReactionRequest) -> str:
    return json.dumps({
        "engagement_score": 6, "emotion": "curious", "inner_thought": "Hm.", "would_continue": True,
        "evidence": req.current.text[:30], "reason": "Because.",
    })


class Recorder:
    mode = "live"
    label = "recorder"

    def __init__(self, reply=good_reply):
        self.requests: list[ReactionRequest] = []
        self.reply = reply

    async def react(self, req):
        self.requests.append(req)
        await asyncio.sleep(0)
        return self.reply(req)


def run(backend, **kw):
    reactions = []
    result = asyncio.run(run_simulation(
        submission=submission(), personas=PERSONAS, backend=backend,
        on_reaction=reactions.append, stop=asyncio.Event(), max_retries=kw.get("max_retries", 2),
    ))
    return result, reactions


# ---- the critical guarantees ------------------------------------------------
def test_each_persona_reads_in_order_and_gets_every_segment_once():
    rec = Recorder()
    (status, _), reactions = run(rec)
    assert status == "completed"
    assert len(reactions) == 4 * len(TEXTS)
    for p in PERSONAS:
        ids = [r.current.id for r in rec.requests if r.persona.key == p.key]
        assert ids == [1, 2, 3, 4]


def test_no_future_segments_ever_reach_a_persona():
    rec = Recorder()
    run(rec)
    markers = ["ALPHA", "BRAVO", "CHARLIE", "DELTA"]
    for req in rec.requests:
        i = req.current.id
        # structural: seen is exactly the earlier segments
        assert [s.id for s in req.seen] == list(range(1, i))
        # textual: the actual prompt text contains no later segment's content
        prompt = build_system_prompt(req.persona) + build_user_prompt(req)
        for later in range(i + 1, len(TEXTS) + 1):
            assert markers[later - 1] not in prompt, f"segment {later} leaked into prompt for segment {i}"
        assert markers[i - 1] in prompt


def test_prompt_never_reveals_total_segment_count():
    rec = Recorder()
    run(rec)
    for req in rec.requests:
        user = build_user_prompt(req).lower()
        assert "of 4" not in user and "total" not in user


def test_personas_have_distinct_prompts():
    prompts = {p.key: build_system_prompt(p) for p in PERSONAS}
    assert len(set(prompts.values())) == 4
    for p in PERSONAS:
        assert p.name in prompts[p.key]
    # shared rule: never a co-writer
    assert all("Never rewrite" in s for s in prompts.values())


def test_persona_history_is_only_its_own():
    rec = Recorder(lambda req: json.dumps({
        "engagement_score": {"doom": 2, "critic": 4, "fan": 9, "newbie": 5}[req.persona.key],
        "emotion": "curious", "inner_thought": f"thought-{req.persona.key}", "would_continue": True,
        "evidence": req.current.text[:30], "reason": "r",
    }))
    run(rec)
    for req in rec.requests:
        for h in req.history:
            assert h.thought == f"thought-{req.persona.key}"


def test_quit_persona_is_told_it_is_reading_on_reluctantly():
    def reply(req):
        return json.dumps({"engagement_score": 1, "emotion": "bored", "inner_thought": "meh",
                           "would_continue": False, "evidence": req.current.text[:30], "reason": "r"})
    rec = Recorder(reply)
    run(rec)
    later = [r for r in rec.requests if r.current.id == 2][0]
    assert "stop reading" in build_user_prompt(later)


# ---- retries, validation, failure handling -----------------------------------
def _req(i=1):
    segs = [Segment(**s) for s in make_segments()]
    return ReactionRequest(persona=PERSONAS_BY_KEY["doom"], title="T", content_type="story",
                           seen=tuple(segs[:i - 1]), current=segs[i - 1])


def test_invalid_json_is_retried_with_correction():
    calls = []

    class Flaky:
        mode, label = "live", "flaky"

        async def react(self, req):
            calls.append(req.correction)
            return "garbage" if len(calls) == 1 else good_reply(req)

    r = asyncio.run(react_with_retries(Flaky(), _req(), max_retries=2))
    assert r.status == "ok" and r.attempts == 2
    assert calls[0] is None and "JSON" in calls[1]


def test_fabricated_evidence_is_never_stored():
    def fake(req):
        return json.dumps({"engagement_score": 5, "emotion": "curious", "inner_thought": "x",
                           "would_continue": True, "evidence": "A sentence that is not in the text at all.",
                           "reason": "r"})

    r = asyncio.run(react_with_retries(Recorder(fake), _req(), max_retries=2))
    assert r.status == "ok"
    assert r.evidence is None and r.evidence_verified is False
    assert r.attempts == 3


def test_persistent_garbage_becomes_failed_reaction_not_a_crash():
    r = asyncio.run(react_with_retries(Recorder(lambda req: "nope"), _req(), max_retries=1))
    assert r.status == "failed" and r.engagement_score is None and r.attempts == 2


def test_non_retryable_llm_error_fails_that_segment_only():
    class Blocked:
        mode, label = "live", "b"
        n = 0

        async def react(self, req):
            Blocked.n += 1
            raise LLMError("blocked by safety filter", retryable=False)

    r = asyncio.run(react_with_retries(Blocked(), _req(), max_retries=2))
    assert r.status == "failed" and Blocked.n == 1 and "safety" in r.error


def test_fatal_error_aborts_whole_run_quickly():
    class BadKey:
        mode, label = "live", "bad"
        n = 0

        async def react(self, req):
            BadKey.n += 1
            raise FatalLLMError("Model API rejected the request (401): bad key")

    (status, error), reactions = run(BadKey())
    assert status == "failed" and "401" in error
    assert BadKey.n <= len(PERSONAS)  # one call per persona, not 16
    assert reactions == []


def test_cancel_stops_the_run():
    stop = asyncio.Event()
    seen = []

    def on_reaction(r):
        seen.append(r)
        stop.set()

    status, _ = asyncio.run(run_simulation(
        submission=submission(), personas=PERSONAS, backend=Recorder(),
        on_reaction=on_reaction, stop=stop, max_retries=0))
    assert status == "cancelled"
    assert len(seen) < 4 * len(TEXTS)


# ---- demo backend ------------------------------------------------------------
def test_demo_backend_outputs_validate_with_verbatim_evidence():
    (status, _), reactions = run(DemoBackend())
    assert status == "completed"
    assert all(r.status == "ok" and r.evidence_verified for r in reactions)
    by_id = {s["id"]: s["text"] for s in make_segments()}
    for r in reactions:
        assert r.evidence in by_id[r.segment_id]
        assert "Demo heuristic" in r.reason


def test_demo_personas_do_not_all_agree():
    long_slow = ("The room was large and old and full of dusty furniture that nobody had used in years, "
                 "and the walls were covered in a faded paper whose pattern had long since lost its meaning "
                 "to the slow patient work of the afternoon sun, which crept across the floor. ") * 2
    punchy = '"Run!" she screamed. "Why would you do that?" He grinned. The door slammed.'
    segs = [Segment(id=1, label="P1", text=long_slow, char_start=0, char_end=len(long_slow)),
            Segment(id=2, label="P2", text=punchy, char_start=0, char_end=len(punchy))]
    scores = {}
    for p in PERSONAS:
        for s in segs:
            req = ReactionRequest(persona=p, title="t", content_type="story", seen=(), current=s)
            scores[(p.key, s.id)] = asyncio.run(DemoBackend().react(req))["engagement_score"]
    # Doomscroller should clearly prefer the punchy segment over the slow one
    assert scores[("doom", 2)] - scores[("doom", 1)] >= 3
    assert len({v for v in scores.values()}) > 2
