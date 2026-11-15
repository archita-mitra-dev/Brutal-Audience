"""Turns raw persona reactions into the numbers the dashboard shows.

Everything here is plain, deterministic arithmetic over the stored reactions.
No model is involved, so the heatmap, drop-offs and collisions can always be
traced back to specific recorded reactions.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ..personas.definitions import PERSONAS, PERSONAS_BY_KEY
from ..schemas import ReactionOut
from .dropoff import build_dropoff
from .meter import build_meter
from .split import build_split
from .models import (
    Agreement, Analysis, Collision, DropOff, Participant, PersonaStat, SegmentStat,
)

# Thresholds (kept as constants so they are easy to tune and to test).
COLLISION_GAP = 4          # personas differ by 4+ points on the same segment
SPLIT_GAP = 3              # ...or 3+ points while some would continue and some would stop
LOW_SCORE = 3              # "lost interest"
AGREE_HIGH = 7
AGREE_LOW = 3
AGREE_SPREAD = 1
MAX_COLLISIONS = 10

# What each persona rewards. Used only to phrase why two opposite reactions can both be fair.
LENS = {
    "doom": "momentum and an immediate payoff",
    "critic": "originality and logic that holds together",
    "fan": "genre craft and texture",
    "newbie": "being clear to someone arriving cold",
}


def _first(s: str | None) -> str:
    s = (s or "").strip()
    return s[:-1] if s.endswith(".") else s


def _participant(r: ReactionOut) -> Participant:
    return Participant(
        persona=r.persona, persona_name=r.persona_name, score=r.engagement_score or 0,
        emotion=r.emotion, inner_thought=r.inner_thought, reason=r.reason,
        evidence=r.evidence, would_continue=r.would_continue,
    )


def explain_collision(high: Participant, low: Participant) -> str:
    """Why both reactions are reasonable, from the personas' own recorded reasons."""
    return (
        f"{high.persona_name} scored this {high.score}/10: {_first(high.reason)}. "
        f"{low.persona_name} scored it {low.score}/10: {_first(low.reason)}. "
        f"They are reading for different things ({LENS.get(high.persona, 'their own taste')} versus "
        f"{LENS.get(low.persona, 'their own taste')}), so both reactions are fair. "
        "This is a trade-off about who the passage is for, not necessarily a flaw to remove."
    )


