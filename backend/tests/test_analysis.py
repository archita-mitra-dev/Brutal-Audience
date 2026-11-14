from app.analysis.stats import analyse, explain_collision
from app.personas.definitions import PERSONAS_BY_KEY
from app.schemas import ReactionOut

SEGS = [{"id": i, "label": f"Paragraph {i}", "text": f"text {i}"} for i in range(1, 5)]


def r(persona, seg, score, cont=True, status="ok"):
    if status == "failed":
        return ReactionOut(persona=persona, persona_name=PERSONAS_BY_KEY[persona].name, segment_id=seg,
                           status="failed", error="boom")
    return ReactionOut(persona=persona, persona_name=PERSONAS_BY_KEY[persona].name, segment_id=seg,
                       status="ok", engagement_score=score, emotion="curious", inner_thought="hm",
                       would_continue=cont, evidence=f"text {seg}", evidence_verified=True,
                       reason=f"reason {persona} {seg}.")


def full(scores):  # scores[seg_id] = {persona: (score, continue)}
    out = []
    for seg, d in scores.items():
        for p, (s, c) in d.items():
            out.append(r(p, seg, s, c))
    return out


def test_collision_found_and_explained():
    rs = full({
        1: {"doom": (8, True), "critic": (7, True), "fan": (8, True), "newbie": (7, True)},
        2: {"doom": (2, False), "critic": (5, True), "fan": (9, True), "newbie": (5, True)},
    })
    a = analyse("x", "completed", SEGS[:2], rs, total_steps=8)
    assert [c.segment_id for c in a.collisions] == [2]
    c = a.collisions[0]
    assert c.high.persona == "fan" and c.low.persona == "doom" and c.spread == 7
    assert "9/10" in c.explanation and "2/10" in c.explanation and "trade-off" in c.explanation
    assert {o.persona for o in c.others} == {"critic", "newbie"}


def test_small_gap_is_not_a_collision_but_continue_split_is():
    rs = full({1: {"doom": (4, True), "critic": (6, True), "fan": (7, True), "newbie": (5, True)}})
    assert analyse("x", "completed", SEGS[:1], rs, 4).collisions == []
    rs = full({1: {"doom": (3, False), "critic": (6, True), "fan": (6, True), "newbie": (5, True)}})
    c = analyse("x", "completed", SEGS[:1], rs, 4).collisions
    assert len(c) == 1 and c[0].kind == "continue_split"


def test_drop_offs_group_first_stop_per_persona():
    rs = full({
        1: {"doom": (5, True), "critic": (5, True), "fan": (5, True), "newbie": (5, True)},
        2: {"doom": (2, False), "critic": (3, False), "fan": (6, True), "newbie": (5, True)},
        3: {"doom": (1, False), "critic": (2, False), "fan": (4, False), "newbie": (5, True)},
    })
    a = analyse("x", "completed", SEGS[:3], rs, 12)
    by = {d.segment_id: d for d in a.drop_offs}
    assert set(by[2].personas) == {"doom", "critic"} and by[2].consensus
    assert by[3].personas == ["fan"] and not by[3].consensus   # doom/critic already counted at 2
    assert 2 in a.lost_attention and 3 in a.lost_attention
    assert next(p for p in a.personas if p.persona == "doom").first_stop_segment == 2


def test_strongest_weakest_and_agreement():
    rs = full({
        1: {"doom": (9, True), "critic": (9, True), "fan": (8, True), "newbie": (9, True)},
        2: {"doom": (2, True), "critic": (3, True), "fan": (2, True), "newbie": (3, True)},
        3: {"doom": (5, True), "critic": (5, True), "fan": (5, True), "newbie": (5, True)},
    })
    a = analyse("x", "completed", SEGS[:3], rs, 12)
    assert a.strongest_segment_id == 1 and a.weakest_segment_id == 2
    kinds = {x.segment_id: x.kind for x in a.agreements}
    assert kinds == {1: "shared_high", 2: "shared_low"}
    assert not a.partial and a.overall_mean == round((35 + 10 + 20) / 12, 2)


def test_failed_reactions_are_excluded_and_partial_flagged():
    rs = [r("doom", 1, 8), r("critic", 1, 0, status="failed")]
    a = analyse("x", "running", SEGS[:1], rs, 4)
    assert a.partial and a.segments[0].read_by == 1
    assert next(p for p in a.personas if p.persona == "critic").n_failed == 1
    assert a.collisions == []


def test_empty_run():
    a = analyse("x", "queued", SEGS, [], 16)
    assert a.overall_mean is None and a.strongest_segment_id is None and a.collisions == []
