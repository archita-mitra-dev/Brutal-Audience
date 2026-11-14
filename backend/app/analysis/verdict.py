"""Brutal Verdict: the final report.

Design rules
------------
* Numbers are never taken from the model. Strongest/weakest segment, drop-off points
  and collisions come from `stats.analyse()`; the model only writes the narrative.
* Every suggestion cites real segment IDs, and any quoted evidence must be a verbatim
  excerpt of a cited segment (checked with the same verifier the simulation uses).
* The report recommends. It never supplies replacement text, and nothing it says is
  ever applied to the creator's draft.
* Demo mode builds the report from the recorded reactions with plain templates, and
  is labelled as demo in the payload and in the UI.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..llm.base import LLMClient
from ..personas.definitions import PERSONAS, PERSONAS_BY_KEY
from ..schemas import ReactionOut
from ..simulation.validation import ReactionError, extract_json, verify_evidence
from .models import Analysis, PersonaTake, SegmentNote, Suggestion, Verdict
from .stats import LENS

MAX_RETRIES = 2


class VerdictError(ValueError):
    """The model's report could not be turned into a valid verdict."""


# --- what the model must return ------------------------------------------------
class _LLMTake(BaseModel):
    model_config = ConfigDict(extra="ignore")
    persona: str
    liked: str = Field(min_length=1, max_length=500)
    disliked: str = Field(min_length=1, max_length=500)


class _LLMSuggestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=120)
    segment_ids: list[int] = Field(min_length=1)
    problem: str = Field(min_length=1, max_length=700)
    action: str = Field(min_length=1, max_length=700)
    evidence: str | None = None


