# PROGRESS.md — Factora (neatHack 2026) Build State

**Hackathon:** neatHack 2026
**Current milestone:** N0–N3 complete and pushed to `origin/main` (`git log` for hashes)
**Current goal:** N4 — production + finance agents (awaiting instruction)
**Repo:** https://github.com/khushi-infinity/factora-agents
**Rule:** update this file (and `docs/BUILD_LOG.md`) at the end of every completed milestone.

---

## Completed

### N3 — autonomous CNC-03 maintenance incident response ✅

- [x] **Factory Watcher (deterministic, zero-LLM pre-filter)**: after every simulation advance it
      escalates only *critical* incidents whose machine is actually CRITICAL, with idempotency —
      one autonomous run per incident, ever. A healthy world costs zero model calls.
- [x] **Coordinator (Factory Brain, workflow in code — not in a prompt)**: persists `agent_runs` /
      `agent_steps`, enforces a code-level state machine
      `DETECTED→INVESTIGATING→PLANNING→ACTION_PENDING→ACTING→VERIFYING→RECOVERING→
      VERIFIED/FAILED/ESCALATED` (`models.ALLOWED_TRANSITIONS`; invalid transitions raise),
      asks the model only for structured decisions (Pydantic-validated, 1 repair attempt then
      escalate), applies the deterministic action policy, executes approved tools, contains the
      incident, and hands the result to a separate verifier.
- [x] **Maintenance Agent (only specialist)**: model call 1 picks a *tool plan*; it then fetches
      its own evidence (telemetry trend, prior bearing repairs, spare-part stock, open work
      orders, running job, incident record — nothing is injected wholesale); model call 2 returns
      a `MaintenanceAssessment` citing the numbers it retrieved.
- [x] **Typed tools (`backend/app/agents/tools.py`)**: read tools `get_machine`,
      `get_recent_telemetry`, `get_maintenance_history`, `get_spare_part`, `get_open_work_orders`,
      `get_current_production_job`, `get_active_incident`; policy-gated action tools
      `create_maintenance_work_order` (source `AGENT`, e.g. `WO-0005`; WO-0002 is evidence that
      the scheduled timing is too late, not a blocker) and `place_machine_in_maintenance` —
      which also **pauses CNC-03's RUNNING job (JB-0005 → PAUSED ids recorded in the action
      payload)**. Agents never execute SQL; every touch goes through the FactoryWorld facade.
- [x] **Deterministic action policy** (`policy.py`): the model proposes; code decides. Allowed
      only for critical incident + CRITICAL machine + reversible action kinds + medium/high
      continued-operation risk + required part in stock + no IN_PROGRESS/ASSIGNED work + no prior
      executed action for the incident. Blocked ⇒ run ends ESCALATED with the reason stored.
- [x] **Separate deterministic verifier** (`verification.py`): re-reads persisted world state —
      `machine_is_maintenance`, `work_order_created`, `action_recorded`, `active_job_paused`,
      `incident_contained` (= status RESOLVING; the N1 CHECK has no CONTAINED literal and was not
      changed). VERIFIED ⇒ all pass; fail ⇒ one targeted remediation retry, then FAILED.
- [x] **Failure + recovery (demo)**: `FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=true` (or a /twin
      checkbox / `fail_first_work_order` in the advance payload) makes the first work-order
      tool call fail deterministically (`TRANSIENT_FAILURE`) → `RECOVERING` → retry once →
      VERIFIED with both the failed and the retry step persisted. Never random.
- [x] **LLM abstraction (`llm.py`)**: `AgentModel` protocol; `OpenRouterAgentModel`
      (OpenAI-compatible, lazy `openai` import, env `OPENROUTER_API_KEY` +
      `FACTORA_LLM_MODEL` default `openrouter/free`, transient-error retries); offline
      `DeterministicAgentModel` labelled `DETERMINISTIC TEST MODEL` (never presented as a live
      model); `ScriptedAgentModel` for tests. ~3–5 model calls per incident (1 coordinator +
      2 maintenance + at most 1 repair each).
- [x] **Auto-trigger**: `POST /api/demo/advance` runs the watcher after advancing — the flagship
      demo needs no button. Response gains `agent_runs` and `watcher: escalated|quiet`;
      `GET /api/agents/status|runs|runs/{id}` + debug `POST /api/agents/run` added.
- [x] **neatlogs — real runtime spans**: `lazy_span` applies `neatlogs.span(kind=…)` at *call*
      time (import-time decoration would freeze before `init()` in the FastAPI lifespan).
      WORKFLOW `factora.incident_response` → AGENT watcher/coordinator/maintenance → CHAIN
      action_policy/verification → TOOL calls span the real workflow; `neatlogs.wrap()` turns on
      OpenAI-compatible LLM-call tracing when a NEATLOGS_API_KEY exists; no key ⇒ disabled, no
      crash; the key is never logged. Verified live: spans export (401 wall = expected with a
      test key; real traces need a project key).
- [x] **`agent_runs` / `agent_steps` tables** (N3 DDL, schema version n3): run lifecycle +
      ordered steps (HANDOFF/STATUS/DECISION/TOOL/ACTION/POLICY/VERIFICATION/RECOVERY/ERROR),
      no hidden chain-of-thought — only summaries, tool I/O and verification status. Added to
      reset/drop logic + repository CRUD only.
