# Factora — Autonomous Factory Operating System

**neatHack 2026 submission (fresh implementation)**

Factora is an autonomous factory operating system built around a digital twin and cooperating AI
agents. Agents observe simulated factory telemetry, investigate anomalies, coordinate decisions,
take controlled actions, and verify the factory actually improved — every step traced.

**Status: Milestone N0 — fresh scaffold.** Health endpoint + frontend shell + sponsor foundations
only. No factory simulation, no agents, no ML, no product pages yet — see [PROGRESS.md](./PROGRESS.md).

## Fresh-code disclosure

The Factora concept, name and UI/UX design mockups predate neatHack (prior exploration:
https://github.com/khushi-infinity/Factora — used strictly as planning/design reference).
**All application code in this repository is written fresh during neatHack 2026.** No implementation
code was copied. See [docs/PROVENANCE.md](./docs/PROVENANCE.md).

## Stack

- **Frontend:** React 19 + Vite + TypeScript + Tailwind CSS 4 (+ Recharts, three.js / React Three Fiber installed for later milestones)
- **Backend:** FastAPI + Python 3.11 + Pydantic v3
- **Sponsors:** neatlogs (agent observability) · Entire (coding-session checkpoints) · cfo.ai (business-plan modelling)

## Sponsor roles

| Sponsor | Role in Factora |
|---|---|
| **neatlogs** | Runtime observability: every agent run, LLM call, tool call, handoff, failure, retry and verification step traced. Foundation initialized in `backend/app/observability.py`. |
| **Entire** | Development-time checkpointing: agent sessions joined to Git commits, giving judges a verifiable build history. Enabled from the first commit. |
| **cfo.ai** | Business-plan modelling only (pricing, costs, revenue scenarios) for the submission material. Not a product runtime component. |

## Quick start

```bash
# Backend — FastAPI on :8000
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
# health: http://127.0.0.1:8000/api/health

# Frontend — Vite on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

The backend boots with **no credentials**. neatlogs tracing activates only when `NEATLOGS_API_KEY`
is set in the environment; without it the app runs normally with observability disabled.

## Tests

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

## Documents

- [PROGRESS.md](./PROGRESS.md) — live milestone state
- [AGENTS.md](./AGENTS.md) — operating rules for coding agents
- [docs/PROVENANCE.md](./docs/PROVENANCE.md) — fresh-code disclosure
- [docs/BUILD_LOG.md](./docs/BUILD_LOG.md) — milestone-by-milestone build record (judging evidence)
- [docs/design/mockups/](./docs/design/mockups/) — the ten design reference screens
- [docs/BUSINESS_PLAN.md](./docs/BUSINESS_PLAN.md) — cfo.ai business plan (not yet modelled)
