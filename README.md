# Factora — Autonomous Factory Operating System

**neatHack 2026 submission (fresh implementation)**

Factora is an autonomous factory operating system built around a digital twin and cooperating AI
agents. Agents observe simulated factory telemetry, investigate anomalies, coordinate decisions,
take controlled actions, and verify the factory actually improved — every step traced.

**Status: Milestone N3 — autonomous CNC-03 maintenance incident response.** A SQLite-backed simulated factory
(23 machines, telemetry, production, parts, work orders, incidents) with a simulation clock and
reset/advance demo controls, a browser 3D floor at `/twin` (and a Command Center at `/`)
driven entirely by the backend, and a real autonomous loop: when CNC-03 goes CRITICAL, a Factory
Watcher escalates, a Coordinator assigns the Maintenance Agent, which investigates with real
tools, containment executes (urgent work order + machine into MAINTENANCE + running job paused),
a separate deterministic verifier re-reads the world, and the run ends VERIFIED — traced by
neatlogs and displayed as a live timeline inside `/twin`. **No ML predictions, no finance agents yet** — see [PROGRESS.md](./PROGRESS.md).

## Fresh-code disclosure

The Factora concept, name and UI/UX design mockups predate neatHack (prior exploration:
https://github.com/khushi-infinity/Factora — used strictly as planning/design reference).
**All application code in this repository is written fresh during neatHack 2026.** No implementation
code was copied. See [docs/PROVENANCE.md](./docs/PROVENANCE.md).

## Stack

- **Frontend:** React 19 + Vite + TypeScript + Tailwind CSS 4, React Router, Recharts, three.js / React Three Fiber / Drei (Factory Digital Twin)
- **Backend:** FastAPI + Python 3.11 + Pydantic v3
- **Sponsors:** neatlogs (agent observability) · Entire (coding-session checkpoints) · cfo.ai (business-plan modelling)

## Sponsor roles

| Sponsor | Role in Factora |
|---|---|
| **neatlogs** | Runtime observability: every agent run, LLM call, tool call, handoff, failure, retry and verification step traced. Real runtime spans (WORKFLOW/AGENT/TOOL/CHAIN) in `backend/app/observability.py` + the agent modules. |
| **Entire** | Development-time checkpointing: agent sessions joined to Git commits, giving judges a verifiable build history. Enabled from the first commit. |
| **cfo.ai** | Business-plan modelling only (pricing, costs, revenue scenarios) for the submission material. Not a product runtime component. |

## Quick start

```bash
# Backend — FastAPI on :8000
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
# health: http://127.0.0.1:8000/api/health · factory: /api/factory

# Seed / inspect the deterministic factory world
python3.11 scripts/seed_local.py            # reset + seed + validate (add --verify for digest proof)
python3.11 scripts/run_demo_scenario.py     # print the CNC-03 degradation arc (no agents)
python3.11 scripts/run_agent_demo.py        # the N3 autonomous loop, headless (add --recovery for the failure/recovery arc)

# Frontend — Vite on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

The backend boots with **no credentials**. neatlogs tracing activates only when `NEATLOGS_API_KEY`
is set in the environment; without it the app runs normally with observability disabled.
Real-LLM mode activates only when `OPENROUTER_API_KEY` is set (`FACTORA_LLM_MODEL`, default
`openrouter/free`); without it the agents run on a clearly-labelled deterministic stand-in
(`DETERMINISTIC TEST MODE`) so tests and demos never need the internet.

## The autonomous loop (N3)

```text
DETECT      Watcher (deterministic, no LLM): critical incident on a CRITICAL machine
↓
INVESTIGATE Coordinator assigns the Maintenance Agent (1 model call)
↓           Maintenance Agent plans tool calls (1 model call), then fetches evidence itself:
↓           recent telemetry · prior bearing repairs · spare-part stock · open work orders ·
↓           running production job · the incident record
↓           then recommends from that evidence (1 model call) — structured Pydantic output
PLAN        Deterministic action policy decides what may run — the model proposes, code decides
↓
ACT         tools: create_maintenance_work_order (source AGENT) · place_machine_in_maintenance
↓           (containment also pauses the machine's RUNNING job; ids recorded)
↓           demo: first work-order call can fail deterministically → RECOVERING → retry once
VERIFY      separate deterministic verifier re-reads the world:
↓           machine_is_maintenance · work_order_created · action_recorded ·
↓           active_job_paused · incident_contained (RESOLVING)
VERIFIED    or FAILED / ESCALATED — every step persisted in agent_runs / agent_steps
```

Demo beat level: open `/twin`, select **CNC-03**, press **Advance +30 min** — the machine turns
amber → red with a one-shot pulse, the state distribution changes, and a deterministic incident
appears. In N3 the same press now triggers the watcher automatically: the "Factora is responding"
timeline plays the agent run, and CNC-03 settles into MAINTENANCE (blue/gray) with its job paused
and an AGENT-source work order; **Reset** restores the start. A single checkbox ("Demo recovery
scenario") makes the first work-order tool call fail so judges can watch the RECOVERING → retry
arc. Visual checklist: [docs/EVIDENCE/demo/manual-twin-checklist.md](./docs/EVIDENCE/demo/manual-twin-checklist.md).

## Tests

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

Demo beat level: open `/twin`, select **CNC-03**, press **Advance +30 min** — the watcher
escalates automatically; the timeline shows the investigation, the containment and the 5/5
verification, and the twin turns CNC-03 MAINTENANCE. **Reset** restores the start.

## Documents

- [PROGRESS.md](./PROGRESS.md) — live milestone state
- [AGENTS.md](./AGENTS.md) — operating rules for coding agents
- [docs/PROVENANCE.md](./docs/PROVENANCE.md) — fresh-code disclosure
- [docs/BUILD_LOG.md](./docs/BUILD_LOG.md) — milestone-by-milestone build record (judging evidence)
- [docs/EVIDENCE/demo/manual-twin-checklist.md](./docs/EVIDENCE/demo/manual-twin-checklist.md) — manual visual verification of `/twin`
- [docs/design/mockups/](./docs/design/mockups/) — the ten design reference screens
- [docs/BUSINESS_PLAN.md](./docs/BUSINESS_PLAN.md) — cfo.ai business plan (not yet modelled)
