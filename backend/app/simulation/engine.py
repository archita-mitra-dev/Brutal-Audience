"""Sequential audience simulation — the core of Brutal Audience.

Guarantees
----------
1. ORDER: each persona reads segment 1, then 2, then 3 ... one at a time. A
   reaction is produced (and stored) before the next segment is even built.
2. NO FUTURE LEAKAGE: the request for segment i is built from `segments[:i]`
   (already read) plus `segments[i]` (current). Later segments are never in scope
   of the code that builds a prompt.
3. PARALLEL PERSONAS: the four personas run concurrently with each other, but
   each persona's own reading sequence stays strictly ordered.
4. NOTHING UNVALIDATED IS STORED: replies are parsed + validated; bad replies are
   retried with a correction message; unverifiable evidence is dropped (never kept).
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Callable

from ..llm.base import FatalLLMError, LLMError
from ..personas.definitions import Persona
from ..schemas import ReactionOut, Segment
from .backends import ReactionBackend
from .types import PriorReaction, ReactionRequest
from .validation import Parsed, ReactionError, parse_reaction

log = logging.getLogger("brutal_audience.engine")

_EVIDENCE_NUDGE = (
    "the 'evidence' must be copied EXACTLY, word for word, from the segment you are reading now "
    "(not from an earlier segment, not paraphrased)."
)


def _ok(persona: Persona, seg_id: int, parsed: Parsed, attempts: int) -> ReactionOut:
    r = parsed.reaction
    return ReactionOut(
        persona=persona.key,
        persona_name=persona.name,
        segment_id=seg_id,
        status="ok",
        engagement_score=r.engagement_score,
        emotion=r.emotion,
        inner_thought=r.inner_thought,
        would_continue=r.would_continue,
        # Never keep a quote we could not find in the text.
        evidence=r.evidence if parsed.evidence_verified else None,
        evidence_verified=parsed.evidence_verified,
        reason=r.reason,
        attempts=attempts,
    )


def _failed(persona: Persona, seg_id: int, error: str, attempts: int) -> ReactionOut:
    return ReactionOut(
        persona=persona.key, persona_name=persona.name, segment_id=seg_id,
        status="failed", error=error, attempts=attempts,
    )


async def react_with_retries(
    backend: ReactionBackend, req: ReactionRequest, max_retries: int
) -> ReactionOut:
    """One persona, one segment: call, validate, retry with feedback, or fail cleanly."""
    persona, seg = req.persona, req.current
    last_error = "unknown error"
    salvage: Parsed | None = None
    correction: str | None = None
    attempts = 0

    for attempt in range(1, max_retries + 2):
        attempts = attempt
        try:
            raw = await backend.react(dataclasses.replace(req, correction=correction))
            parsed = parse_reaction(raw, seg.text)
        except FatalLLMError:
            raise  # misconfiguration: abort the whole run
        except ReactionError as exc:
            last_error = f"Invalid model reply: {exc}"
            correction = f"{exc}. Reply again with ONE valid JSON object only."
            continue
        except LLMError as exc:
            last_error = str(exc)
            if not exc.retryable:
                break
            continue

        if parsed.evidence_verified:
            return _ok(persona, seg.id, parsed, attempts)
        # Valid reaction but the quote isn't in the text: ask again, keep as fallback.
        salvage = parsed
        last_error = "evidence was not a verbatim quote of the segment"
        correction = _EVIDENCE_NUDGE

    if salvage is not None:
        return _ok(persona, seg.id, salvage, attempts)  # evidence dropped, flagged unverified
    return _failed(persona, seg.id, last_error, attempts)


async def run_persona(
    persona: Persona,
    title: str,
    content_type: str,
    segments: list[Segment],
    backend: ReactionBackend,
    on_reaction: Callable[[ReactionOut], None],
    stop: asyncio.Event,
    max_retries: int,
) -> None:
    history: list[PriorReaction] = []
    for i, current in enumerate(segments):
        if stop.is_set():
            return
        req = ReactionRequest(
            persona=persona,
            title=title,
            content_type=content_type,
            seen=tuple(segments[:i]),      # <- only what was already read
            current=current,
            history=tuple(history),
        )
        reaction = await react_with_retries(backend, req, max_retries)
        on_reaction(reaction)
        history.append(
            PriorReaction(
                segment_id=current.id,
                score=reaction.engagement_score,
                emotion=reaction.emotion,
                thought=reaction.inner_thought,
                would_continue=reaction.would_continue,
            )
        )
        await asyncio.sleep(0)  # yield so other personas / pollers get a turn


async def run_simulation(
    *,
    submission: dict,
    personas: tuple[Persona, ...],
    backend: ReactionBackend,
    on_reaction: Callable[[ReactionOut], None],
    stop: asyncio.Event,
    max_retries: int = 2,
    blind: bool = False,
) -> tuple[str, str | None]:
    """Run all personas. Returns (final_status, error_message).

    blind=True is the Blind Audience Test: the title is withheld from every persona. The
    reading itself is blind in every run (no author identity, no explanation, no later text).
    """
    segments = [Segment(**s) for s in submission["segments"]]
    title = "" if blind else submission["title"]
    fatal: list[str] = []

    async def one(p: Persona) -> None:
        try:
            await run_persona(
                p, title, submission["content_type"], segments,
                backend, on_reaction, stop, max_retries,
            )
        except FatalLLMError as exc:
            fatal.append(str(exc))
            stop.set()  # no point continuing the other personas

    results = await asyncio.gather(*(one(p) for p in personas), return_exceptions=True)
    unexpected = [r for r in results if isinstance(r, BaseException)]
    if unexpected:
        log.exception("persona task crashed", exc_info=unexpected[0])
        return "failed", "An unexpected error stopped the simulation."
    if fatal:
        return "failed", fatal[0]
    if stop.is_set():
        return "cancelled", None
    return "completed", None
