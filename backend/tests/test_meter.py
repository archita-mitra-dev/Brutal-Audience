"""Brutality Meter: every label must follow from the published thresholds."""
from app.analysis.meter import (
    CURIOUS_MEAN, STRONG_MEAN, build_meter, classify_segment,
)
from app.analysis.models import SegmentStat
from app.analysis.stats import LOW_SCORE, analyse

from .test_analysis import SEGS, full


def stat(scores: dict, stopped=(), sid=1):
    vals = list(scores.values())
    return SegmentStat(
        segment_id=sid, label=f"Paragraph {sid}", read_by=len(vals),
        mean=round(sum(vals) / len(vals), 2) if vals else None,
        min=min(vals) if vals else None, max=max(vals) if vals else None,
        spread=(max(vals) - min(vals)) if vals else None, scores=scores, stopped=list(stopped),
    )


def level(st):
    return classify_segment(st, LOW_SCORE).level


def test_strong_needs_high_mean_and_nobody_stopping():
    assert level(stat({"doom": 8, "critic": 7, "fan": 8, "newbie": 7})) == "strong"
    # same mean, but one reader would stop -> not strong
    assert level(stat({"doom": 8, "critic": 7, "fan": 8, "newbie": 7}, stopped=["newbie"])) == "declining"


def test_curious_band_is_between_the_two_means():
    st = stat({"doom": 6, "critic": 6, "fan": 6, "newbie": 5})
    assert CURIOUS_MEAN <= st.mean < STRONG_MEAN and level(st) == "curious"


def test_low_mean_is_declining():
    assert level(stat({"doom": 4, "critic": 5, "fan": 4, "newbie": 4})) == "declining"


def test_two_stoppers_or_two_low_scores_is_multi_stop():
    assert level(stat({"doom": 5, "critic": 5, "fan": 8, "newbie": 5}, stopped=["doom", "critic"])) == "multi_stop"
    assert level(stat({"doom": 2, "critic": 3, "fan": 9, "newbie": 8})) == "multi_stop"   # two <= LOW_SCORE


def test_multi_stop_outranks_everything_else():
    # high mean, but two readers stop: the stoppers win
    st = stat({"doom": 9, "critic": 9, "fan": 9, "newbie": 9}, stopped=["doom", "fan"])
    assert level(st) == "multi_stop"


def test_unrated_segment_is_skipped():
    assert classify_segment(stat({}), LOW_SCORE) is None


def test_rule_text_shows_the_numbers():
    m = classify_segment(stat({"doom": 5, "critic": 5, "fan": 8, "newbie": 5}, stopped=["doom", "critic"]), LOW_SCORE)
    assert "2 of 4" in m.rule and "Doomscroller" in m.rule and "Skeptical Critic" in m.rule


def _doc(levels_scores, overall):
    sts = [stat(sc, stopped=stop, sid=i) for i, (sc, stop) in enumerate(levels_scores, start=1)]
    return build_meter(sts, overall, never_stopped=[], low_score=LOW_SCORE).document


GOOD = ({"doom": 8, "critic": 8, "fan": 8, "newbie": 8}, [])
OK = ({"doom": 6, "critic": 6, "fan": 6, "newbie": 6}, [])
BAD = ({"doom": 4, "critic": 4, "fan": 4, "newbie": 4}, [])
GONE = ({"doom": 2, "critic": 2, "fan": 6, "newbie": 6}, ["doom", "critic"])


def test_document_levels():
    assert _doc([GOOD] * 9 + [OK], 7.6).level == "holds"
    assert _doc([GOOD, OK, OK, OK, OK], 6.4).level == "mixed"
    assert _doc([GOOD, BAD, BAD, OK, OK], 5.2).level == "shaky"            # 40% weak
    assert _doc([GOOD, GONE, GONE, OK], 5.0).level == "brutal"             # 50% multi-stop
    assert _doc([OK, OK], 3.9).level == "brutal"                           # mean alone


def test_document_counts_and_never_stopped():
    sts = [stat(GOOD[0], sid=1), stat(GONE[0], GONE[1], sid=2)]
    m = build_meter(sts, 6.0, ["newbie"], LOW_SCORE)
    assert m.document.counts == {"strong": 1, "curious": 0, "declining": 0, "multi_stop": 1}
    assert m.document.never_stopped == ["The Casual Newcomer"]


def test_thresholds_are_published():
    m = build_meter([stat(GOOD[0])], 8.0, [], LOW_SCORE)
    assert m.thresholds["strong_mean"] == STRONG_MEAN and m.thresholds["low_score"] == LOW_SCORE


def test_analysis_carries_the_meter_end_to_end():
    rs = full({
        1: {"doom": (8, True), "critic": (7, True), "fan": (8, True), "newbie": (7, True)},
        2: {"doom": (2, False), "critic": (3, False), "fan": (6, True), "newbie": (5, True)},
    })
    a = analyse("x", "completed", SEGS[:2], rs, total_steps=8)
    by = {m.segment_id: m.level for m in a.meter.segments}
    assert by == {1: "strong", 2: "multi_stop"}
    assert a.meter.document is not None
    # fan and newbie read to the end without wanting to stop
    assert set(a.meter.document.never_stopped) == {"The Genre Superfan", "The Casual Newcomer"}


def test_empty_analysis_has_no_document_verdict():
    a = analyse("x", "running", SEGS[:2], [], total_steps=8)
    assert a.meter.segments == [] and a.meter.document is None
