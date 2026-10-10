# PROGRESS.md — Factora (neatHack 2026) Build State

**Hackathon:** neatHack 2026
**Current milestone:** N0 + N1 + N2 complete and pushed to `origin/main` (N1 = `7df8fbb`; N2 hash in `git log`)
**Current goal:** N3 — first autonomous detect → investigate → act → verify loop (awaiting instruction)
**Repo:** https://github.com/khushi-infinity/factora-agents
**Rule:** update this file (and `docs/BUILD_LOG.md`) at the end of every completed milestone.

---

## Completed

### N2 — operational APIs + visual Factory Digital Twin ✅

- [x] **`/twin` is a real visual twin, not a card wall.** React Three Fiber + Drei canvas occupies
      the main workspace; machines are placed from FactoryWorld `x_m/y_m/z_m` (no hardcoded
      positions), procedural box geometry per machine type, no downloaded models.
- [x] **Factory organisation**: one floor lane per production line (Assembly, CNC, Press,
      Packaging, Quality) with pastel tint + label, derived from where that line's machines
      actually are; a line rail above the canvas (`GET /api/factory/lines`) filters the floor.
- [x] **Interaction**: hover tooltip (id · state · health), click to select (blue ring + recoloured
      body), floor click clears selection, one-shot pulse when a machine's state changes.
- [x] **Machine Inspector** (right rail) from `GET /api/machines/{id}/context`: identity, latest
      telemetry, separate Recharts **vibration** and **temperature** trend charts (a shared axis
      would flatten vibration), economics labelled `Synthetic demo economics`, jobs, maintenance
      history, work orders, and any open incident prominently.
- [x] **CNC-03 flagship works end to end**: Reset → WARNING → Advance +30 min → **CRITICAL**,
      distribution 19/2/0/1/1 → 19/1/1/1/1, incident `INC-20261005-001` appears in a page-level
      incident strip and in the inspector; Reset restores the deterministic start — all without a
      page reload.
- [x] **Scenario controls**: Reset / +10 / +30 / +60 min only (the steps the backend supports),
      authoritative sim clock in the header — never the wall clock.
- [x] **Command Center (`/`)** secondary to the twin: machine count, state distribution, sim time,
      CNC-03 state, a "Needs attention" list of WARNING/CRITICAL machines, and links into `/twin`.
      No invented metrics.
- [x] **WebGL resilience**: capability probe + error boundary + `TwinFallback`, which renders the
      same FactoryWorld data as a per-line floor table if the canvas cannot start.
- [x] **New/kept endpoints** (typed, FactoryWorld-sourced, tested): `GET /api/factory/lines`,
      `GET /api/machines/{id}/context`, `/maintenance`, `/work-orders`, `/production`. The
      collection routes and `/context` now share one row-reader each so they cannot drift.
- [x] **Gates**: backend `ruff` clean + **61 tests**; frontend typecheck/lint clean, **21 tests
      (6 files)**, build OK; `seed_local.py --verify` determinism VERIFIED; demo scenario prints
      the WARNING→CRITICAL arc. No agents, no ML, no fake traces.

### N1 — deterministic FactoryWorld and local factory state ✅

- [x] **SQLite world layer (no ORM, FK-enforced)**: machines, capabilities, sensor_readings,
      production_jobs, maintenance_history, spare_parts, work_orders, downtime_events, incidents,
      actions, world_state, seed_audit — 23 machines, 3,312 telemetry rows, 16 production jobs,
      8 parts, 10 maintenance records, 4 work orders, 3 downtime events per seed.
- [x] **Determinism proved**: per-domain SHA-256 RNG streams, fixed epoch 2026-10-05 06:00
      (persisted clock, 10-min ticks, never the wall clock); reseed digest
      `76d28cc593b3` stable across `scripts/seed_local.py --verify` runs; test-pinned.
- [x] **CNC-03 flagship recreated fresh**: 24-h monotonic ramp vibration 2.4→≈5.0 mm/s,
      bearing temp 62→70.7 °C; seeded state WARNING so the live advance walks
      WARNING→CRITICAL and opens deterministic incident `INC-20261005-001` with an evidence
      pack (telemetry + 2 prior BRG-AX-17 repairs + stock 2 ≤ reorder 3).
- [x] **Economics**: downtime-loss, scrap-loss and type-restricted reroute feasibility as pure
      functions over stored demo economics (output/hour, cost/hour, margin per unit, scrap cost).
- [x] **FactoryWorld service API** (`get_factory_snapshot`, `get_machine`, `get_recent_telemetry`,
      `get_machine_history`, `get_spare_part`, `get_compatible_machines`, `get_open_work_orders`,
      `get_active_incidents`, `advance`, `reset_world`, `compute_downtime_loss`,
      `compute_scrap_loss`) — agents (N3) will call this, never SQL.
- [x] **API**: GET /api/factory · /api/machines · /api/machines/{id} · /api/machines/{id}/telemetry
      · /api/incidents · POST /api/demo/reset · POST /api/demo/advance — all typed, all tested.