- [x] **Simulation honesty**: machines already in MAINTENANCE are left in MAINTENANCE by later
      advances (telemetry keeps emitting, never flipped back to CRITICAL, no second incident).
- [x] **Twin UI (inside `/twin`, no chat page)**: "Factora is responding" activity timeline
      (watcher → coordinator → maintenance tool evidence → policy → containment → recovery when
      injected → "N/N checks passed" → VERIFIED/ESCALATED), REAL LLM / DETERMINISTIC TEST MODEL
      badge in the header, one small "Demo recovery scenario" toggle, and the twin itself
      reflects containment: CNC-03 turns MAINTENANCE blue/gray, inspector shows the AGENT work
      order, RESOLVING incident, and paused job.
- [x] **Gates**: backend `ruff` clean + **96 tests** (37 new agent tests, no network);
      frontend typecheck/lint clean, **25 tests (7 files)**, build OK; determinism
      `76d28cc593b3` unchanged; live API demo verified BOTH flows (normal + recovery) against a
      running uvicorn **in REAL LLM mode** (openrouter/free), plus offline deterministic mode in
      the test-suite. Verified states after +30 min: CNC-03 MAINTENANCE, JB-0005 PAUSED,
      WO-0005 source=AGENT, incident RESOLVING, run VERIFIED.

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

- Nothing — N3 is complete. Waiting on explicit instruction to start N4.

## Next 3 (do NOT start without instruction)

1. **N4 — production + finance agents, approvals, reroute flow** (per plan §K).
2. **N6** — remaining pages and sponsor integrations per plan §K.

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
| Backend tests | ✅ | `cd backend && .venv/bin/pytest` → **96 passed** (N3 +35 agent/agent-API tests) |
| Frontend typecheck | ✅ | `npm run typecheck` → no findings |
| Frontend lint | ✅ | `npm run lint` → no findings |
| Frontend tests | ✅ | `npm test` → **25 passed (7 files)** |
| Frontend build | ✅ | `npm run build` → built in ~330 ms |
| Determinism diff | ✅ | `git diff --check` → no whitespace errors |
| Seed determinism | ✅ | `python3.11 scripts/seed_local.py --verify` → Determinism: VERIFIED (digest 76d28cc593b3) │ CNC-03 scenario: VERIFIED │ Validation: PASS |
| Scenario runner | ✅ | `python3.11 scripts/run_demo_scenario.py` → T+30→T+120 walk, CNC-03 CRITICAL, incident INC-20261005-001 |
| Live API smoke (N3) | ✅ | uvicorn → reset → advance +30: watcher escalated, CNC-03 → MAINTENANCE, JB-0005 PAUSED, WO-0005 source=AGENT, incident RESOLVING, run `RUN-20261005-0001` VERIFIED (5/5 checks). Recovery flow (`fail_first_work_order`): work-order tool FAILED → RECOVERING → retry → VERIFIED (24 steps). Both flows ran in REAL LLM mode (openrouter/free). |
| Visual verification (browser) | ⏳ | no connected desktop browser in this environment — manual checklist at `docs/EVIDENCE/demo/manual-twin-checklist.md` (to be extended for the agent timeline) |
| neatlogs SDK doctor (local) | ✅ | `python -m neatlogs doctor --local --json` → pass, v1.4.26, doctor/v2, schema 2 |
| neatlogs runtime spans | ✅ (local wall) | `lazy_span` from `observability.py` emits real spans under an initialised SDK (test key → 401 wall as expected); disabled cleanly with no key. Real dashboard traces await a project NEATLOGS_API_KEY |
| neatlogs doctor (probe) | ⏳ | awaits NEATLOGS_API_KEY (no fake traces — never fabricated) |
| Snowflake/Cortex/CoCo grep | ✅ | 0 matches in app code/docs (PROVENANCE.md historical mention only) |
| Entire enabled | ✅ | `entire status` → Enabled · branch main; `entire checkpoint list` → **0 checkpoints** (recorded honestly) |

## Sponsor Status

| Sponsor | Status |
|---|---|
| neatlogs | ✅ real runtime spans on the agent workflow (WORKFLOW/AGENT/TOOL/CHAIN) + OpenAI-compatible LLM wrap; verified with a test key (401 wall expected). Project key still pending → local status `disabled` |
| Entire | ✅ CLI 0.11.4 installed, repo enabled on `main`; `entire checkpoint list` reports **0 checkpoints** so far |
| cfo.ai | ⏳ not started by design — BUSINESS_PLAN.md is a placeholder (`NOT YET MODELLED IN CFO.AI`) |

## Demo Status

- **Demo-able now (N3)**: everything from N2 **plus the autonomous loop** — advance +30 min and
  the watcher escalates, the coordinator assigns the maintenance agent, which investigates with
  real tools, containment runs (urgent AGENT work order + machine to MAINTENANCE + running job
  paused), a separate verifier re-reads the world and the run ends VERIFIED — visible as a live
  timeline inside `/twin` with the twin turning CNC-03 blue/gray. `scripts/run_agent_demo.py`
  prints both the normal and recovery arcs headlessly; the recovery checkbox re-runs it with a
  deterministic tool failure.
- **Not demo-able yet**: production/loss + finance agents (N4), ML predictions, workforce page.
- **Judge-ready point**: N7 per plan §K (deterministic flagship scenario + evidence pack).
