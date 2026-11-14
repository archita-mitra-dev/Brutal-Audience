"""Response models for the analysis (Phase 3) and the Brutal Verdict (Phase 4)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Participant(BaseModel):
    """One persona's recorded reaction, as quoted inside a collision."""

    persona: str
    persona_name: str
    score: int
    emotion: str | None = None
    inner_thought: str | None = None
    reason: str | None = None
    evidence: str | None = None
    would_continue: bool | None = None


class SegmentStat(BaseModel):
    segment_id: int
    label: str
    read_by: int                       # personas with a valid reaction here
    mean: float | None = None
    min: int | None = None
    max: int | None = None
    spread: int | None = None
    scores: dict[str, int] = Field(default_factory=dict)   # persona key -> score
    stopped: list[str] = Field(default_factory=list)       # persona keys who would stop here


class PersonaStat(BaseModel):
    persona: str
    persona_name: str
    avg: float | None = None
    n_ok: int
    n_failed: int
    first_stop_segment: int | None = None


class DropOff(BaseModel):
    segment_id: int
    label: str
    personas: list[str]
    persona_names: list[str]
    consensus: bool                    # two or more personas stop at the same segment


class Collision(BaseModel):
    segment_id: int
    label: str
    kind: Literal["score_gap", "continue_split"]
    spread: int
    high: Participant
    low: Participant
    others: list[Participant] = Field(default_factory=list)
    explanation: str                   # built from the personas' own recorded reasons


class Agreement(BaseModel):
    segment_id: int
    label: str
    kind: Literal["shared_high", "shared_low"]
    mean: float


class Analysis(BaseModel):
    run_id: str
    status: str
    partial: bool                      # True while the run is still going / was stopped early
    overall_mean: float | None = None
    strongest_segment_id: int | None = None
    weakest_segment_id: int | None = None
    segments: list[SegmentStat]
    personas: list[PersonaStat]
    drop_offs: list[DropOff]
    lost_attention: list[int]          # segments where 2+ personas stopped or scored <= 3
    collisions: list[Collision]
    agreements: list[Agreement]


# --- Brutal Verdict ------------------------------------------------------------
class SegmentNote(BaseModel):
    segment_id: int
    label: str
    mean: float | None = None
    why: str


class PersonaTake(BaseModel):
    persona: str
    persona_name: str
    liked: str
    disliked: str


class Suggestion(BaseModel):
    title: str
    segment_ids: list[int]
    problem: str                       # what caused the reaction, and where
    action: str                        # what to look at / consider. Never replacement text.
    evidence: str | None = None        # verbatim excerpt of a cited segment, or None


class Verdict(BaseModel):
    run_id: str
    mode: Literal["live", "demo"]
    model: str
    generated_at: str
    overall: str
    strongest: SegmentNote | None = None
    weakest: SegmentNote | None = None
    drop_offs: list[DropOff]
    persona_takes: list[PersonaTake]
    polarising_note: str | None = None
    suggestions: list[Suggestion]
