"""Audience Split Detector: goes beyond the average to say WHO a passage works for and who it loses.

Deterministic. For every segment where readers differ by SPLIT_GAP+ points it names the readers
who responded strongly and the ones who did not, and explains the divide using the low-scoring
reader's own recorded reason (quoted, never invented). It also summarises the whole work: how well
it fits each audience, and which pair of readers diverged most often.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from ..personas.definitions import PERSONAS, PERSONAS_BY_KEY
from ..schemas import ReactionOut
from .models import DividePair, PersonaFit, SplitReader, SplitReport, SplitSegment

SPLIT_GAP = 3        # readers differ by this many points or more on one segment
FIT_GAP = 2.0        # whole-work averages differ by this much between audiences

AUDIENCE = {
    "doom": "fast-scrolling readers",
    "critic": "sceptical readers",
    "fan": "genre enthusiasts",
    "newbie": "casual readers",
}


def _first(s: str | None) -> str:
    s = (s or "").strip()
    return s[:-1] if s.endswith(".") else s


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _reader(r: ReactionOut) -> SplitReader:
    return SplitReader(persona=r.persona, persona_name=r.persona_name, audience=AUDIENCE[r.persona],
                       score=r.engagement_score or 0, reason=r.reason)


def build_split(segments: list[dict], ok: list[ReactionOut]) -> SplitReport:
    by_seg: dict[int, list[ReactionOut]] = defaultdict(list)
    for r in ok:
        by_seg[r.segment_id].append(r)
    label = {s["id"]: s["label"] for s in segments}

    found: list[SplitSegment] = []
    pairs: Counter[tuple[str, str]] = Counter()
    for s in segments:
        rs = sorted(by_seg.get(s["id"], []), key=lambda r: (-(r.engagement_score or 0), r.persona))
        if len(rs) < 2:
            continue
        hi, lo = rs[0].engagement_score or 0, rs[-1].engagement_score or 0
        gap = hi - lo
        if gap < SPLIT_GAP:
            continue
        appeals = [r for r in rs if (r.engagement_score or 0) >= hi - 1]
        loses = [r for r in rs if (r.engagement_score or 0) <= lo + 1]
        weakest = loses[-1]
        a_names = _join([AUDIENCE[r.persona] for r in appeals])
        l_names = _join([AUDIENCE[r.persona] for r in loses])
        headline = f"This section may appeal strongly to {a_names} but lose {l_names}."
        why = (f"{weakest.persona_name} scored it {weakest.engagement_score}/10: {_first(weakest.reason)}. "
               f"{appeals[0].persona_name} scored it {appeals[0].engagement_score}/10: {_first(appeals[0].reason)}. "
               "A split like this usually means the passage is written for one kind of reader, "
               "so decide who it is for before treating the weaker score as a flaw.")
        found.append(SplitSegment(
            segment_id=s["id"], label=s["label"], gap=gap, headline=headline, why=why,
            appeals_to=[_reader(r) for r in appeals], loses=[_reader(r) for r in loses],
        ))
        pairs[(appeals[0].persona, weakest.persona)] += 1
    found.sort(key=lambda x: (-x.gap, x.segment_id))

    # Whole-work fit per audience.
    avgs = []
    for p in PERSONAS:
        sc = [r.engagement_score for r in ok if r.persona == p.key and r.engagement_score is not None]
        if sc:
            avgs.append((p, sum(sc) / len(sc)))
    avgs.sort(key=lambda t: -t[1])
    fit = [PersonaFit(persona=p.key, persona_name=p.name, audience=AUDIENCE[p.key], avg=round(a, 2), rank=i + 1)
           for i, (p, a) in enumerate(avgs)]

    if len(avgs) >= 2 and avgs[0][1] - avgs[-1][1] >= FIT_GAP:
        best, worst = avgs[0], avgs[-1]
        note = (f"The work lands differently by audience: best with {AUDIENCE[best[0].key]} "
                f"(average {best[1]:.1f}/10) and weakest with {AUDIENCE[worst[0].key]} "
                f"(average {worst[1]:.1f}/10). A single panel average would hide that.")
    elif avgs:
        note = "The four readers responded at similar levels overall, so the work does not favour one audience."
    else:
        note = "There are no rated reactions to compare yet."

    divides = [DividePair(high=PERSONAS_BY_KEY[h].name, low=PERSONAS_BY_KEY[l].name, count=c)
               for (h, l), c in pairs.most_common(3)]
    return SplitReport(segments=found, fit=fit, work_note=note, divides=divides,
                       thresholds={"split_gap": SPLIT_GAP, "fit_gap": FIT_GAP})
