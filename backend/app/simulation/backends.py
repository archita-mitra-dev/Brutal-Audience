"""Reaction backends: how a persona's reaction to one segment is produced.

- LiveBackend: asks a real LLM (Gemini / OpenAI-compatible).
- DemoBackend: NO AI. Cheap text statistics (sentence length, dialogue, cliché
  phrases...) standing in for an audience so the app can be explored without an
  API key. It is labelled "demo" end to end and must never be presented as real
  AI-generated feedback. Evidence it returns is still a real excerpt.
"""
from __future__ import annotations

import re
import zlib
from typing import Literal, Protocol

from ..llm.base import LLMClient
from ..personas.prompts import build_system_prompt, build_user_prompt
from .types import ReactionRequest


class ReactionBackend(Protocol):
    mode: Literal["live", "demo"]
    label: str

    async def react(self, req: ReactionRequest) -> str | dict: ...


class LiveBackend:
    mode: Literal["live", "demo"] = "live"

    def __init__(self, client: LLMClient):
        self._client = client
        self.label = client.name

    async def react(self, req: ReactionRequest) -> str:
        return await self._client.complete_json(
            build_system_prompt(req.persona), build_user_prompt(req)
        )


# --------------------------------------------------------------------------- demo
_CLICHES = (
    "dark and stormy", "suddenly", "little did", "heart pounded", "heart racing", "the chosen one",
    "once upon a time", "in a world", "at the end of the day", "it was all a dream", "time stood still",
    "a chill ran down", "blood ran cold", "deafening silence", "tears streamed", "little did they know",
    "against all odds", "mysterious stranger", "ancient prophecy",
)
_SENT = re.compile(r"(?<=[.!?…])[\"')\]”’]*\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z’']*")

_THOUGHTS = {
    "doom": {
        "low": ["Okay, when does something happen?", "I'm skimming. Next.", "Still setting up. Thumb's twitching."],
        "mid": ["Fine. Not hooked, not gone.", "Something's here, but it's slow.", "Give me a reason to stay."],
        "high": ["Wait, now I'm listening.", "Okay, that actually pulled me in.", "Hook landed. Keep going."],
    },
    "critic": {
        "low": ["I've read this beat a hundred times.", "That feels convenient.", "I'm not buying it."],
        "mid": ["Competent, but nothing I haven't seen.", "Holding judgement, for now.", "No flaws, no spark either."],
        "high": ["That detail is doing real work.", "Fresh, and it holds together.", "Earned. I'll give it that."],
    },
    "fan": {
        "low": ["Generic. This could be from any genre.", "Trope-by-numbers, and not well done.", "Where's the texture?"],
        "mid": ["Familiar ground, decently walked.", "I know where this is heading.", "Solid, if safe."],
        "high": ["Oh, that's the good stuff.", "Love the texture here.", "Someone knows their genre."],
    },
    "newbie": {
        "low": ["Wait, who is that again?", "I'm lost. Did I miss something?", "I feel like I need homework for this."],
        "mid": ["I mostly follow, but I'm guessing a bit.", "Okay, I'm along for the ride.", "Clear enough, not gripping."],
        "high": ["Oh, that actually got me.", "Clear and it landed.", "I understood that and felt it."],
    },
}
_EMOTION = {
    "doom":   {"low": "bored", "mid": "indifferent", "high": "excited"},
    "critic": {"low": "skeptical", "mid": "skeptical", "high": "delighted"},
    "fan":    {"low": "disappointed", "mid": "curious", "high": "excited"},
    "newbie": {"low": "confused", "mid": "curious", "high": "moved"},
}
_CONTINUE_AT = {"doom": 5, "critic": 4, "fan": 3, "newbie": 4}


def _band(score: int) -> str:
    return "low" if score <= 3 else "mid" if score <= 6 else "high"


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT.split(text.strip()) if s.strip()]
    return parts or [text.strip()]


def _clip(s: str, limit: int = 200) -> str:
    """Prefix of `s` cut at a word boundary — still a verbatim substring."""
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut or s[:limit]