def analyse(
    run_id: str, status: str, segments: list[dict], reactions: Iterable[ReactionOut],
    total_steps: int,
) -> Analysis:
    reactions = list(reactions)
    ok = [r for r in reactions if r.status == "ok" and r.engagement_score is not None]
    seg_label = {s["id"]: s["label"] for s in segments}
    by_seg: dict[int, list[ReactionOut]] = defaultdict(list)
    for r in ok:
        by_seg[r.segment_id].append(r)

    # --- per segment ---------------------------------------------------------
    seg_stats: list[SegmentStat] = []
    for s in segments:
        rs = by_seg.get(s["id"], [])
        scores = [r.engagement_score for r in rs]  # type: ignore[misc]
        seg_stats.append(SegmentStat(
            segment_id=s["id"], label=s["label"], read_by=len(rs),
            mean=round(sum(scores) / len(scores), 2) if scores else None,
            min=min(scores) if scores else None,
            max=max(scores) if scores else None,
            spread=(max(scores) - min(scores)) if scores else None,
            scores={r.persona: r.engagement_score for r in rs},  # type: ignore[misc]
            stopped=[r.persona for r in rs if r.would_continue is False],
        ))

    # --- per persona ---------------------------------------------------------
    persona_stats: list[PersonaStat] = []
    first_stop: dict[str, int] = {}
    for p in PERSONAS:
        mine = [r for r in reactions if r.persona == p.key]
        mine_ok = [r for r in mine if r in ok]
        stops = sorted(r.segment_id for r in mine_ok if r.would_continue is False)
        if stops:
            first_stop[p.key] = stops[0]
        persona_stats.append(PersonaStat(
            persona=p.key, persona_name=p.name,
            avg=round(sum(r.engagement_score for r in mine_ok) / len(mine_ok), 2) if mine_ok else None,  # type: ignore[misc]
            n_ok=len(mine_ok), n_failed=len(mine) - len(mine_ok),
            first_stop_segment=stops[0] if stops else None,
        ))

    # --- drop-off points: the first segment where each persona would stop -----
    grouped: dict[int, list[str]] = defaultdict(list)
    for key, seg_id in first_stop.items():
        grouped[seg_id].append(key)
    drop_offs = [
        DropOff(
            segment_id=seg_id, label=seg_label.get(seg_id, f"Segment {seg_id}"), personas=keys,
            persona_names=[PERSONAS_BY_KEY[k].name for k in keys], consensus=len(keys) >= 2,
        )
        for seg_id, keys in sorted(grouped.items())
    ]

    # --- segments where several personas lost interest ------------------------
    lost = [
        st.segment_id for st in seg_stats
        if len(st.stopped) >= 2 or sum(1 for v in st.scores.values() if v <= LOW_SCORE) >= 2
    ]

    # --- strongest / weakest: only segments seen by 2+ personas when possible --
    rated = [st for st in seg_stats if st.mean is not None]
    pool = [st for st in rated if st.read_by >= 2] or rated
    strongest = max(pool, key=lambda st: (st.mean, -st.segment_id)) if pool else None  # type: ignore[arg-type,return-value]
    weakest = min(pool, key=lambda st: (st.mean, st.segment_id)) if pool else None  # type: ignore[arg-type,return-value]

    # --- audience collisions ---------------------------------------------------
    collisions: list[Collision] = []
    for st in seg_stats:
        rs = by_seg.get(st.segment_id, [])
        if len(rs) < 2 or st.spread is None:
            continue
        ranked = sorted(rs, key=lambda r: (r.engagement_score, r.persona))  # type: ignore[arg-type,return-value]
        low, high = ranked[0], ranked[-1]
        split = any(r.would_continue for r in rs) and any(r.would_continue is False for r in rs)
        if st.spread >= COLLISION_GAP:
            kind = "score_gap"
        elif split and st.spread >= SPLIT_GAP:
            kind = "continue_split"
        else:
            continue
        hp, lp = _participant(high), _participant(low)
        collisions.append(Collision(
            segment_id=st.segment_id, label=st.label, kind=kind, spread=st.spread,
            high=hp, low=lp,
            others=[_participant(r) for r in rs if r is not high and r is not low],
            explanation=explain_collision(hp, lp),
        ))
    collisions.sort(key=lambda c: (-c.spread, c.segment_id))
    collisions = collisions[:MAX_COLLISIONS]

    # --- agreement: everyone within 1 point, all high or all low ---------------
    agreements: list[Agreement] = []
    for st in seg_stats:
        if st.read_by < 3 or st.spread is None or st.mean is None or st.spread > AGREE_SPREAD:
            continue
        if st.mean >= AGREE_HIGH:
            agreements.append(Agreement(segment_id=st.segment_id, label=st.label, kind="shared_high", mean=st.mean))
        elif st.mean <= AGREE_LOW:
            agreements.append(Agreement(segment_id=st.segment_id, label=st.label, kind="shared_low", mean=st.mean))

    all_scores = [r.engagement_score for r in ok]
    overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else None  # type: ignore[arg-type]
    # Personas who read everything they were given without once wanting to stop.
    never_stopped = [
        ps.persona for ps in persona_stats
        if ps.n_ok > 0 and ps.first_stop_segment is None
    ]
    return Analysis(
        run_id=run_id, status=status,
        partial=status != "completed" or len(reactions) < total_steps,
        overall_mean=overall,
        strongest_segment_id=strongest.segment_id if strongest else None,
        weakest_segment_id=weakest.segment_id if weakest else None,
        segments=seg_stats, personas=persona_stats, drop_offs=drop_offs,
        lost_attention=lost, collisions=collisions, agreements=agreements,
        meter=build_meter(seg_stats, overall, never_stopped, LOW_SCORE),
        dropoff=build_dropoff(segments, ok),
        split=build_split(segments, ok),
    )
