# Brutal Audience

> Rehearse your audience before you meet them.

AI audience personas read your draft **one segment at a time**, react as they go, and show you where attention rises, collapses or splits. They never rewrite your work.

This repo is built in phases. Each phase is runnable on its own.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Scaffold, backend API, segmentation, SQLite, landing page, creative workspace | ✅ |
| 2 | Four personas, sequential simulation engine, validated JSON, LLM adapters, demo mode, live reading room | ✅ |
| 3 | Results dashboard, interactive heatmap, engagement chart, drop-offs, Audience Collision engine | ✅ |
| 4 | Brutal Verdict report, deployment config, final README | ✅ this zip |

## What works in Phases 3 and 4

- **Results dashboard.** When a run finishes, the reading room turns into a dashboard: summary cards (panel average, strongest, weakest, collisions), then everything below.
- **Interactive heatmap.** Personas are rows, segments are columns, colour is engagement, and a "Panel avg" row sits underneath. Click a cell for one reader, or a column number for all four. Column headers are marked ◆ for an audience collision and ▾ where somebody would stop; a dashed outline marks segments where two or more readers lost interest.
- **Engagement chart.** One line per persona plus the panel average across the piece; click a point to inspect that segment.
- **Segment by segment.** The passage with every persona's verbatim evidence highlighted, next to all four reactions.
- **Audience Collision engine** (`backend/app/analysis/stats.py`). A collision is a segment where personas differ by 4+ points, or by 3+ points while some would keep reading and some would stop. Each collision shows both sides and an explanation of why both can be reasonable. That explanation is built from the personas' own recorded reasons, not invented, and it frames the split as a trade-off about who the passage is for. It also lists drop-off points (each reader's first stop, grouped) and segments where the whole panel agreed.
- **Brutal Verdict** (`backend/app/analysis/verdict.py`). Overall response, strongest and weakest segment, drop-off points, what each persona liked and disliked, where the audience split, and three suggestions linked to exact segments with verbatim evidence.
  - The strongest/weakest segments, drop-offs and collisions are computed from the stored reactions. The model never supplies numbers.
  - Live mode: the model writes only the narrative. Its reply is validated with Pydantic: right number of suggestions, every persona covered, every cited segment ID must exist, and every quote must be a verbatim excerpt of a cited segment. Invalid replies are retried with a correction; a quote that still can't be verified is dropped, never shown.
  - The prompt forbids rewrites and replacement text. Suggestions say what to look at and decide. Nothing is applied to the draft.
  - Demo mode: assembled from the recorded reactions with plain templates, labelled "Demo verdict, not an AI audience" in the API and the UI.
  - Verdicts are stored in SQLite, can be regenerated, and can be copied as plain text.

## What works in Phase 2

- **Four distinct personas** (Doomscroller, Skeptical Critic, Genre Superfan, Casual Newcomer). Each has its own personality, criteria, scoring habits and voice in `backend/app/personas/definitions.py`. Prompts are assembled in `personas/prompts.py`.
- **Sequential simulation.** Every persona reads segment 1, then 2, then 3. Personas run in parallel with each other, but each one's own sequence stays strictly ordered.
- **No future leakage.** A persona's prompt contains only the current segment, segments it has already read, and its own earlier reactions. Tests inspect the actual prompt text to prove later segments never appear, and the prompt never reveals how many segments there are.
- **Structured, validated reactions.** Score 0–10, emotion, one-line inner thought, would-continue, evidence, reason. Replies are parsed (tolerating code fences), validated with Pydantic, retried with a correction message when invalid, and recorded as a failed reaction (never a crash) if they stay invalid.
- **No fabricated evidence.** The quoted evidence must be a verbatim excerpt of the segment being read. If the model keeps returning a quote that isn't in the text, the quote is dropped and the reaction is flagged unverified.
- **Providers.** Gemini and any OpenAI-style endpoint, behind one small interface (`backend/app/llm/`). Transient errors (429/5xx/timeouts) are retried with backoff; a bad key or model aborts the whole run immediately with a clear message instead of failing 100 times.
- **Demo mode** when no key is set. It uses plain text statistics, **not AI**, and says so in the API (`mode: "demo"`) and in a banner on every results page. Its evidence quotes are still real excerpts.
- **Reading room** (`/run/:id`): live progress, a lane per persona that fills in as they read, click any cell for the reaction, highlighted evidence and the passage, per-persona summary, and a stop button.
- Runs and reactions persist in SQLite. Deleting a submission deletes its runs. A server restart marks interrupted runs as failed rather than leaving them stuck.

