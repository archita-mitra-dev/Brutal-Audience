"""Simulation run endpoints. A run executes in the background; clients poll GET /runs/{id}."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from .. import db, run_store
from ..config import get_settings
from ..llm.factory import get_llm_client
from ..personas.definitions import PERSONAS
from ..schemas import (
    ChildRunSummary, ReactionOut, RevisionRequest, RunDetail, RunOut, RunRequest, SegmentOut, WhatIfRequest,
)
from ..segmenter import segment_content
from ..simulation.backends import DemoBackend, LiveBackend, ReactionBackend
from ..security import current_user
from ..simulation.engine import run_simulation

router = APIRouter(prefix="/api", tags=["simulation"], dependencies=[Depends(current_user)])

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


async def _execute(
    run_id: str, submission: dict, backend: ReactionBackend, stop: asyncio.Event, blind: bool = False
) -> None:
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
            blind=blind,
        )
    except Exception:  # never leave a run stuck in "running"
        status, error = "failed", "An unexpected error stopped the simulation."
    run_store.set_status(run_id, status, error)
    _active.pop(run_id, None)


def _detail(run_id: str, user_id: str) -> RunDetail:
    d = run_store.get_run_detail(run_id)
    if d is None or not run_store.run_belongs_to(run_id, user_id):
        raise HTTPException(404, "Run not found.")
    segs = [SegmentOut(**s, word_count=len(s["text"].split())) for s in d["segments"]]
    return RunDetail(**{**d, "segments": segs})


@router.post("/submissions/{sub_id}/runs", response_model=RunOut, status_code=201)
async def start_run(sub_id: str, req: RunRequest | None = None, user: dict = Depends(current_user)) -> RunOut:
    sub = db.get_owned_submission(sub_id, user["id"])
    if sub is None:
        raise HTTPException(404, "Submission not found.")
    req = req or RunRequest()
    backend = _resolve_backend(req.mode)
    total = len(sub["segments"]) * len(PERSONAS)
    run = run_store.create_run(sub_id, backend.mode, backend.label, total, blind=req.blind)

    stop = asyncio.Event()
    task = asyncio.create_task(_execute(run["id"], sub, backend, stop, blind=req.blind))
    _active[run["id"]] = (stop, task)
    return RunOut(**run)


def _launch_child(baseline_id: str, user: dict, content: str, *, kind: str, label: str | None, title: str | None) -> RunOut:
    """Simulate an edited version of a finished run's draft, like for like.

    The child run reuses the baseline's mode and blind setting, so the comparison never mixes a demo
    run with a live one or a blind run with an unblind one. The original draft is never modified: the
    edited text is stored as a separate submission (hidden from the draft list for a what-if).
    """
    base = run_store.get_run(baseline_id)
    if base is None or not run_store.run_belongs_to(baseline_id, user["id"]):
        raise HTTPException(404, "Run not found.")
    if base["status"] != "completed":
        raise HTTPException(409, "Finish the original simulation before testing a change to it.")
    if base["kind"] != "standard":
        raise HTTPException(409, "Test changes against an original run, not against another revision or experiment.")
    orig = db.get_owned_submission(base["submission_id"], user["id"])
    if orig is None:
        raise HTTPException(404, "The original draft no longer exists.")
    if content.strip() == orig["content"].strip():
        raise HTTPException(422, "That text is identical to the original, so there is nothing to compare.")
    max_chars = get_settings().max_content_chars
    if len(content) > max_chars:
        raise HTTPException(413, f"Content is {len(content):,} characters; the limit is {max_chars:,}.")

    from ..schemas import ContentType
    ctype = ContentType(orig["content_type"])
    segments, _ = segment_content(content, ctype, get_settings().max_segments)
    if not segments:
        raise HTTPException(422, "Nothing to test: the content is empty.")
    backend = _resolve_backend(base["mode"])
    default_title = f"{orig['title']} (v2)" if kind == "revision" else f"{orig['title']} (what if)"
    sub = db.create_submission(user["id"], (title or "").strip() or default_title, ctype, content, segments,
                               hypothetical=(kind == "whatif"))
    blind = bool(base["blind"])
    run = run_store.create_run(sub["id"], backend.mode, backend.label, len(segments) * len(PERSONAS),
                               blind=blind, baseline_run_id=baseline_id, kind=kind, label=label)
    stop = asyncio.Event()
    task = asyncio.create_task(_execute(run["id"], sub, backend, stop, blind=blind))
    _active[run["id"]] = (stop, task)
    return RunOut(**run)


@router.post("/runs/{run_id}/revisions", response_model=RunOut, status_code=201)
async def start_revision(run_id: str, req: RevisionRequest, user: dict = Depends(current_user)) -> RunOut:
    """Revision Impact Tracker: submit version 2 and read it with the same audience, in the same mode."""
    return _launch_child(run_id, user, req.content, kind="revision", label=None, title=req.title)


@router.post("/runs/{run_id}/whatif", response_model=RunOut, status_code=201)
async def start_whatif(run_id: str, req: WhatIfRequest, user: dict = Depends(current_user)) -> RunOut:
    """What If?: simulate a hypothetical edit. The original draft and its results stay untouched."""
    return _launch_child(run_id, user, req.content, kind="whatif", label=req.hypothesis.strip(), title=None)


@router.get("/runs/{run_id}/children", response_model=list[ChildRunSummary])
def list_children(run_id: str, user: dict = Depends(current_user)):
    if not run_store.run_belongs_to(run_id, user["id"]):
        raise HTTPException(404, "Run not found.")
    return [c for c in run_store.list_children(run_id) if c["kind"] in ("revision", "whatif")]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, user: dict = Depends(current_user)) -> RunDetail:
    return _detail(run_id, user["id"])


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: str, user: dict = Depends(current_user)) -> RunOut:
    run = run_store.get_run(run_id)
    if run is None or not run_store.run_belongs_to(run_id, user["id"]):
        raise HTTPException(404, "Run not found.")
    active = _active.get(run_id)
    if active is None:
        raise HTTPException(409, f"This run is already {run['status']}.")
    active[0].set()
    return RunOut(**run)
