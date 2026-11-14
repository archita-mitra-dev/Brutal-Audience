"""SQLite persistence (stdlib sqlite3 — no ORM, to keep the MVP light).

Phase 1 stores submissions + their segments. Later phases add simulation runs,
reactions and verdicts using the same `init_db()` pattern (CREATE IF NOT EXISTS).
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from .config import get_settings
from .schemas import ContentType, Segment

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    submission_id TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    seg_id        INTEGER NOT NULL,
    label         TEXT NOT NULL,
    text          TEXT NOT NULL,
    char_start    INTEGER NOT NULL,
    char_end      INTEGER NOT NULL,
    PRIMARY KEY (submission_id, seg_id)
);

CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    mode          TEXT NOT NULL,
    model         TEXT NOT NULL,
    status        TEXT NOT NULL,
    total_steps   INTEGER NOT NULL,
    done_steps    INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    created_at    TEXT NOT NULL,
    finished_at   TEXT
);

CREATE TABLE IF NOT EXISTS reactions (
    run_id            TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    persona           TEXT NOT NULL,
    segment_id        INTEGER NOT NULL,
    status            TEXT NOT NULL,
    engagement_score  INTEGER,
    emotion           TEXT,
    inner_thought     TEXT,
    would_continue    INTEGER,
    evidence          TEXT,
    evidence_verified INTEGER NOT NULL DEFAULT 0,
    reason            TEXT,
    error             TEXT,
    attempts          INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id, persona, segment_id)
);

CREATE TABLE IF NOT EXISTS verdicts (
    run_id     TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")  # readers (polling) don't block the writer
        conn.executescript(SCHEMA)


def create_submission(
    title: str, content_type: ContentType, content: str, segments: list[Segment]
) -> dict:
    sub_id = uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO submissions (id, title, content_type, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sub_id, title, content_type.value, content, created_at),
        )
        conn.executemany(
            "INSERT INTO segments (submission_id, seg_id, label, text, char_start, char_end) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(sub_id, s.id, s.label, s.text, s.char_start, s.char_end) for s in segments],
        )
    return get_submission(sub_id)  # type: ignore[return-value]


def get_submission(sub_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
        if row is None:
            return None
        segs = conn.execute(
            "SELECT seg_id AS id, label, text, char_start, char_end "
            "FROM segments WHERE submission_id = ? ORDER BY seg_id",
            (sub_id,),
        ).fetchall()
    return {**dict(row), "segments": [dict(s) for s in segs]}


def list_submissions() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT s.id, s.title, s.content_type, s.created_at, "
            "(SELECT COUNT(*) FROM segments g WHERE g.submission_id = s.id) AS segment_count "
            "FROM submissions s ORDER BY s.created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_submission(sub_id: str) -> bool:
    """Users own their data: deleting a submission removes its segments too."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM submissions WHERE id = ?", (sub_id,))
        return cur.rowcount > 0
