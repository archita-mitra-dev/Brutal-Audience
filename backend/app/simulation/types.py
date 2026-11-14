from __future__ import annotations

from dataclasses import dataclass, field

from ..personas.definitions import Persona
from ..schemas import Segment


@dataclass(frozen=True)
class PriorReaction:
    """Compact memory of a persona's own earlier reaction (continuity only)."""

    segment_id: int
    score: int | None
    emotion: str | None
    thought: str | None
    would_continue: bool | None


@dataclass(frozen=True)
class ReactionRequest:
    """Everything a persona is allowed to know when reacting to `current`.

    Spec guarantee: `seen` only ever holds segments *before* `current`. The engine
    builds it as `segments[:i]`, so future text cannot be passed in by accident.
    Nothing in here carries the total segment count either.
    """

    persona: Persona
    title: str
    content_type: str
    seen: tuple[Segment, ...]
    current: Segment
    history: tuple[PriorReaction, ...] = field(default_factory=tuple)
    correction: str | None = None  # set on a retry, explains what was wrong
