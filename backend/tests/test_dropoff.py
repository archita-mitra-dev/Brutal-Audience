from app.analysis.dropoff import sentence_containing
from app.analysis.stats import analyse
from app.schemas import ReactionOut
from app.personas.definitions import PERSONAS_BY_KEY

from .test_analysis import SEGS, full

TEXT = 'It was quiet. "Don\'t go up there," he said. Suddenly, her heart pounded! Then nothing.'


def test_sentence_containing_finds_the_whole_sentence():
    assert sentence_containing(TEXT, "heart pounded") == "Suddenly, her heart pounded!"
    assert sentence_containing(TEXT, "it was quiet") == "It was quiet."
    assert sentence_containing(TEXT, "Then nothing") == "Then nothing."


def test_sentence_containing_never_guesses():
    assert sentence_containing(TEXT, "not in the text") is None
    assert sentence_containing(TEXT, None) is None and sentence_containing(TEXT, "  ") is None


def _a(scores, n=3):
    return analyse("x", "completed", SEGS[:n], full(scores), total_steps=4 * n).dropoff


S = {
    1: {"doom": (5, True), "critic": (5, True), "fan": (5, True), "newbie": (5, True)},
    2: {"doom": (2, False), "critic": (5, True), "fan": (6, True), "newbie": (5, True)},
    3: {"doom": (1, False), "critic": (2, False), "fan": (6, True), "newbie": (5, True)},
}


def test_states_continue_drop_off_already_left():
    d = _a(S)
    st = {r.segment_id: r.states for r in d.rows}
    assert st[1]["doom"] == "continue"
    assert st[2]["doom"] == "drop_off" and st[2]["critic"] == "continue"
    assert st[3]["doom"] == "already_left" and st[3]["critic"] == "drop_off"
    assert all(st[i]["fan"] == "continue" for i in (1, 2, 3))


def test_retention_curve_counts_readers_still_going():
    d = _a(S)
    assert [(c.segment_id, c.still_reading, c.pct) for c in d.curve] == [
        (0, 4, 100.0), (1, 4, 100.0), (2, 3, 75.0), (3, 2, 50.0)]
    assert d.steepest_segment_id == 2 or d.steepest_segment_id == 3   # one reader lost at each
    assert set(d.reached_end) == {"The Genre Superfan", "The Casual Newcomer"}


def test_trigger_uses_the_personas_own_quote():
    rs = full(S)
    rs = [r.model_copy(update={"evidence": "text 2"}) if (r.persona, r.segment_id) == ("doom", 2) else r for r in rs]
    segs = [{"id": 1, "label": "Paragraph 1", "text": "text 1"}, {"id": 2, "label": "Paragraph 2", "text": "Intro. text 2 is here. End."},
            {"id": 3, "label": "Paragraph 3", "text": "text 3"}]
    d = analyse("x", "completed", segs, rs, 12).dropoff
    t = next(t for t in d.triggers if t.persona == "doom")
    assert t.segment_id == 2 and t.sentence == "text 2 is here."


def test_no_drop_offs_means_flat_curve_and_no_triggers():
    d = _a({1: {"doom": (7, True), "critic": (7, True), "fan": (7, True), "newbie": (7, True)}}, n=1)
    assert d.triggers == [] and d.curve[-1].pct == 100.0 and d.steepest_segment_id is None


def test_failed_reactions_are_unread_not_drop_offs():
    rs = [ReactionOut(persona="doom", persona_name=PERSONAS_BY_KEY["doom"].name, segment_id=1, status="failed", error="x"),
          *full({1: {"critic": (5, True)}})]
    d = analyse("x", "completed", SEGS[:1], rs, 4).dropoff
    assert d.reader_count == 1 and "doom" not in d.rows[0].states