class _LLMVerdict(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overall: str = Field(min_length=1, max_length=900)
    strongest_why: str = Field(min_length=1, max_length=600)
    weakest_why: str = Field(min_length=1, max_length=600)
    persona_takes: list[_LLMTake]
    polarising_note: str | None = None
    suggestions: list[_LLMSuggestion]


SYSTEM = """\
You write the final "Brutal Verdict" for a creator whose draft has just been read, segment by segment, by four simulated audience members (an audience simulation, not real readers).

HARD RULES
- You report on the audience's recorded reactions. You are NOT a co-writer: never write replacement sentences, rewrites, or example lines. Say what caused a reaction and what the creator might look at or decide. All creative decisions stay with the creator.
- Be honest but constructive. No flattery, no filler, no generic advice like "improve the pacing" or "improve the writing". Name the cause and the place.
- Use only the facts provided. Cite segments by their numeric ID. Do not invent segments, scores or quotes.
- "evidence", when you include it, must be an EXACT word-for-word excerpt (max 200 characters) from one of the segments you cite in that suggestion. If you cannot quote exactly, set "evidence" to null.
- Disagreement between personas is information, not a defect. If a suggestion would please one persona and lose another, say so.
- Reply with ONE JSON object and nothing else (no markdown, no code fences).

JSON SHAPE
{
  "overall": "3-4 sentences on how the audience responded overall",
  "strongest_why": "why the strongest segment worked, citing what the personas reacted to",
  "weakest_why": "why the weakest segment lost them, citing what the personas reacted to",
  "persona_takes": [ {"persona": "doom|critic|fan|newbie", "liked": "what this persona liked", "disliked": "what this persona disliked"} ],
  "polarising_note": "one or two sentences on where the audience split and why that may be fine, or null",
  "suggestions": [ {"title": "short label", "segment_ids": [3], "problem": "what caused the reaction and where", "action": "what to look at or decide (no replacement text)", "evidence": "exact quote or null"} ]
}
"persona_takes" must contain exactly one entry for each persona that appears in the data. "suggestions" must contain EXACTLY the requested number of items, ordered by importance."""


def _clip(s: str | None, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def build_user_prompt(title: str, content_type: str, segments: list[dict],
                      reactions: list[ReactionOut], analysis: Analysis, n_suggestions: int) -> str:
    big = len(segments) > 30
    seg_chars, reason_chars = (350, 110) if big else (700, 200)
    lines = [f'Work: "{title}" ({content_type}). {len(segments)} segments.\n', "SEGMENTS"]
    for s in segments:
        lines.append(f"[{s['id']}] {s['label']}: {_clip(s['text'], seg_chars)}")
    lines.append("\nREACTIONS (persona | segment | score 0-10 | emotion | would continue | reason)")
    for r in reactions:
        if r.status != "ok":
            continue
        lines.append(
            f"{r.persona} | {r.segment_id} | {r.engagement_score} | {r.emotion} | "
            f"{'yes' if r.would_continue else 'NO'} | {_clip(r.reason, reason_chars)}"
        )
    lines.append("\nCOMPUTED FACTS (use these, do not recompute)")
    lines.append(f"- Overall mean engagement: {analysis.overall_mean}/10")
    lines.append(f"- Strongest segment: {analysis.strongest_segment_id}; weakest segment: {analysis.weakest_segment_id}")
    for d in analysis.drop_offs:
        lines.append(f"- First wanted to stop at segment {d.segment_id}: {', '.join(d.persona_names)}")
    for c in analysis.collisions[:5]:
        lines.append(
            f"- Collision at segment {c.segment_id}: {c.high.persona} {c.high.score}/10 vs "
            f"{c.low.persona} {c.low.score}/10"
        )
    lines.append(f"\nWrite the verdict now with exactly {n_suggestions} suggestion(s).")
    return "\n".join(lines)


def _validate(data: dict, segments: dict[int, str], expected_personas: set[str],
              n_suggestions: int, *, strip_bad_evidence: bool) -> tuple[_LLMVerdict, list[str]]:
    """Returns the parsed verdict and a list of evidence problems (empty when clean)."""
    try:
        v = _LLMVerdict.model_validate(data)
    except ValidationError as exc:
        raise VerdictError("invalid fields: " + "; ".join(
            f"'{'.'.join(str(p) for p in e['loc'])}' {e['msg']}" for e in exc.errors())) from None

    got = {t.persona for t in v.persona_takes}
    unknown = got - set(PERSONAS_BY_KEY)
    if unknown:
        raise VerdictError(f"unknown persona key(s): {sorted(unknown)}")
    missing = expected_personas - got
    if missing:
        raise VerdictError(f"persona_takes is missing: {sorted(missing)}")
    if len(v.suggestions) != n_suggestions:
        raise VerdictError(f"expected exactly {n_suggestions} suggestion(s), got {len(v.suggestions)}")

    problems: list[str] = []
    for i, s in enumerate(v.suggestions, start=1):
        bad = [x for x in s.segment_ids if x not in segments]
        if bad:
            raise VerdictError(f"suggestion {i} cites segment id(s) that do not exist: {bad}")
        if s.evidence and not any(verify_evidence(s.evidence, segments[x]) for x in s.segment_ids):
            problems.append(f"suggestion {i}: evidence is not a verbatim excerpt of segment(s) {s.segment_ids}")
            if strip_bad_evidence:
                s.evidence = None
    return v, problems


def _note(analysis: Analysis, seg_id: int | None, why: str) -> SegmentNote | None:
    if seg_id is None:
        return None
    st = next(s for s in analysis.segments if s.segment_id == seg_id)
    return SegmentNote(segment_id=seg_id, label=st.label, mean=st.mean, why=why)


def _assemble(run_id: str, mode: str, model: str, analysis: Analysis, v: _LLMVerdict) -> Verdict:
    order = {p.key: i for i, p in enumerate(PERSONAS)}
    takes = sorted(v.persona_takes, key=lambda t: order[t.persona])
    return Verdict(
        run_id=run_id, mode=mode, model=model,  # type: ignore[arg-type]
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        overall=v.overall.strip(),
        strongest=_note(analysis, analysis.strongest_segment_id, v.strongest_why.strip()),
        weakest=_note(analysis, analysis.weakest_segment_id, v.weakest_why.strip()),
        drop_offs=analysis.drop_offs,
        persona_takes=[PersonaTake(persona=t.persona, persona_name=PERSONAS_BY_KEY[t.persona].name,
                                   liked=t.liked.strip(), disliked=t.disliked.strip()) for t in takes],
        polarising_note=(v.polarising_note or "").strip() or None,
        suggestions=[Suggestion(**s.model_dump()) for s in v.suggestions],
    )


def suggestion_count(reactions: list[ReactionOut]) -> int:
    return min(3, sum(1 for r in reactions if r.status == "ok"))


async def generate_live(client: LLMClient, *, run_id: str, title: str, content_type: str,
                        segments: list[dict], reactions: list[ReactionOut],
                        analysis: Analysis) -> Verdict:
    seg_text = {s["id"]: s["text"] for s in segments}
    expected = {r.persona for r in reactions if r.status == "ok"}
    n = suggestion_count(reactions)
    user = build_user_prompt(title, content_type, segments, reactions, analysis, n)

    correction: str | None = None
    last = "unknown error"
    for attempt in range(1, MAX_RETRIES + 2):
        final = attempt == MAX_RETRIES + 1
        prompt = user if correction is None else f"{user}\n\nYour previous reply was rejected: {correction}"
        raw = await client.complete_json(SYSTEM, prompt)   # LLMError propagates to the route
        try:
            v, problems = _validate(extract_json(raw), seg_text, expected, n, strip_bad_evidence=final)
        except (ReactionError, VerdictError) as exc:
            last = str(exc)
            correction = f"{exc}. Reply again with ONE valid JSON object only."
            continue
        if problems and not final:
            last = "; ".join(problems)
            correction = "; ".join(problems) + ". Copy evidence EXACTLY from the segment, or use null."
            continue
        return _assemble(run_id, "live", client.name, analysis, v)
    raise VerdictError(f"The model did not return a usable verdict ({last}).")


# --- demo verdict: templates over recorded reactions, clearly not AI --------------
def generate_demo(*, run_id: str, model: str, segments: list[dict], reactions: list[ReactionOut],
                  analysis: Analysis) -> Verdict:
    ok = [r for r in reactions if r.status == "ok" and r.engagement_score is not None]
    label = {s["id"]: s["label"] for s in segments}
    mean = analysis.overall_mean or 0
    tone = "strong" if mean >= 7 else "mixed" if mean >= 4.5 else "weak"
    overall = (
        f"The panel's average engagement was {mean:.1f}/10, a {tone} response overall. "
        f"{len(analysis.drop_offs)} drop-off point(s) and {len(analysis.collisions)} audience collision(s) were found. "
        "This summary is generated from text statistics, not by an AI audience."
    )

    def why(seg_id: int | None, high: bool) -> str:
        rs = sorted((r for r in ok if r.segment_id == seg_id), key=lambda r: r.engagement_score or 0, reverse=high)
        return f"{rs[0].persona_name} reacted most {'positively' if high else 'negatively'}: {rs[0].reason}" if rs else "No data."

    takes = []
    for p in PERSONAS:
        mine = sorted((r for r in ok if r.persona == p.key), key=lambda r: r.engagement_score or 0)
        if not mine:
            continue
        takes.append(PersonaTake(
            persona=p.key, persona_name=p.name,
            liked=f"Best moment ({label[mine[-1].segment_id]}, {mine[-1].engagement_score}/10): {mine[-1].reason}",
            disliked=f"Worst moment ({label[mine[0].segment_id]}, {mine[0].engagement_score}/10): {mine[0].reason}",
        ))

    # Three suggestions from the lowest-scoring reactions, preferring different segments.
    pool = sorted((r for r in ok), key=lambda r: (r.engagement_score or 0, r.segment_id))
    picked: list[ReactionOut] = []
    seen_segs: set[int] = set()
    for r in pool:
        if r.segment_id not in seen_segs:
            picked.append(r); seen_segs.add(r.segment_id)
        if len(picked) == 3:
            break
    for r in pool:
        if len(picked) >= min(3, len(pool)):
            break
        if r not in picked:
            picked.append(r)
    suggestions = [
        Suggestion(
            title=f"Look again at {label[r.segment_id]}",
            segment_ids=[r.segment_id],
            problem=f"{r.persona_name} scored it {r.engagement_score}/10 ({r.emotion}): {r.reason}",
            action=f"Re-read {label[r.segment_id]} from {r.persona_name}'s point of view "
                   f"({LENS.get(r.persona, 'their taste')}) and decide whether that reaction matters for your intended audience.",
            evidence=r.evidence,
        ) for r in picked
    ]

    pol = None
    if analysis.collisions:
        c = analysis.collisions[0]
        pol = (f"Biggest split: {c.label}, where {c.high.persona_name} gave {c.high.score}/10 and "
               f"{c.low.persona_name} gave {c.low.score}/10. Not every audience has to agree.")

    return Verdict(
        run_id=run_id, mode="demo", model=model,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        overall=overall,
        strongest=_note(analysis, analysis.strongest_segment_id, why(analysis.strongest_segment_id, True)),
        weakest=_note(analysis, analysis.weakest_segment_id, why(analysis.weakest_segment_id, False)),
        drop_offs=analysis.drop_offs, persona_takes=takes, polarising_note=pol, suggestions=suggestions,
    )
