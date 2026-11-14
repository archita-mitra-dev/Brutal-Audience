"""Validation of model output.

Nothing the model returns is trusted: it is parsed, coerced where that is
unambiguous, validated with Pydantic, and its quoted "evidence" is checked to be
a genuine verbatim excerpt of the segment being read (no fabricated evidence).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..personas.prompts import EMOTIONS


class ReactionError(ValueError):
    """The model's reply could not be turned into a valid reaction."""


class LLMReaction(BaseModel):
    """The validated shape of one persona reaction (persona + segment_id are added
    by the engine, never trusted from the model)."""

    model_config = ConfigDict(extra="ignore")

    engagement_score: int = Field(ge=0, le=10)
    emotion: str
    inner_thought: str = Field(min_length=1, max_length=400)
    would_continue: bool
    evidence: str = Field(min_length=1, max_length=600)
    reason: str = Field(min_length=1, max_length=800)

    @field_validator("engagement_score", mode="before")
    @classmethod
    def _score(cls, v):
        if isinstance(v, bool):
            raise ValueError("must be a number from 0 to 10")
        if isinstance(v, str):
            try:
                v = float(v.strip().split("/")[0])
            except ValueError as exc:
                raise ValueError("must be a number from 0 to 10") from exc
        if isinstance(v, float):
            v = round(v)
        return v

    @field_validator("emotion", mode="before")
    @classmethod
    def _emotion(cls, v):
        e = str(v).strip().lower()
        if e not in EMOTIONS:
            raise ValueError(f"must be one of: {', '.join(EMOTIONS)}")
        return e

    @field_validator("would_continue", mode="before")
    @classmethod
    def _bool(cls, v):
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"yes", "true"}:
                return True
            if s in {"no", "false"}:
                return False
        return v

    @field_validator("inner_thought", "reason", "evidence", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


@dataclass(frozen=True)
class Parsed:
    reaction: LLMReaction
    evidence_verified: bool


def extract_json(raw: str | dict) -> dict:
    """Pull one JSON object out of a model reply (tolerates code fences / chatter)."""
    if isinstance(raw, dict):
        return raw
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ReactionError("the reply was not a JSON object") from None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ReactionError(f"the reply was not valid JSON ({exc.msg})") from None
    if not isinstance(data, dict):
        raise ReactionError("the reply was JSON but not an object")
    return data


# --- evidence verification ---------------------------------------------------
_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip().casefold()


def verify_evidence(evidence: str, segment_text: str) -> bool:
    """True if `evidence` is a verbatim excerpt of `segment_text`.

    Tolerates: curly vs straight quotes, whitespace/line-break differences, case,
    surrounding quotation marks, and '...' joining separate fragments (each
    fragment must itself appear in the segment).
    """
    hay = _norm(segment_text)
    ev = _norm(evidence).strip("\"' ")
    fragments = [f.strip("\"' ") for f in re.split(r"\.\.\.|…", ev)]
    fragments = [f for f in fragments if f]
    if not fragments:
        return False
    if sum(len(f) for f in fragments) < 4:
        return False
    return all(f in hay for f in fragments)


def parse_reaction(raw: str | dict, segment_text: str) -> Parsed:
    """Raw model output -> validated reaction + whether its evidence is genuine."""
    data = extract_json(raw)
    try:
        reaction = LLMReaction.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"'{'.'.join(str(p) for p in e['loc'])}' {e['msg']}" for e in exc.errors()
        )
        raise ReactionError(f"invalid fields: {problems}") from None
    return Parsed(reaction, verify_evidence(reaction.evidence, segment_text))
