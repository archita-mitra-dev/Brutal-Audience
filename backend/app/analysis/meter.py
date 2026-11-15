"""The Brutality Meter: a plain-rules classification of every segment and of the whole work.

No model is involved. Every label comes from the thresholds below, applied to the stored
reactions, and each result carries a `rule` sentence that shows the numbers behind it, so the
creator can see exactly why a segment was rated the way it was.

Segment levels, checked in this order (first match wins):

  multi_stop  2+ readers would stop here, or 2+ scored it <= LOW_SCORE
  declining   panel average < CURIOUS_MEAN, or exactly 1 reader would stop here
  strong      panel average >= STRONG_MEAN (and, by the rules above, nobody would stop)
  curious     everything else: CURIOUS_MEAN <= average < STRONG_MEAN, nobody would stop

Document levels, from the share of rated segments in each level:

  brutal   multi_stop segments >= BRUTAL_MULTI_SHARE of all segments, or panel average < BRUTAL_MEAN
  shaky    weak segments (multi_stop + declining) >= SHAKY_WEAK_SHARE, or panel average < SHAKY_MEAN
  holds    weak segments <= HOLDS_WEAK_SHARE and panel average >= STRONG_MEAN
  mixed    everything else
"""
from __future__ import annotations

from ..personas.definitions import PERSONAS, PERSONAS_BY_KEY
from .models import DocumentMeter, Meter, SegmentMeter, SegmentStat

STRONG_MEAN = 7.0
CURIOUS_MEAN = 5.0
MULTI_STOP_READERS = 2

BRUTAL_MULTI_SHARE = 0.25
BRUTAL_MEAN = 4.0
SHAKY_WEAK_SHARE = 0.40
SHAKY_MEAN = 5.5
HOLDS_WEAK_SHARE = 0.15

SEGMENT_NAMES = {
    "strong": "Strong engagement",
    "curious": "Audience wants to know more",
    "declining": "Engagement is declining",
    "multi_stop": "Multiple personas would stop reading",
}
DOCUMENT_NAMES = {
    "holds": "Holds the room",
    "mixed": "Mostly holds, with weak spots",
    "shaky": "Shaky: it loses people in places",
    "brutal": "Brutal: the room empties",
}


def thresholds(low_score: int) -> dict[str, float]:
    """Published with every analysis so the UI can show the rules, not just the results."""
    return {
        "strong_mean": STRONG_MEAN,
        "curious_mean": CURIOUS_MEAN,
        "multi_stop_readers": MULTI_STOP_READERS,
        "low_score": low_score,
        "brutal_multi_share": BRUTAL_MULTI_SHARE,
        "brutal_mean": BRUTAL_MEAN,
        "shaky_weak_share": SHAKY_WEAK_SHARE,
        "shaky_mean": SHAKY_MEAN,
        "holds_weak_share": HOLDS_WEAK_SHARE,
    }


def _names(keys: list[str]) -> str:
    return ", ".join(PERSONAS_BY_KEY[k].name.replace("The ", "") for k in keys)


def classify_segment(st: SegmentStat, low_score: int) -> SegmentMeter | None:
    if st.mean is None or st.read_by == 0:
        return None
    low = [k for k, v in st.scores.items() if v <= low_score]
    stopped = st.stopped
    if len(stopped) >= MULTI_STOP_READERS or len(low) >= MULTI_STOP_READERS:
        who = stopped if len(stopped) >= MULTI_STOP_READERS else low
        verb = "would stop reading" if len(stopped) >= MULTI_STOP_READERS else f"scored it {low_score} or lower"
        level, rule = "multi_stop", f"{len(who)} of {st.read_by} readers {verb} ({_names(who)})."
    elif st.mean < CURIOUS_MEAN or len(stopped) == 1:
        level = "declining"
        if len(stopped) == 1:
            rule = f"{_names(stopped)} would stop here; panel average {st.mean:.1f}."
        else:
            rule = f"Panel average {st.mean:.1f} is below {CURIOUS_MEAN:g}."
    elif st.mean >= STRONG_MEAN:
        level, rule = "strong", f"Panel average {st.mean:.1f} is {STRONG_MEAN:g} or more and nobody would stop."
    else:
        level = "curious"
        rule = f"Panel average {st.mean:.1f} (between {CURIOUS_MEAN:g} and {STRONG_MEAN:g}) and nobody would stop."
    return SegmentMeter(
        segment_id=st.segment_id, label=st.label, level=level,  # type: ignore[arg-type]
        name=SEGMENT_NAMES[level], rule=rule, mean=st.mean,
    )


def build_meter(
    seg_stats: list[SegmentStat], overall_mean: float | None, never_stopped: list[str], low_score: int,
) -> Meter:
    rows = [m for m in (classify_segment(st, low_score) for st in seg_stats) if m]
    if not rows or overall_mean is None:
        return Meter(segments=rows, document=None, thresholds=thresholds(low_score))

    counts = {k: 0 for k in SEGMENT_NAMES}
    for m in rows:
        counts[m.level] += 1
    n = len(rows)
    multi_share = counts["multi_stop"] / n
    weak_share = (counts["multi_stop"] + counts["declining"]) / n

    if multi_share >= BRUTAL_MULTI_SHARE or overall_mean < BRUTAL_MEAN:
        level = "brutal"
        rule = (f"Multiple readers would stop in {counts['multi_stop']} of {n} segments "
                f"({multi_share:.0%}) with a panel average of {overall_mean:.1f}.")
    elif weak_share >= SHAKY_WEAK_SHARE or overall_mean < SHAKY_MEAN:
        level = "shaky"
        rule = (f"{counts['multi_stop'] + counts['declining']} of {n} segments are declining or worse "
                f"({weak_share:.0%}); panel average {overall_mean:.1f}.")
    elif weak_share <= HOLDS_WEAK_SHARE and overall_mean >= STRONG_MEAN:
        level = "holds"
        rule = f"Only {weak_share:.0%} of segments are declining or worse; panel average {overall_mean:.1f}."
    else:
        level = "mixed"
        rule = f"{weak_share:.0%} of segments are declining or worse; panel average {overall_mean:.1f}."

    return Meter(
        segments=rows,
        document=DocumentMeter(
            level=level, name=DOCUMENT_NAMES[level], rule=rule, counts=counts,  # type: ignore[arg-type]
            never_stopped=[PERSONAS_BY_KEY[k].name for k in never_stopped],
            persona_count=len(PERSONAS),
        ),
        thresholds=thresholds(low_score),
    )
