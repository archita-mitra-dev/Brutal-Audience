"""Prompt construction for live (LLM) reactions. Kept apart from the engine so
prompts can be tuned without touching control flow."""
from __future__ import annotations

from ..simulation.types import ReactionRequest
from .definitions import Persona

EMOTIONS = (
    "bored", "confused", "curious", "amused", "moved", "excited", "frustrated",
    "surprised", "skeptical", "indifferent", "delighted", "tense", "disappointed", "unsettled",
)

# How much already-read text a persona is shown verbatim. Older segments beyond
# this budget are dropped from the prompt (the persona still "remembers" them via
# its own reactions). Bounded context keeps cost and latency flat for long works.
MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_ITEMS = 14

_SHARED_RULES = f"""\
You are simulating ONE member of an audience experiencing a creative work for the first time, one segment at a time.

HARD RULES
- You are an AUDIENCE MEMBER, not an editor or co-writer. Never rewrite, rephrase, "fix" or suggest replacement text. Describe how the work lands on you and why.
- You only know what you have been shown so far. You do not know what happens next; never guess at or refer to later parts.
- Stay in character. Your reaction must differ from what a generic reviewer would say; react from YOUR taste.
- Be honest, specific and constructive. No flattery, no filler. Use the whole 0-10 scale: 5 is "fine, unremarkable"; most segments should land between 2 and 8.
- "evidence" must be an EXACT, word-for-word quote (max 200 characters) copied from the segment you are reading NOW. Do not quote earlier segments. Do not paraphrase. Do not invent text.
- "reason" must name what in the text caused your reaction. Do not write generic advice like "improve the writing".

OUTPUT: a single JSON object and nothing else (no markdown, no code fences), with exactly these keys:
{{
  "engagement_score": <integer 0-10>,
  "emotion": <one of: {", ".join(EMOTIONS)}>,
  "inner_thought": <one sentence, first person, in your voice, max 25 words>,
  "would_continue": <true or false: would you keep reading after this segment?>,
  "evidence": <exact quote from the CURRENT segment, max 200 characters>,
  "reason": <1-2 sentences explaining the reaction, pointing at what in the text caused it>
}}"""


def build_system_prompt(p: Persona) -> str:
    bullets = lambda items: "\n".join(f"- {i}" for i in items)  # noqa: E731
    return (
        f"{_SHARED_RULES}\n\n"
        f"YOUR PERSONA: {p.name} — {p.tagline}\n"
        f"{p.personality}\n\n"
        f"WHAT YOU NOTICE\n{bullets(p.criteria)}\n\n"
        f"HOW YOU SCORE ENGAGEMENT\n{bullets(p.scoring)}\n\n"
        f"YOUR VOICE\n{p.voice}\n\n"
        f"WHEN YOU STOP READING\n{p.quits_when}\n\n"
        f"Emotions you most often feel: {', '.join(p.typical_emotions)} (you may use any allowed emotion)."
    )


def _seen_block(req: ReactionRequest) -> str:
    """Already-read segments, newest first within budget, then restored to reading order."""
    if not req.seen:
        return "(Nothing yet — this is the very first thing you are reading.)"
    kept, used = [], 0
    for seg in reversed(req.seen):
        if used + len(seg.text) > MAX_CONTEXT_CHARS and kept:
            break
        kept.append(seg)
        used += len(seg.text)
    kept.reverse()
    omitted = req.seen[0].id != kept[0].id
    head = (
        f"[Segments {req.seen[0].id}-{kept[0].id - 1} were read earlier; their text is omitted "
        f"for length. You remember them through your own reactions below.]\n\n"
        if omitted else ""
    )
    return head + "\n\n".join(f"[Segment {s.id}]\n{s.text}" for s in kept)


def _history_block(req: ReactionRequest) -> str:
    if not req.history:
        return "(None yet.)"
    lines = []
    for h in req.history[-MAX_HISTORY_ITEMS:]:
        if h.score is None:
            lines.append(f"- Segment {h.segment_id}: (no reaction recorded)")
        else:
            cont = "would keep reading" if h.would_continue else "would stop here"
            lines.append(f'- Segment {h.segment_id}: {h.score}/10, {h.emotion}, {cont} — "{h.thought}"')
    return "\n".join(lines)


def _already_left(req: ReactionRequest) -> str:
    left = [h for h in req.history if h.would_continue is False]
    if not left:
        return ""
    return (
        f"\nNOTE: After segment {left[0].segment_id} you said you would stop reading. You are still "
        "going on for the sake of this test, so react as someone who has already lost faith in the "
        "work and is reading on reluctantly. A genuinely strong segment can still win you back.\n"
    )


def build_user_prompt(req: ReactionRequest) -> str:
    # Title and content type are what any real reader sees on the cover; they carry no
    # unseen text, so they are safe to include.
    # Blind Audience Test: an empty title means the creator's title is withheld.
    name = f'"{req.title}"' if req.title.strip() else "Untitled"
    prompt = (
        f"WORK: {name} (type: {req.content_type})\n\n"
        f"=== WHAT YOU HAVE ALREADY READ ===\n{_seen_block(req)}\n\n"
        f"=== YOUR OWN EARLIER REACTIONS ===\n{_history_block(req)}\n"
        f"{_already_left(req)}\n"
        f"=== YOU ARE NOW READING: SEGMENT {req.current.id} ===\n{req.current.text}\n"
        f"=== END OF SEGMENT {req.current.id} ===\n\n"
        "React to Segment "
        f"{req.current.id} as {req.persona.name}. Reply with the JSON object only."
    )
    if req.correction:
        prompt += f"\n\nYOUR PREVIOUS REPLY WAS REJECTED: {req.correction}"
    return prompt
