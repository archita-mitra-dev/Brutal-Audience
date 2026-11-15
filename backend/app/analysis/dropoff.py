"""Drop-off prediction: where each simulated reader would stop, the retention curve, and the
sentence that most plausibly triggered each exit.

Deterministic, like the rest of the analysis. A "drop-off" is a persona's FIRST segment with
would_continue = false. The trigger sentence is the sentence of that segment that contains the
persona's own verbatim evidence quote. If the persona gave no verifiable quote, no trigger is
shown: it is never guessed.

These are simulated reactions, so everything here is a *predicted* drop-off, not a measurement.
"""
from __future__ import annotations

import re

from ..personas.definitions import PERSONAS
from ..schemas import ReactionOut
from .models import CurvePoint, DropoffPrediction, DropoffRow, Trigger

_BOUNDARY = re.compile(r"(?<=[.!?…])[\"')\]”’]*\s+")


def sentence_containing(text: str, quote: str | None) -> str | None:
    """The full sentence of `text` that contains `quote` (case-insensitive), else None."""
    if not quote or not quote.strip():
        return None
    idx = text.lower().find(quote.strip().lower())
    if idx < 0:
        return None
    start = 0
    for m in _BOUNDARY.finditer(text):
        if m.end() <= idx:
            start = m.end()
        else:
            end = m.start() + len(m.group(0).rstrip())
            return text[start:end].strip() or None
    return text[start:].strip() or None


def build_dropoff(segments: list[dict], ok: list[ReactionOut]) -> DropoffPrediction:
    seg_ids = [s["id"] for s in segments]
    label = {s["id"]: s["label"] for s in segments}
    text = {s["id"]: s["text"] for s in segments}
    by: dict[tuple[str, int], ReactionOut] = {(r.persona, r.segment_id): r for r in ok}
    readers = [p for p in PERSONAS if any(r.persona == p.key for r in ok)]

    first_stop: dict[str, int] = {}
    for p in readers:
        stops = sorted(r.segment_id for r in ok if r.persona == p.key and r.would_continue is False)
        if stops:
            first_stop[p.key] = stops[0]

    # table: continue / drop_off / already_left / unread
    rows: list[DropoffRow] = []
    for sid in seg_ids:
        states: dict[str, str] = {}
        for p in readers:
            fs = first_stop.get(p.key)
            if (p.key, sid) not in by:
                states[p.key] = "unread"
            elif fs is None or sid < fs:
                states[p.key] = "continue"
            elif sid == fs:
                states[p.key] = "drop_off"
            else:
                states[p.key] = "already_left"
        rows.append(DropoffRow(segment_id=sid, label=label[sid], states=states))

    # retention curve: share of readers still going once they have finished each segment
    total = len(readers)
    curve: list[CurvePoint] = []
    steepest: int | None = None
    if total:
        curve.append(CurvePoint(segment_id=0, label="Start", still_reading=total, pct=100.0))
        prev, worst = total, 0
        for sid in seg_ids:
            if not any(r.segment_id == sid for r in ok):
                continue
            still = sum(1 for p in readers if first_stop.get(p.key) is None or first_stop[p.key] > sid)
            curve.append(CurvePoint(segment_id=sid, label=label[sid], still_reading=still,
                                    pct=round(100 * still / total, 1)))
            if prev - still > worst:
                worst, steepest = prev - still, sid
            prev = still

    triggers: list[Trigger] = []
    for p in readers:
        sid = first_stop.get(p.key)
        if sid is None:
            continue
        r = by[(p.key, sid)]
        triggers.append(Trigger(
            persona=p.key, persona_name=p.name, segment_id=sid, label=label[sid],
            sentence=sentence_containing(text[sid], r.evidence), score=r.engagement_score or 0,
            inner_thought=r.inner_thought, reason=r.reason,
        ))
    triggers.sort(key=lambda t: (t.segment_id, t.persona))

    return DropoffPrediction(
        reader_count=total, rows=rows, curve=curve, triggers=triggers,
        steepest_segment_id=steepest,
        reached_end=[p.name for p in readers if p.key not in first_stop],
    )
