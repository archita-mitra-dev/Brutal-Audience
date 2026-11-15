"""Analysis (heatmap data, drop-offs, collisions) and Brutal Verdict endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import run_store
from ..analysis.compare import Comparison, compare
from ..analysis.models import Analysis, Verdict
from ..analysis.stats import analyse
from ..analysis.verdict import VerdictError, generate_demo, generate_live
from ..config import get_settings
from ..llm.base import LLMError
from ..llm.factory import get_llm_client
from ..security import current_user

router = APIRouter(prefix="/api", tags=["analysis"], dependencies=[Depends(current_user)])


def _load(run_id: str, user_id: str) -> tuple[dict, Analysis]:
    d = run_store.get_run_detail(run_id)
    if d is None or not run_store.run_belongs_to(run_id, user_id):
        raise HTTPException(404, "Run not found.")
    return d, analyse(run_id, d["status"], d["segments"], d["reactions"], d["total_steps"])


@router.get("/runs/{run_id}/analysis", response_model=Analysis)
def get_analysis(run_id: str, user: dict = Depends(current_user)) -> Analysis:
    """Cheap and deterministic, so the dashboard can call it freely (also mid-run)."""
    return _load(run_id, user["id"])[1]


@router.get("/runs/{run_id}/verdict", response_model=Verdict)
def get_verdict(run_id: str, user: dict = Depends(current_user)) -> Verdict:
    if not run_store.run_belongs_to(run_id, user["id"]):
        raise HTTPException(404, "Run not found.")
    raw = run_store.get_verdict_json(run_id)
    if raw is None:
        raise HTTPException(404, "No verdict has been generated for this run yet.")
    return Verdict.model_validate_json(raw)


@router.post("/runs/{run_id}/verdict", response_model=Verdict)
async def create_verdict(run_id: str, user: dict = Depends(current_user)) -> Verdict:
    d, analysis = _load(run_id, user["id"])
    if d["status"] not in run_store.TERMINAL:
        raise HTTPException(409, "The audience is still reading. Generate the verdict once the run has finished.")
    reactions = d["reactions"]
    if not any(r.status == "ok" for r in reactions):
        raise HTTPException(409, "There are no valid reactions to build a verdict from.")

    if d["mode"] == "demo":
        verdict = generate_demo(run_id=run_id, model=d["model"], segments=d["segments"],
                                reactions=reactions, analysis=analysis)
    else:
        client = get_llm_client(get_settings())
        if client is None:
            raise HTTPException(400, "This run used a live model, but LLM_API_KEY / LLM_MODEL are not set now.")
        try:
            verdict = await generate_live(
                client, run_id=run_id, title=d["title"], content_type=d["content_type"],
                segments=d["segments"], reactions=reactions, analysis=analysis,
            )
        except (LLMError, VerdictError) as exc:
            raise HTTPException(502, str(exc)) from exc

    run_store.save_verdict(run_id, verdict.model_dump_json())
    return verdict


@router.get("/runs/{run_id}/compare", response_model=Comparison)
def get_comparison(run_id: str, user: dict = Depends(current_user)) -> Comparison:
    """What changed between a revision (or what-if) and the original it was made from."""
    d, revised = _load(run_id, user["id"])
    if d["kind"] not in ("revision", "whatif") or not d["baseline_run_id"]:
        raise HTTPException(409, "This run is an original, so there is nothing to compare it with.")
    if d["status"] not in run_store.TERMINAL:
        raise HTTPException(409, "The audience is still reading the revised text.")
    if not run_store.run_belongs_to(d["baseline_run_id"], user["id"]):
        raise HTTPException(404, "The original run no longer exists.")
    b, baseline = _load(d["baseline_run_id"], user["id"])
    return compare(
        baseline=baseline, base_segments=b["segments"], revised=revised, rev_segments=d["segments"],
        baseline_run_id=d["baseline_run_id"], run_id=run_id, kind=d["kind"], label=d["label"],
    )
