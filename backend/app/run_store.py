"""SQLite persistence for simulation runs and their reactions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .db import connect, get_submission
from .personas.definitions import PERSONAS, PERSONAS_BY_KEY
from .schemas import ReactionOut

_ORDER = {p.key: i for i, p in enumerate(PERSONAS)}
TERMINAL = {"completed", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_run(
    submission_id: str, mode: str, model: str, total_steps: int, blind: bool = False,
    baseline_run_id: str | None = None, kind: str = "standard", label: str | None = None,
) -> dict:
    run_id = uuid.uuid4().hex[:12]
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, submission_id, mode, model, status, total_steps, blind, "
            "baseline_run_id, kind, label, created_at) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)",
            (run_id, submission_id, mode, model, total_steps, int(blind), baseline_run_id, kind, label, _now()),
        )
    return get_run(run_id)  # type: ignore[return-value]


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def set_status(run_id: str, status: str, error: str | None = None) -> None:
    finished = _now() if status in TERMINAL else None
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, error = COALESCE(?, error), finished_at = COALESCE(?, finished_at) "
            "WHERE id = ?",
            (status, error, finished, run_id),
        )


def add_reaction(run_id: str, r: ReactionOut) -> None:
    """Persist one reaction and bump progress (so pollers see the run advance live)."""
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reactions (run_id, persona, segment_id, status, engagement_score, "
            "emotion, inner_thought, would_continue, evidence, evidence_verified, reason, error, attempts, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "(SELECT COALESCE(MAX(seq), 0) + 1 FROM reactions WHERE run_id = ?))",
            (
                run_id, r.persona, r.segment_id, r.status, r.engagement_score, r.emotion,
                r.inner_thought,
                None if r.would_continue is None else int(r.would_continue),
                r.evidence, int(r.evidence_verified), r.reason, r.error, r.attempts,
                run_id,
            ),
        )
        conn.execute("UPDATE runs SET done_steps = done_steps + 1 WHERE id = ?", (run_id,))


def get_reactions(run_id: str) -> list[ReactionOut]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reactions WHERE run_id = ?", (run_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        out.append(
            ReactionOut(
                persona=d["persona"],
                persona_name=PERSONAS_BY_KEY[d["persona"]].name,
                segment_id=d["segment_id"],
                status=d["status"],
                engagement_score=d["engagement_score"],
                emotion=d["emotion"],
                inner_thought=d["inner_thought"],
                would_continue=None if d["would_continue"] is None else bool(d["would_continue"]),
                evidence=d["evidence"],
                evidence_verified=bool(d["evidence_verified"]),
                reason=d["reason"],
                error=d["error"],
                attempts=d["attempts"],
                seq=d.get("seq"),
            )
        )
    out.sort(key=lambda x: (_ORDER.get(x.persona, 99), x.segment_id))
    return out


def get_run_detail(run_id: str) -> dict | None:
    run = get_run(run_id)
    if run is None:
        return None
    sub = get_submission(run["submission_id"])
    if sub is None:
        return None
    return {
        **run,
        "title": sub["title"],
        "content_type": sub["content_type"],
        "segments": sub["segments"],
        "reactions": get_reactions(run_id),
    }


def fail_stale_runs() -> int:
    """Runs left 'queued'/'running' by a previous process can never finish; mark them."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE runs SET status = 'failed', error = 'The server restarted during this run.', "
            "finished_at = ? WHERE status IN ('queued', 'running')",
            (_now(),),
        )
        return cur.rowcount


def save_verdict(run_id: str, payload_json: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO verdicts (run_id, payload, created_at) VALUES (?, ?, ?)",
            (run_id, payload_json, _now()),
        )


def get_verdict_json(run_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM verdicts WHERE run_id = ?", (run_id,)).fetchone()
    return row["payload"] if row else None


def run_belongs_to(run_id: str, user_id: str) -> bool:
    """Ownership comes from the submission the run was made from."""
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM runs r JOIN submissions s ON s.id = r.submission_id "
            "WHERE r.id = ? AND s.user_id = ?", (run_id, user_id),
        ).fetchone()
    return row is not None


def list_children(baseline_run_id: str) -> list[dict]:
    """Revisions and what-if experiments made from a baseline run, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, label, status, created_at, finished_at FROM runs "
            "WHERE baseline_run_id = ? ORDER BY created_at DESC", (baseline_run_id,),
        ).fetchall()
    return [dict(r) for r in rows]
