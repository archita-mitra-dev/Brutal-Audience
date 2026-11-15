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


# --- Brutality Meter (Phase 6) -------------------------------------------------
SegmentLevel = Literal["strong", "curious", "declining", "multi_stop"]
DocumentLevel = Literal["holds", "mixed", "shaky", "brutal"]


class SegmentMeter(BaseModel):
    segment_id: int
    label: str
    level: SegmentLevel
    name: str                          # human label for the level
    rule: str                          # the numbers behind the classification
    mean: float


class DocumentMeter(BaseModel):
    level: DocumentLevel
    name: str
    rule: str
    counts: dict[str, int]             # segments per SegmentLevel
    never_stopped: list[str]           # persona names who never wanted to stop reading
    persona_count: int


class Meter(BaseModel):
    segments: list[SegmentMeter] = Field(default_factory=list)
    document: DocumentMeter | None = None
    thresholds: dict[str, float] = Field(default_factory=dict)


# --- Drop-off prediction (Phase 7) -------------------------------------------------
class DropoffRow(BaseModel):
    segment_id: int
    label: str
    states: dict[str, Literal["continue", "drop_off", "already_left", "unread"]]   # persona key -> state


class CurvePoint(BaseModel):
    segment_id: int                    # 0 = the start, before anything is read
    label: str
    still_reading: int
    pct: float


class Trigger(BaseModel):
    persona: str
    persona_name: str
    segment_id: int
    label: str
    sentence: str | None = None        # the sentence containing the persona's verbatim evidence, or None
    score: int
    inner_thought: str | None = None
    reason: str | None = None


class DropoffPrediction(BaseModel):
    reader_count: int = 0
    rows: list[DropoffRow] = Field(default_factory=list)
    curve: list[CurvePoint] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)
    steepest_segment_id: int | None = None
    reached_end: list[str] = Field(default_factory=list)   # persona names who never wanted to stop


# --- Audience Split Detector (Phase 7) -----------------------------------------------
class SplitReader(BaseModel):
    persona: str
    persona_name: str
    audience: str                      # plain-language audience this persona stands for
    score: int
    reason: str | None = None


class SplitSegment(BaseModel):
    segment_id: int
    label: str
    gap: int
    headline: str                      # "may appeal strongly to X but lose Y"
    why: str                           # built from the personas' own recorded reasons
    appeals_to: list[SplitReader]
    loses: list[SplitReader]


class PersonaFit(BaseModel):
    persona: str
    persona_name: str
    audience: str
    avg: float
    rank: int


class DividePair(BaseModel):
    high: str
    low: str
    count: int


class SplitReport(BaseModel):
    segments: list[SplitSegment] = Field(default_factory=list)
    fit: list[PersonaFit] = Field(default_factory=list)
    work_note: str = ""
    divides: list[DividePair] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)


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
    meter: Meter = Field(default_factory=Meter)
    dropoff: DropoffPrediction = Field(default_factory=DropoffPrediction)
    split: SplitReport = Field(default_factory=SplitReport)


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
