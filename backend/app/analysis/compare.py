"""The comparison engine shared by the Revision Impact Tracker and What If? experiments.

Takes the analysis of a baseline run and of a revised run and says what changed: which
segments improved or weakened, which readers responded better, whether each earlier drop-off was
resolved, and whether a segment the creator did NOT touch got worse (a side effect of an edit).

Deterministic. Segments are matched between versions by text, because a revision can add, remove
or edit segments, so segment numbers cannot be compared directly.

Scores come from simulated readers and (in live mode) vary from run to run, so small differences
are not reported as improvements: see MEANINGFUL_SEGMENT / MEANINGFUL_PERSONA.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from ..personas.definitions import PERSONAS, PERSONAS_BY_KEY
from .models import Analysis

MEANINGFUL_SEGMENT = 1.0    # a segment must move this many points to count as improved / weakened
MEANINGFUL_PERSONA = 0.5    # same, for one reader's whole-work average
MEANINGFUL_OVERALL = 0.5
EDITED_MIN_SIMILARITY = 0.4  # below this a replaced segment is "new", not an edit of the old one

NOISE_NOTE = (
    "These are simulated readers. Live-model scores can shift a point or so between runs even with "
    "identical text, so treat differences of 1 point or less as noise. A hypothetical result is a "
    "simulation, not a guaranteed improvement."
)

Change = Literal["unchanged", "edited", "new", "removed"]
Status = Literal["improved", "weakened", "unchanged", "new", "removed", "unrated"]


class PersonaScore(BaseModel):
    before: int
    after: int
    delta: int


class SegmentDelta(BaseModel):
    base_segment_id: int | None = None
    rev_segment_id: int | None = None
    base_label: str | None = None
    rev_label: str | None = None
    change: Change
    status: Status
    base_mean: float | None = None
    rev_mean: float | None = None
    delta: float | None = None
    personas: dict[str, PersonaScore] = Field(default_factory=dict)
    collateral: bool = False           # text untouched, yet it got worse


class PersonaDelta(BaseModel):
    persona: str
    persona_name: str
    before: float | None = None
    after: float | None = None
    delta: float | None = None
    status: Literal["improved", "weakened", "unchanged", "unrated"]


class DropoffOutcome(BaseModel):
    persona: str
    persona_name: str
    status: Literal["resolved", "still", "moved", "new"]
    before_label: str | None = None
    after_label: str | None = None
    text: str


class Comparison(BaseModel):
    baseline_run_id: str
    run_id: str
    kind: Literal["revision", "whatif"]
    label: str | None = None
    overall_before: float | None = None
    overall_after: float | None = None
    overall_delta: float | None = None
    verdict: Literal["better", "worse", "mixed", "about_the_same", "unrated"]
    meter_before: str | None = None
    meter_after: str | None = None
    retention_before: float | None = None      # % of readers still going at the end
    retention_after: float | None = None
    improved: int = 0
    weakened: int = 0
    collateral: int = 0
    segments: list[SegmentDelta]
    personas: list[PersonaDelta]
    dropoffs: list[DropoffOutcome]
    highlights: list[str]
    noise_note: str = NOISE_NOTE


# ------------------------------------------------------------------ alignment
def _norm(t: str) -> str:
    return " ".join(t.split())


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a[:2000], b[:2000], autojunk=False).ratio()


def align(base: list[dict], rev: list[dict]) -> list[tuple[int | None, int | None, Change]]:
    """Pair baseline segments with revised ones. Order follows the revised work."""
    bt, rt = [_norm(s["text"]) for s in base], [_norm(s["text"]) for s in rev]
    out: list[tuple[int | None, int | None, Change]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, bt, rt, autojunk=False).get_opcodes():
        if tag == "equal":
            out += [(base[i1 + k]["id"], rev[j1 + k]["id"], "unchanged") for k in range(i2 - i1)]
        elif tag == "delete":
            out += [(base[i]["id"], None, "removed") for i in range(i1, i2)]
        elif tag == "insert":
            out += [(None, rev[j]["id"], "new") for j in range(j1, j2)]
        else:  # replace: pair edits in order when the text is still recognisably the same passage
            matched: dict[int, int] = {}
            last_i = i1 - 1
            for j in range(j1, j2):
                best, best_r = None, EDITED_MIN_SIMILARITY
                for i in range(last_i + 1, i2):
                    r = _sim(bt[i], rt[j])
                    if r >= best_r:
                        best, best_r = i, r
                if best is not None:
                    matched[j], last_i = best, best
            used = set(matched.values())
            for j in range(j1, j2):
                out.append((base[matched[j]]["id"], rev[j]["id"], "edited") if j in matched else (None, rev[j]["id"], "new"))
            out += [(base[i]["id"], None, "removed") for i in range(i1, i2) if i not in used]
    return out


# ------------------------------------------------------------------ comparison
def _first_stop(a: Analysis) -> dict[str, int]:
    return {p.persona: p.first_stop_segment for p in a.personas if p.first_stop_segment is not None}


def compare(
    *, baseline: Analysis, base_segments: list[dict], revised: Analysis, rev_segments: list[dict],
    baseline_run_id: str, run_id: str, kind: Literal["revision", "whatif"], label: str | None,
) -> Comparison:
    b_stat = {s.segment_id: s for s in baseline.segments}
    r_stat = {s.segment_id: s for s in revised.segments}
    b_label = {s["id"]: s["label"] for s in base_segments}
    r_label = {s["id"]: s["label"] for s in rev_segments}
    pairs = align(base_segments, rev_segments)
    to_rev = {b: r for b, r, _ in pairs if b is not None and r is not None}

    rows: list[SegmentDelta] = []
    for b, r, change in pairs:
        bs, rs = b_stat.get(b) if b else None, r_stat.get(r) if r else None
        bm = bs.mean if bs else None
        rm = rs.mean if rs else None
        per: dict[str, PersonaScore] = {}
        if bs and rs:
            for k, before in bs.scores.items():
                if k in rs.scores:
                    per[k] = PersonaScore(before=before, after=rs.scores[k], delta=rs.scores[k] - before)
        if change == "removed":
            status: Status = "removed"
        elif change == "new":
            status = "new"
        elif bm is None or rm is None:
            status = "unrated"
        else:
            d = rm - bm
            status = "improved" if d >= MEANINGFUL_SEGMENT else "weakened" if d <= -MEANINGFUL_SEGMENT else "unchanged"
        rows.append(SegmentDelta(
            base_segment_id=b, rev_segment_id=r, base_label=b_label.get(b) if b else None,
            rev_label=r_label.get(r) if r else None, change=change, status=status,
            base_mean=bm, rev_mean=rm, delta=round(rm - bm, 2) if bm is not None and rm is not None else None,
            personas=per, collateral=(change == "unchanged" and status == "weakened"),
        ))

    # per reader
    b_avg = {p.persona: p.avg for p in baseline.personas}
    r_avg = {p.persona: p.avg for p in revised.personas}
    personas: list[PersonaDelta] = []
    for p in PERSONAS:
        b, r = b_avg.get(p.key), r_avg.get(p.key)
        if b is None or r is None:
            personas.append(PersonaDelta(persona=p.key, persona_name=p.name, before=b, after=r, status="unrated"))
            continue
        d = round(r - b, 2)
        personas.append(PersonaDelta(
            persona=p.key, persona_name=p.name, before=b, after=r, delta=d,
            status="improved" if d >= MEANINGFUL_PERSONA else "weakened" if d <= -MEANINGFUL_PERSONA else "unchanged"))

    # drop-offs: was each earlier exit resolved?
    b_stop, r_stop = _first_stop(baseline), _first_stop(revised)
    outcomes: list[DropoffOutcome] = []
    for key, b_sid in sorted(b_stop.items()):
        name = PERSONAS_BY_KEY[key].name
        mapped = to_rev.get(b_sid)
        r_sid = r_stop.get(key)
        if r_sid is None:
            st, txt = "resolved", f"{name} no longer wants to stop (it was {b_label[b_sid]})."
        elif mapped is not None and r_sid == mapped:
            st, txt = "still", f"{name} would still stop at {r_label[r_sid]}."
        else:
            st, txt = "moved", f"{name} used to stop at {b_label[b_sid]} and now stops at {r_label[r_sid]}."
        outcomes.append(DropoffOutcome(persona=key, persona_name=name, status=st,  # type: ignore[arg-type]
                                       before_label=b_label[b_sid], after_label=r_label.get(r_sid) if r_sid else None, text=txt))
    for key, r_sid in sorted(r_stop.items()):
        if key not in b_stop:
            name = PERSONAS_BY_KEY[key].name
            outcomes.append(DropoffOutcome(persona=key, persona_name=name, status="new", after_label=r_label[r_sid],
                                           text=f"{name} did not stop before, but now would stop at {r_label[r_sid]}."))

    # overall
    ob, oa = baseline.overall_mean, revised.overall_mean
    od = round(oa - ob, 2) if ob is not None and oa is not None else None
    improved = sum(1 for r in rows if r.status == "improved")
    weakened = sum(1 for r in rows if r.status == "weakened")
    if od is None:
        verdict = "unrated"
    elif od >= MEANINGFUL_OVERALL and weakened <= improved:
        verdict = "better"
    elif od <= -MEANINGFUL_OVERALL and improved <= weakened:
        verdict = "worse"
    elif abs(od) < MEANINGFUL_OVERALL and improved == 0 and weakened == 0:
        verdict = "about_the_same"
    else:
        verdict = "mixed"

    def _ret(a: Analysis) -> float | None:
        return a.dropoff.curve[-1].pct if a.dropoff.curve else None

    return Comparison(
        baseline_run_id=baseline_run_id, run_id=run_id, kind=kind, label=label,
        overall_before=ob, overall_after=oa, overall_delta=od, verdict=verdict,  # type: ignore[arg-type]
        meter_before=baseline.meter.document.name if baseline.meter.document else None,
        meter_after=revised.meter.document.name if revised.meter.document else None,
        retention_before=_ret(baseline), retention_after=_ret(revised),
        improved=improved, weakened=weakened, collateral=sum(1 for r in rows if r.collateral),
        segments=rows, personas=personas, dropoffs=outcomes,
        highlights=_highlights(rows, personas, outcomes),
    )


def _highlights(rows: list[SegmentDelta], personas: list[PersonaDelta], outcomes: list[DropoffOutcome]) -> list[str]:
    out: list[str] = []
    best = max(((r, k, v) for r in rows for k, v in r.personas.items()), key=lambda t: t[2].delta, default=None)
    if best and best[2].delta >= 2:
        r, k, v = best
        out.append(f"{PERSONAS_BY_KEY[k].name} responded better to {r.rev_label}: {v.before}/10 became {v.after}/10.")
    worst = min(((r, k, v) for r in rows for k, v in r.personas.items()), key=lambda t: t[2].delta, default=None)
    if worst and worst[2].delta <= -2:
        r, k, v = worst
        side = " That text was not edited, so an earlier change may have affected it." if r.collateral else ""
        out.append(f"{PERSONAS_BY_KEY[k].name} responded worse to {r.rev_label}: {v.before}/10 became {v.after}/10.{side}")
    resolved = [o for o in outcomes if o.status == "resolved"]
    if resolved:
        out.append(f"Resolved drop-off{'s' if len(resolved) > 1 else ''}: " + " ".join(o.text for o in resolved))
    for o in outcomes:
        if o.status in ("still", "moved", "new"):
            out.append(o.text)
    return out
