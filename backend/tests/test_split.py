from app.analysis.split import SPLIT_GAP, build_split
from app.analysis.stats import analyse

from .test_analysis import SEGS, full


def _split(scores, n=None):
    segs = SEGS[: n or len(scores)]
    return analyse("x", "completed", segs, full(scores), total_steps=4 * len(segs)).split


def test_headline_names_who_it_appeals_to_and_who_it_loses():
    s = _split({1: {"doom": (2, False), "critic": (5, True), "fan": (9, True), "newbie": (3, True)}})
    seg = s.segments[0]
    assert seg.gap == 7
    assert "genre enthusiasts" in seg.headline and "fast-scrolling readers" in seg.headline and "casual readers" in seg.headline
    assert [r.persona for r in seg.appeals_to] == ["fan"] and {r.persona for r in seg.loses} == {"doom", "newbie"}
    # the middle reader (critic, 5) is in neither group: only clear responders are named
    assert "critic" not in {r.persona for r in seg.appeals_to + seg.loses}


def test_explanation_quotes_recorded_reasons_only():
    seg = _split({1: {"doom": (2, False), "critic": (5, True), "fan": (9, True), "newbie": (5, True)}}).segments[0]
    assert "reason doom 1" in seg.why and "reason fan 1" in seg.why and "2/10" in seg.why and "9/10" in seg.why


def test_small_gaps_are_not_splits():
    s = _split({1: {"doom": (5, True), "critic": (6, True), "fan": (7, True), "newbie": (5, True)}})
    assert SPLIT_GAP == 3 and s.segments == []


def test_split_is_broader_than_a_collision():
    # a 3-point gap is a split, but not a collision (those need 4, or 3 plus a stop/continue disagreement)
    rs = {1: {"doom": (4, True), "critic": (5, True), "fan": (7, True), "newbie": (5, True)}}
    a = analyse("x", "completed", SEGS[:1], full(rs), 4)
    assert len(a.split.segments) == 1 and a.collisions == []


def test_work_level_fit_ranks_audiences():
    s = _split({
        1: {"doom": (2, False), "critic": (5, True), "fan": (9, True), "newbie": (4, True)},
        2: {"doom": (3, False), "critic": (5, True), "fan": (8, True), "newbie": (4, True)},
    })
    assert [f.persona for f in s.fit] == ["fan", "critic", "newbie", "doom"] and s.fit[0].rank == 1
    assert "best with genre enthusiasts" in s.work_note and "weakest with fast-scrolling readers" in s.work_note


def test_agreeing_panel_gets_no_audience_favourite():
    s = _split({1: {"doom": (6, True), "critic": (6, True), "fan": (7, True), "newbie": (6, True)}})
    assert "similar levels" in s.work_note


def test_most_common_divide_is_counted():
    s = _split({i: {"doom": (2, False), "critic": (5, True), "fan": (9, True), "newbie": (5, True)} for i in (1, 2, 3)})
    assert s.divides[0].high == "The Genre Superfan" and s.divides[0].low == "The Doomscroller" and s.divides[0].count == 3


def test_empty_run():
    assert build_split(SEGS[:2], []).segments == []
