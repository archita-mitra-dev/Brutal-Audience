"""Content segmentation.

Design rules
------------
1. Offset-preserving: every segment is an exact slice of the original string
   (`content[char_start:char_end]`). We never trim inside, re-wrap or
   normalise text, so the creator's work is preserved byte for byte.
2. Structure-aware: the split strategy depends on the content type.
3. Bounded: tiny fragments are merged forward and oversized blocks are split,
   so the later per-segment LLM calls stay a sensible size and count.
"""
from __future__ import annotations

import re

from .schemas import ContentType, Segment

# Tunables ------------------------------------------------------------------
MIN_SEGMENT_CHARS = 25      # merge only tiny fragments ("Hi.", one-word lines) forward
MAX_SEGMENT_CHARS = 1400    # split blocks longer than this on sentence bounds
LYRIC_FALLBACK_LINES = 4    # group size when lyrics have no blank-line stanzas

_SCENE_HEADING = re.compile(
    r"^\s*(?:\d+\s*[.)]?\s*)?(?:INT\.?|EXT\.?|INT\./EXT\.?|INT/EXT\.?|I/E\.?)\s+.+$",
    re.IGNORECASE | re.MULTILINE,
)
_BLANK_LINE_SPLIT = re.compile(r"\n[ \t]*\n+")
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"')\]]*\s+")

Span = tuple[int, int]


# Low-level span helpers ------------------------------------------------------
def _trim_span(content: str, start: int, end: int) -> Span | None:
    """Shrink a span so it excludes leading/trailing whitespace. None if empty."""
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return (start, end) if end > start else None


def _blank_line_blocks(content: str) -> list[Span]:
    """Spans of text separated by one or more blank lines."""
    spans: list[Span] = []
    cursor = 0
    for m in _BLANK_LINE_SPLIT.finditer(content):
        span = _trim_span(content, cursor, m.start())
        if span:
            spans.append(span)
        cursor = m.end()
    tail = _trim_span(content, cursor, len(content))
    if tail:
        spans.append(tail)
    return spans


def _split_long_span(content: str, span: Span, max_chars: int) -> list[Span]:
    """Split an oversized span on sentence boundaries (never mid-sentence unless
    a single sentence is itself longer than the limit)."""
    start, end = span
    if end - start <= max_chars:
        return [span]

    text = content[start:end]
    cut_points = [m.end() for m in _SENTENCE_END.finditer(text)]
    pieces: list[Span] = []
    piece_start = 0
    last_ok = None
    for cp in cut_points + [len(text)]:
        if cp - piece_start > max_chars and last_ok is not None:
            sub = _trim_span(content, start + piece_start, start + last_ok)
            if sub:
                pieces.append(sub)
            piece_start = last_ok
        last_ok = cp
    final = _trim_span(content, start + piece_start, end)
    if final:
        pieces.append(final)
    return pieces or [span]


def _merge_small(content: str, spans: list[Span], min_chars: int) -> list[Span]:
    """Merge fragments shorter than `min_chars` into the following span.
    The merged span covers the original text between them (including the gap),
    which keeps the slice-exactness guarantee."""
    merged: list[Span] = []
    carry_start: int | None = None
    for start, end in spans:
        if carry_start is not None:
            start = carry_start
            carry_start = None
        if end - start < min_chars:
            carry_start = start
            continue
        merged.append((start, end))
    if carry_start is not None:
        # trailing fragment: attach to previous span if any, else keep alone
        end = spans[-1][1]
        if merged:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((carry_start, end))
    return merged


# Strategy per content type ---------------------------------------------------
def _spans_prose(content: str) -> list[Span]:
    spans = _blank_line_blocks(content)
    # Some pasted text has single newlines between paragraphs and no blank lines.
    if len(spans) == 1 and content.count("\n") >= 3:
        line_spans = []
        pos = 0
        for line in content.split("\n"):
            sp = _trim_span(content, pos, pos + len(line))
            if sp:
                line_spans.append(sp)
            pos += len(line) + 1
        if len(line_spans) > 1:
            spans = line_spans
    spans = _merge_small(content, spans, MIN_SEGMENT_CHARS)
    out: list[Span] = []
    for sp in spans:
        out.extend(_split_long_span(content, sp, MAX_SEGMENT_CHARS))
    return out


def _spans_screenplay(content: str) -> list[Span]:
    headings = [m.start() for m in _SCENE_HEADING.finditer(content)]
    if not headings:
        # No sluglines: fall back to dialogue/action blocks.
        return _spans_prose(content)

    bounds = headings[:]
    spans: list[Span] = []
    # Anything before the first heading (title page / opening action) is kept.
    if bounds[0] > 0:
        pre = _trim_span(content, 0, bounds[0])
        if pre:
            spans.append(pre)
    for i, s in enumerate(bounds):
        e = bounds[i + 1] if i + 1 < len(bounds) else len(content)
        sp = _trim_span(content, s, e)
        if sp:
            spans.append(sp)

    out: list[Span] = []
    for sp in spans:
        if sp[1] - sp[0] <= MAX_SEGMENT_CHARS * 2:
            out.append(sp)
            continue
        # Long scene: split into blank-line blocks inside it, keep the slugline
        # attached to the first block.
        inner = [
            (sp[0] + a, sp[0] + b)
            for a, b in _blank_line_blocks(content[sp[0]:sp[1]])
        ]
        inner = _merge_small(content, inner, MIN_SEGMENT_CHARS)
        for isp in inner:
            out.extend(_split_long_span(content, isp, MAX_SEGMENT_CHARS))
    return out


def _spans_lyrics(content: str) -> list[Span]:
    stanzas = _blank_line_blocks(content)
    if len(stanzas) > 1:
        return stanzas
    # One big block: group every N non-empty lines.
    lines: list[Span] = []
    pos = 0
    for line in content.split("\n"):
        sp = _trim_span(content, pos, pos + len(line))
        if sp:
            lines.append(sp)
        pos += len(line) + 1
    spans: list[Span] = []
    for i in range(0, len(lines), LYRIC_FALLBACK_LINES):
        group = lines[i:i + LYRIC_FALLBACK_LINES]
        spans.append((group[0][0], group[-1][1]))
    return spans


_STRATEGIES = {
    ContentType.story: _spans_prose,
    ContentType.article: _spans_prose,
    ContentType.other: _spans_prose,
    ContentType.screenplay: _spans_screenplay,
    ContentType.lyrics: _spans_lyrics,
}

_LABELS = {
    ContentType.story: "Paragraph",
    ContentType.article: "Paragraph",
    ContentType.other: "Section",
    ContentType.screenplay: "Scene",
    ContentType.lyrics: "Stanza",
}


def segment_content(
    content: str,
    content_type: ContentType = ContentType.story,
    max_segments: int = 80,
) -> tuple[list[Segment], bool]:
    """Split `content` into ordered segments.

    Returns (segments, truncated). `truncated` is True when the work produced
    more than `max_segments` and the tail was left out to bound LLM cost.
    """
    if not content or not content.strip():
        return [], False

    spans = _STRATEGIES[content_type](content)
    truncated = len(spans) > max_segments
    spans = spans[:max_segments]

    label = _LABELS[content_type]
    segments = [
        Segment(
            id=i,
            label=f"{label} {i}",
            text=content[s:e],
            char_start=s,
            char_end=e,
        )
        for i, (s, e) in enumerate(spans, start=1)
    ]
    return segments, truncated
