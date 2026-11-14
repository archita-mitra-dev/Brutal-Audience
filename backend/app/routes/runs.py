"""Simulation run endpoints. A run executes in the background; clients poll GET /runs/{id}."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from .. import db, run_store
from ..config import get_settings
from ..llm.factory import get_llm_client
from ..personas.definitions import PERSONAS
from ..schemas import ReactionOut, RunDetail, RunOut, RunRequest, SegmentOut
from ..simulation.backends import DemoBackend, LiveBackend, ReactionBackend
from ..simulation.engine import run_simulation

router = APIRouter(prefix="/api", tags=["simulation"])

# In-process registry of active runs (stop events + task refs so tasks aren't GC'd).
_active: dict[str, tuple[asyncio.Event, asyncio.Task]] = {}


def _resolve_backend(mode: str) -> ReactionBackend:
    settings = get_settings()
    if mode == "demo":
        return DemoBackend()
    client = get_llm_client(settings)
    if client is None:
        if mode == "live":
            raise HTTPException(
                400,
                "Live mode needs LLM_API_KEY and LLM_MODEL in backend/.env. "
                "Use demo mode, or configure a key.",
            )
        return DemoBackend()  # auto
    return LiveBackend(client)


async def _execute(run_id: str, submission: dict, backend: ReactionBackend, stop: asyncio.Event) -> None:
    run_store.set_status(run_id, "running")

    def on_reaction(r: ReactionOut) -> None:
        run_store.add_reaction(run_id, r)

    try:
        status, error = await run_simulation(
            submission=submission,
            personas=PERSONAS,
            backend=backend,
            on_reaction=on_reaction,
            stop=stop,
            max_retries=get_settings().reaction_max_retries,
        )
    except Exception:  # never leave a run stuck in "running"
        status, error = "failed", "An unexpected error stopped the simulation."
    run_store.set_status(run_id, status, error)
    _active.pop(run_id, None)


def _detail(run_id: str) -> RunDetail:
    d = run_store.get_run_detail(run_id)
    if d is None:
        raise HTTPException(404, "Run not found.")
    segs = [SegmentOut(**s, word_count=len(s["text"].split())) for s in d["segments"]]
    return RunDetail(**{**d, "segments": segs})


@router.post("/submissions/{sub_id}/runs", response_model=RunOut, status_code=201)
async def start_run(sub_id: str, req: RunRequest | None = None) -> RunOut:
    sub = db.get_submission(sub_id)
    if sub is None:
        raise HTTPException(404, "Submission not found.")
    backend = _resolve_backend((req or RunRequest()).mode)
    total = len(sub["segments"]) * len(PERSONAS)
    run = run_store.create_run(sub_id, backend.mode, backend.label, total)

    stop = asyncio.Event()
    task = asyncio.create_task(_execute(run["id"], sub, backend, stop))
    _active[run["id"]] = (stop, task)
    return RunOut(**run)


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    return _detail(run_id)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: str) -> RunOut:
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found.")
    active = _active.get(run_id)
    if active is None:
        raise HTTPException(409, f"This run is already {run['status']}.")
    active[0].set()
    return RunOut(**run)
