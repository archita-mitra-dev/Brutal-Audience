"""Pydantic models shared by the API and the segmenter."""
from enum import Enum

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    story = "story"
    screenplay = "screenplay"
    lyrics = "lyrics"
    article = "article"
    other = "other"


class Segment(BaseModel):
    """One ordered, addressable slice of the creator's work.

    `text` is always exactly `content[char_start:char_end]` of the original
    submission, so nothing is ever rewritten or normalised.
    """

    id: int = Field(ge=1, description="1-based position; unique within a submission")
    label: str = Field(description="Human label, e.g. 'Paragraph 3' or 'Scene 2'")
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class SegmentOut(Segment):
    word_count: int


class SegmentRequest(BaseModel):
    content: str
    content_type: ContentType = ContentType.story


class SegmentResponse(BaseModel):
    content_type: ContentType
    segments: list[SegmentOut]
    total_words: int
    truncated: bool = False


class SubmissionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content_type: ContentType
    content: str = Field(min_length=1)


class SubmissionOut(BaseModel):
    id: str
    title: str
    content_type: ContentType
    content: str
    created_at: str
    segments: list[SegmentOut]


class SubmissionSummary(BaseModel):
    id: str
    title: str
    content_type: ContentType
    created_at: str
    segment_count: int


class UploadResponse(BaseModel):
    filename: str
    text: str


# --- Phase 2: simulation runs --------------------------------------------------
from typing import Literal  # noqa: E402


class RunRequest(BaseModel):
    # auto = live if an LLM key is configured, otherwise demo
    mode: Literal["auto", "live", "demo"] = "auto"


class ReactionOut(BaseModel):
    persona: str                      # persona key: doom | critic | fan | newbie
    persona_name: str
    segment_id: int
    status: Literal["ok", "failed"]
    engagement_score: int | None = None
    emotion: str | None = None
    inner_thought: str | None = None
    would_continue: bool | None = None
    evidence: str | None = None       # verbatim excerpt of the segment, or None
    evidence_verified: bool = False
    reason: str | None = None
    error: str | None = None
    attempts: int = 1


class RunOut(BaseModel):
    id: str
    submission_id: str
    mode: Literal["live", "demo"]
    model: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    total_steps: int
    done_steps: int
    error: str | None = None
    created_at: str
    finished_at: str | None = None


class RunDetail(RunOut):
    title: str
    content_type: ContentType
    segments: list[SegmentOut]
    reactions: list[ReactionOut]