class DemoBackend:
    mode: Literal["live", "demo"] = "demo"
    label = "demo (text-statistics heuristic, not AI)"

    async def react(self, req: ReactionRequest) -> dict:
        text = req.current.text
        sents = _sentences(text)
        words = _WORD.findall(text)
        n = len(words)
        avg_len = n / max(len(sents), 1)
        long_ratio = sum(1 for w in words if len(w) >= 9) / max(n, 1)
        lowered = text.lower()
        cliches = [c for c in _CLICHES if c in lowered]
        adverbs = [w for w in words if w.lower().endswith("ly") and w.lower() not in {"only", "family", "early", "reply", "july", "italy", "lily"}]
        caps = sum(1 for s in sents for w in s.split()[1:] if w[:1].isupper() and w[1:].islower())
        has_dialogue = any(q in text for q in ('"', "“", "”"))
        punchy = "?" in text or "!" in text
        first = req.current.id == 1
        seed = zlib.crc32(f"{req.persona.key}:{req.current.id}:{text[:40]}".encode())
        jitter = (-1, 0, 0, 1)[seed % 4]
        key = req.persona.key
        why: list[str] = []

        score = 6
        if key == "doom":
            if n > 60:
                score -= min(3, (n - 60) // 40 + 1); why.append(f"{n} words is a lot of runway before anything happens")
            if avg_len > 26:
                score -= 1; why.append("long sentences slow the pace")
            if has_dialogue:
                score += 1; why.append("dialogue keeps it moving")
            if punchy:
                score += 1; why.append("a question or exclamation creates pull")
            if first:
                score += 1 if (has_dialogue or punchy) else -1
                why.append("the opening has a hook" if (has_dialogue or punchy) else "the opening has no obvious hook")
        elif key == "critic":
            if cliches:
                score -= min(3, 2 * len(cliches)); why.append(f"stock phrase '{cliches[0]}'")
            if len(adverbs) >= 3:
                score -= 1; why.append("a pile of -ly adverbs")
            if caps >= 2 or re.search(r"\d", text):
                score += 1; why.append("concrete, specific detail")
            if n < 15:
                score -= 1; why.append("too thin to judge")
        elif key == "fan":
            if has_dialogue:
                score += 1; why.append("dialogue gives the genre voice room")
            if caps >= 3:
                score += 1; why.append("named things and world-building texture")
            if n > 80:
                score += 1; why.append("space for detail")
            if len(cliches) >= 2:
                score -= 2; why.append("trope-by-numbers phrasing")
        else:  # newbie
            if long_ratio > 0.12:
                score -= 1; why.append("a lot of long, heavy words")
            if caps >= 4:
                score -= 1; why.append("many names/terms with no explanation")
            if avg_len > 28:
                score -= 1; why.append("sentences too long to follow easily")
            if avg_len <= 16 and long_ratio < 0.08:
                score += 1; why.append("short, plain sentences")
            if re.search(r"\([^)]*\)|\b[A-Z]{3,}\b", text):
                score -= 1; why.append("acronyms/asides assume prior knowledge")

        score = max(0, min(10, score + jitter))
        band = _band(score)

        # Evidence: always a real sentence (or prefix of one) from THIS segment.
        def pick(pred=None, fallback=None):
            if pred:
                for s in sents:
                    if pred(s):
                        return s
            return fallback if fallback is not None else sents[0]

        longest = max(sents, key=len)
        if key == "doom":
            ev = longest if n > 60 else sents[0]
        elif key == "critic":
            ev = pick(lambda s: any(c in s.lower() for c in cliches) if cliches else False,
                      pick(lambda s: any(w in s.split() for w in adverbs) if adverbs else False, longest))
        elif key == "fan":
            ev = max(sents, key=lambda s: sum(1 for w in s.split()[1:] if w[:1].isupper())) if caps else pick(lambda s: '"' in s or "“" in s)
        else:
            ev = max(sents, key=lambda s: sum(1 for w in _WORD.findall(s) if len(w) >= 9) + sum(1 for w in s.split()[1:] if w[:1].isupper()))

        thoughts = _THOUGHTS[key][band]
        reason = "Demo heuristic: " + ("; ".join(why) if why else "nothing stood out in either direction") + "."
        return {
            "engagement_score": score,
            "emotion": _EMOTION[key][band],
            "inner_thought": thoughts[seed % len(thoughts)],
            "would_continue": score >= _CONTINUE_AT[key],
            "evidence": _clip(ev),
            "reason": reason,
        }