- [x] **Frontend proof panel**: FactoryWorld snapshot (state distribution, sim clock, incidents)
      + Reset/Advance buttons in the existing design language; no twin visuals yet (N2).
- [x] **Gates**: backend ruff clean + **53 tests passed** (24 N0 + 18 world + 11 factory API);
      frontend typecheck/lint clean, **6 tests**, build OK; seed --verify determinism VERIFIED;
      live uvicorn smoke of all endpoints; zero Snowflake/Cortex/CoCo references; no LLM calls,
      no agents, no fabricated neatlogs traces.

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

- Nothing — N2 is complete. Waiting on explicit instruction to start N3.

## Next 3 (do NOT start without instruction)

1. **N3 — first autonomous detect → investigate → act → verify loop.** Agent runtime + neatlogs
   instrumented spans + Watcher/Coordinator/Maintenance minimum viable loop over the N1 world.
2. **N4 — production + finance agents, approvals, reroute flow** (per plan §K).
3. **N5+** — remaining pages and sponsor integrations per plan §K.

## Blockers

- ~~GitHub repository creation~~ **resolved at N0-close**: `khushi-infinity/factora-agents` is
  public on GitHub and N0+N1+N2 are pushed (`origin/main`).
- **neatlogs API key not yet supplied** — probe mode (`doctor --probe`) and real traces remain
  unverified until a project key is provided in `.env` (gitignored). Local doctor passes; the app
  boots with observability disabled. *Not blocking any planned work.*
- **No connected desktop browser in this environment** — the twin was verified through unit
  tests, the non-WebGL fallback render, and a live API smoke of the CNC-03 arc. Pixel-level
  visual verification is pending: run `docs/EVIDENCE/demo/manual-twin-checklist.md`.

## Test Status

| Gate | State | Evidence |
|---|---|---|
| Backend lint | ✅ | `cd backend && .venv/bin/ruff check .` → All checks passed! |
| Backend tests | ✅ | `cd backend && .venv/bin/pytest` → **61 passed**, 1 warning |
| Frontend typecheck | ✅ | `npm run typecheck` → no findings |
| Frontend lint | ✅ | `npm run lint` → no findings |
| Frontend tests | ✅ | `npm test` → **21 passed (6 files)** |
| Frontend build | ✅ | `npm run build` → built in ~511 ms |
| Determinism diff | ✅ | `git diff --check` → no whitespace errors |
| Seed determinism | ✅ | `python3.11 scripts/seed_local.py --verify` → Determinism: VERIFIED (digest 76d28cc593b3) │ CNC-03 scenario: VERIFIED │ Validation: PASS |
| Scenario runner | ✅ | `python3.11 scripts/run_demo_scenario.py` → T+30→T+120 walk, CNC-03 CRITICAL, incident INC-20261005-001 |
| Live API smoke (N2) | ✅ | uvicorn → `/api/factory/lines` 5 lines · `/api/machines/CNC-03/context` full inspector payload · advance 30 → 19/1/1/1/1 + incident · reset → 19/2/0/1/1, 0 incidents |
| Visual verification (browser) | ⏳ | no connected desktop browser in this environment — manual checklist at `docs/EVIDENCE/demo/manual-twin-checklist.md` |
| neatlogs SDK doctor (local) | ✅ | `python -m neatlogs doctor --local --json` → pass, v1.4.26, doctor/v2, schema 2 |
| neatlogs doctor (probe) | ⏳ | awaits NEATLOGS_API_KEY (unchanged; no fake traces — agents don't exist yet) |
| Snowflake/Cortex/CoCo grep | ✅ | 0 matches in app code/docs (PROVENANCE.md historical mention only) |
| Entire enabled | ✅ | `entire status` → Enabled · branch main; `entire checkpoint list` → **0 checkpoints** (recorded honestly) |

## Sponsor Status

| Sponsor | Status |
|---|---|
| neatlogs | ✅ foundation integrated + verified locally (doctor pass); probe/traces need a project key |
| Entire | ✅ CLI 0.10.5 installed, repo enabled on `main`, hooks wired for 8 agents; `entire checkpoint list` reports **0 checkpoints** so far |
| cfo.ai | ⏳ not started by design — BUSINESS_PLAN.md is a placeholder (`NOT YET MODELLED IN CFO.AI`) |

## Demo Status

- **Demo-able now (N2)**: `/` Command Center with live counts, `/twin` visual factory floor with
  23 machines on 5 labelled lines, hover/select/inspect with real telemetry and trend charts,
  Reset/+10/+30/+60 controls, and the CNC-03 WARNING → CRITICAL transition with a visible
  incident. `scripts/run_demo_scenario.py` prints the same arc headlessly.
- **Not demo-able yet**: no agents (N3), no ML predictions, no finance pages.
- **Judge-ready point**: N7 per plan §K (deterministic flagship scenario + evidence pack).
