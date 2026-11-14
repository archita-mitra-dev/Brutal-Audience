"""Brutal Audience API entrypoint.  Run: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, run_store
from .config import get_settings
from .routes import analysis, content, runs


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    run_store.fail_stale_runs()
    yield


app = FastAPI(title="Brutal Audience API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(content.router)
app.include_router(runs.router)
app.include_router(analysis.router)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "phase": 4,
        # Lets the frontend show "demo mode" later. Never returns the key itself.
        "llm_configured": s.llm_configured,
        "mode_default": "live" if s.llm_configured else "demo",
        "provider": s.llm_provider if s.llm_configured else None,
        "model": s.llm_model if s.llm_configured else None,
    }
