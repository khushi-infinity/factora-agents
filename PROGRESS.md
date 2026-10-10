# PROGRESS.md — Factora (neatHack 2026) Build State

**Hackathon:** neatHack 2026
**Current milestone:** N0
**Current goal:** fresh repository + sponsor foundations + green scaffold
**Repo:** local `/Users/khushisarawagi/Desktop/factora-agents` (GitHub push pending — see Blockers)
**Rule:** update this file (and `docs/BUILD_LOG.md`) at the end of every completed milestone.

---

## Completed

### N0 — fresh repository + sponsor foundations + green scaffold ✅

- [x] **Fresh Git repository** `/Users/khushisarawagi/Desktop/factora-agents` — brand-new history,
      not a branch/worktree/copy of the old Factora repo. Old repo untouched.
- [x] **Design references preserved**: the ten mockup images copied byte-identical into
      `docs/design/mockups/` (sha256 spot-check matched source); no old implementation code,
      docs or playbook text copied. `docs/PROVENANCE.md` states the disclosure.
- [x] **Backend scaffold (fresh)**: FastAPI app factory, `GET /api/health` + `GET /api/health/live`,
      CORS for the Vite dev origin, typed settings that boot with zero credentials.
      No database, no agents, no ML — by design at N0.
- [x] **neatlogs foundation (verified against docs.neatlogs.com on 2026-10-10)**: isolated module
      `backend/app/observability.py`; `neatlogs.init()` runs at FastAPI lifespan startup **only when
      `NEATLOGS_API_KEY` is present**; missing key → status `disabled`, app runs normally; init
      failure → status `error` surfaced in `/api/health` as `degraded`, never a crash (rule: an
      observability outage must not take the product down). `flush()` + `shutdown()` on server stop
      per the SDK docs. No fake agent spans (agents do not exist yet).
      SDK verified with `python -m neatlogs doctor --local --json` → **pass** (v1.4.26, doctor/v2).
- [x] **Frontend scaffold (fresh)**: React 19 + Vite + TS strict + Tailwind 4; design tokens from
      the mockups bootstrapped in `index.css`; minimal navy-sidebar shell calling `/api/health`
      through the dev proxy; honest "N0 scaffold — 0 / 10 pages" note; no twin, no product pages.
- [x] **Toolchains installed**: Recharts, three, @react-three/fiber, @react-three/drei present for
      later milestones (unused at N0 — verified they install, not that pages exist).
- [x] **Entire CLI installed + initialised** in the repo (version 0.10.5; setup commands recorded in
      `docs/EVIDENCE/entire/README.md`).
- [x] **All gates green**: backend `ruff` + **24 pytest passed**; frontend typecheck + lint + **4
      vitest passed** + production build. Repo-wide grep confirms **no Snowflake / Cortex / CoCo
      references in app code or docs** (only PROVENANCE.md mentions them as history).
- [x] **Fresh root docs**: README.md, AGENTS.md, PROGRESS.md, BUILD_LOG.md, BUSINESS_PLAN.md
      (placeholder, `NOT YET MODELLED IN CFO.AI`), `.env.example`, `.gitignore`, LICENSE (MIT).
- [x] **First commit** made on `main`.

---

## In Progress

- **GitHub push** (see Blockers) — local commit exists; remote creation is a single command.

## Next 3 (do NOT start without instruction)

1. **N1 — deterministic FactoryWorld + SQLite + fresh factory data.** Simulation tick loop, machines,
   telemetry, maintenance history, parts, production; deterministic seeding; first `/api/world`
   endpoints. New CNC-03-equivalent anomaly script written fresh.
2. **N2 — digital twin + operational APIs / UI foundation.** The 3D/2.5D twin page, machine state
   colours, `/api` operational surfaces feeding it.
3. **N3 — first autonomous detect → investigate → act → verify loop.** Agent runtime + neatlogs
   instrumented spans + Watcher/Coordinator/Maintenance minimum viable loop.

## Blockers

- **GitHub repository creation**: `gh` CLI is authenticated (account `khushi-infinity`), but the
  remote was deliberately **not** created during N0 to keep the first commit scope clean. Create +
  push with:
  ```bash
  cd /Users/khushisarawagi/Desktop/factora-agents
  gh repo create khushi-infinity/factora-agents --public --source . --push
  ```
- **neatlogs API key not yet supplied** — probe mode (`doctor --probe`) and real traces remain
  unverified until a project key is provided in `.env` (gitignored). Local doctor passes; the app
  boots with observability disabled. *Not blocking any planned work.*

## Test Status

| Gate | State | Evidence |
|---|---|---|
| Backend lint | ✅ | `cd backend && .venv/bin/ruff check .` → All checks passed! |
| Backend tests | ✅ | `cd backend && .venv/bin/pytest` → **24 passed**, 1 warning (Starlette httpx2 advisory) |
| Frontend typecheck | ✅ | `npm run typecheck` → no findings |
| Frontend lint | ✅ | `npm run lint` → no findings |
| Frontend tests | ✅ | `npm test` → **4 passed** (2 files) |
| Frontend build | ✅ | `npm run build` → built in ~110 ms, three.js in separate vendor chunk |
| neatlogs SDK doctor (local) | ✅ | `python -m neatlogs doctor --local --json` → pass, v1.4.26, doctor/v2, schema 2 |
| neatlogs doctor (probe) | ⏳ | awaits NEATLOGS_API_KEY |
| Snowflake/Cortex/CoCo grep | ✅ | 0 matches in app code/docs (PROVENANCE.md historical mention only) |
| Entire initialised | ✅ | `entire status` → active, hooks installed (see docs/EVIDENCE/entire/README.md) |

## Sponsor Status

| Sponsor | Status |
|---|---|
| neatlogs | ✅ foundation integrated + verified locally (doctor pass); probe/traces need a project key |
| Entire | ✅ CLI 0.10.5 installed, repo initialised, hooks wired; first checkpoint recorded in BUILD_LOG |
| cfo.ai | ⏳ not started by design — BUSINESS_PLAN.md is a placeholder (`NOT YET MODELLED IN CFO.AI`) |

## Demo Status

- **Not demo-able**: health check + shell only. First demo-able point: N1/N2 (world + twin).
- **Judge-ready point**: N7 per plan §K (deterministic flagship scenario + evidence pack).
