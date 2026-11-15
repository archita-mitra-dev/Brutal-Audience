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
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id           TEXT PRIMARY KEY,
    user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content      TEXT NOT NULL,
    hypothetical INTEGER NOT NULL DEFAULT 0,
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
    blind         INTEGER NOT NULL DEFAULT 0,
    baseline_run_id TEXT,
    kind          TEXT NOT NULL DEFAULT 'standard',
    label         TEXT,
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
    seq               INTEGER,
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
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Upgrade databases created before accounts existed (Phase 1-4 databases).

    Old submissions get user_id NULL. They belong to nobody, so no account can open them.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(submissions)")}
    if "user_id" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN user_id TEXT REFERENCES users(id) ON DELETE CASCADE")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user ON submissions(user_id, created_at)")

    # Phase 6: the order reactions arrived in (Live Audience Theatre) and blind-test runs.
    rcols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)")}
    if "seq" not in rcols:
        conn.execute("ALTER TABLE reactions ADD COLUMN seq INTEGER")
    runcols = {r["name"] for r in conn.execute("PRAGMA table_info(runs)")}
    if "blind" not in runcols:
        conn.execute("ALTER TABLE runs ADD COLUMN blind INTEGER NOT NULL DEFAULT 0")

    # Phase 8: revisions and what-if experiments are runs that point at a baseline run.
    if "baseline_run_id" not in runcols:
        conn.execute("ALTER TABLE runs ADD COLUMN baseline_run_id TEXT")
    if "kind" not in runcols:
        conn.execute("ALTER TABLE runs ADD COLUMN kind TEXT NOT NULL DEFAULT 'standard'")
    if "label" not in runcols:
        conn.execute("ALTER TABLE runs ADD COLUMN label TEXT")
    scols = {r["name"] for r in conn.execute("PRAGMA table_info(submissions)")}
    if "hypothetical" not in scols:
        conn.execute("ALTER TABLE submissions ADD COLUMN hypothetical INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_baseline ON runs(baseline_run_id)")


# --- users -----------------------------------------------------------------------
def create_user(email: str, display_name: str, password_hash: str) -> dict | None:
    """Returns None when the email is already registered."""
    user_id = uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users (id, email, display_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, display_name, password_hash, created_at),
            )
    except sqlite3.IntegrityError:
        return None
    return get_user(user_id)


def get_user(user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    """Deletes the account and, through ON DELETE CASCADE, every draft, run, reaction and verdict."""
    with connect() as conn:
        return conn.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount > 0


def create_submission(
    user_id: str, title: str, content_type: ContentType, content: str, segments: list[Segment],
    hypothetical: bool = False,
) -> dict:
    sub_id = uuid.uuid4().hex[:12]
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO submissions (id, user_id, title, content_type, content, hypothetical, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sub_id, user_id, title, content_type.value, content, int(hypothetical), created_at),
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


def list_submissions(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT s.id, s.title, s.content_type, s.created_at, "
            "(SELECT COUNT(*) FROM segments g WHERE g.submission_id = s.id) AS segment_count "
            "FROM submissions s WHERE s.user_id = ? AND s.hypothetical = 0 ORDER BY s.created_at DESC LIMIT 50",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_submission(sub_id: str, user_id: str) -> bool:
    """Users own their data: deleting a submission removes its segments, runs and verdicts too."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM submissions WHERE id = ? AND user_id = ?", (sub_id, user_id))
        return cur.rowcount > 0


def get_owned_submission(sub_id: str, user_id: str) -> dict | None:
    """A submission, only if it belongs to this user (otherwise indistinguishable from missing)."""
    sub = get_submission(sub_id)
    return sub if sub and sub.get("user_id") == user_id else None