## Not built (out of scope for the MVP)

- Cultural and accessibility analysis, Style Guardian, custom personas, debate mode, accounts/login (out of scope for the MVP).

## Run it

**Prerequisites:** Python 3.10+, Node 18+.

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

With no key the app runs in **demo mode**. To use real AI personas, edit `backend/.env`:

```
LLM_PROVIDER=gemini
LLM_API_KEY=your-key
LLM_MODEL=<a current model ID from Google AI Studio>
```

`LLM_MODEL` has no default on purpose, because model IDs get retired. (Use `LLM_PROVIDER=openai_compat` plus `LLM_BASE_URL` for OpenAI-style providers.) Check `GET /api/health`: `mode_default` shows `live` once both key and model are set.

Tests (85, no network or key needed):

```bash
cd backend && pytest -q
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. In dev, Vite proxies `/api` to port 8000.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | status, default mode, provider/model (never the key) |
| POST | `/api/segment` | stateless live segmentation preview |
| POST | `/api/upload` | extract text from .txt / .md / .docx |
| POST/GET/DELETE | `/api/submissions[/{id}]` | save / list / read / delete a work |
| POST | `/api/submissions/{id}/runs` | start a simulation `{mode: auto\|live\|demo}` |
| GET | `/api/runs/{id}` | status, progress, segments and every reaction so far (poll this) |
| POST | `/api/runs/{id}/cancel` | stop a running simulation |
| GET | `/api/runs/{id}/analysis` | per-segment stats, drop-offs, collisions, agreements (deterministic, safe mid-run) |
| POST/GET | `/api/runs/{id}/verdict` | generate (or regenerate) / fetch the Brutal Verdict; the run must be finished |

Interactive docs at <http://127.0.0.1:8000/docs>.

## Project layout

```
backend/app/
├── main.py  config.py  db.py  run_store.py  schemas.py
├── segmenter.py  file_parser.py
├── personas/        definitions.py (the 4 personas)  prompts.py (prompt assembly)
├── llm/             base.py  gemini.py  openai_compat.py  factory.py
├── simulation/      engine.py  backends.py (live + demo)  validation.py  types.py
├── analysis/        stats.py (collisions, drop-offs)  verdict.py  models.py
└── routes/          content.py  runs.py  analysis.py
backend/tests/       segmenter, API, validation, engine (incl. no-leak), adapters (mocked HTTP), analysis, verdict
frontend/src/
├── pages/           Landing  Workspace  RunPage
├── components/      SimulationPreview  SegmentInspector  PersonaLanes  ReactionDetail  ModeBanner
│                    Dashboard  Heatmap  EngagementChart  SegmentCompare  CollisionPanel  VerdictPanel
└── lib/             api.ts  useRun.ts  heat.ts  personas.ts
```

## Deploy

- **Backend → Render.** Create a Blueprint from this repo (`render.yaml`). Set `LLM_API_KEY`, `LLM_MODEL` and `CORS_ORIGINS` (your Vercel URL) in the Render dashboard.
- **Frontend → Vercel.** Root directory `frontend`; set `VITE_API_URL` to the Render URL (no trailing slash). `frontend/vercel.json` handles client-side routes.

## Honest limitations

- Simulated personas are an informed guess, not real readers; scores are subjective estimates.
- The Gemini and OpenAI-compatible adapters are tested against a mocked HTTP server (request shape, retries, errors), not against the live APIs, since that needs your key. The first real run is the real test.
- Concurrency is per run (4 personas at once). There is no global rate limiter, so heavy parallel use on a free API tier may hit 429s (they are retried with backoff).
- Render's free disk is ephemeral, so SQLite data resets on redeploy.
- Long works only keep the most recent ~6,000 characters of already-read text in each prompt. Earlier segments are carried through the persona's own reactions.
- Collision and drop-off thresholds (4-point gap, 3-point split, 3-or-lower for "lost interest") are sensible defaults, not validated measures. They are constants at the top of `analysis/stats.py`.
- The live Brutal Verdict has only been tested against a fake model client, like the adapters. The first real run is the real test.
- The browser flow (workspace → run → dashboard → verdict) was exercised end to end in demo mode only.
