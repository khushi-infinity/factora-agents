# BUILD_LOG.md — Factora (neatHack 2026)

Judging evidence for the build process. Never rewritten to look cleaner than reality
(AGENTS rule 11): failures and detours are recorded alongside successes.

---

## Milestone N0 — fresh neatHack scaffold and sponsor foundations

- **Date/time:** 2026-10-10, ≈17:20–18:15
- **Objective:** brand-new Git repository with fresh history; mockup design references; verified
  sponsor foundations (neatlogs + Entire); FastAPI health backend; minimal frontend shell; all
  gates green; one initial commit.
- **Coding session:** Freebuff agent session (coding agent used for the whole milestone).
- **Entire checkpoint/session:** Entire was enabled **before** substantive scaffold code was written
  (see `docs/EVIDENCE/entire/README.md`): hooks installed, `.entire/settings.json` committed with
  the scaffold. Honest limitation: after the first commit, `entire checkpoint list` shows 0
  checkpoints — checkpoints only materialise when the commit is made *during* a hooked agent
  session (the commit was made at the very start before a session had accumulated activity).
  The next milestone's commit is the target for the first linked checkpoint. Entire's stale
  cloud auth (`entire login` needed) is recorded as a user action in the evidence README.

### Commands run (in order)

```bash
# 1. Verify tooling versions (before writing code)
git --version; node --version; npm --version; python3.11 --version
entire version                      # Entire CLI 0.10.5
gh auth status                      # authenticated as khushi-infinity

# 2. Strange-but-true: Entire was already on PATH at 0.10.5; verified current docs
#    (docs.entire.io/quickstart) match the installed CLI's help output before using it.

# 3. Fresh repository (no old history)
mkdir -p factora-agents && cd factora-agents
git init -b main

# 4. Structure + mockup copies (byte-identical, sha256 spot-verified)
mkdir -p backend/app/{api,agents/tools,world,ml} backend/tests \
         frontend/src/{routes,components,lib} scripts data/{raw,generated} \
         docs/{EVIDENCE/neatlogs,EVIDENCE/entire,EVIDENCE/demo,design/mockups}
cp ../Snowflake/mockup/*.jpg docs/design/mockups/
shasum -a 256 docs/design/mockups/01-command-center.jpg   # matches source file

# 5. Backend
cd backend && python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m neatlogs doctor --local --json     # PASS (v1.4.26, doctor/v2)
.venv/bin/ruff check .                                 # clean
.venv/bin/pytest                                       # 24 passed

# 6. Frontend
cd ../frontend && npm install                            # runtime + dev deps
npm run typecheck && npm run lint && npm test && npm run build

# 7. Repo-wide hygiene grep (section 11 of the task)
grep -rniE "snowflake|cortex|coco" . --exclude-dir=node_modules --exclude-dir=.venv \
  --exclude-dir=.git --exclude-dir=dist --exclude-dir=__pycache__ \
  --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache --exclude-dir=.entire
# → only docs/PROVENANCE.md historical mentions
```

### Result

- Backend: ruff clean, **24/24 tests pass**.
- Frontend: typecheck clean, lint clean, **4/4 tests pass**, production build succeeds.
- no Snowflake/Cortex/CoCo anywhere in the fresh implementation.
- Initial commit `N0: fresh neatHack scaffold and sponsor foundations` on `main`.

### Failures encountered (rule 11 — recorded, not hidden)

1. **Wrong working directory drift (biggest one).** Partway through the frontend scaffold the
   editing tools silently fell back to the OLD repository's directory; a `BackendStatus.tsx` edit
   and a stray `backend/app/observability.py` landed in the old Factora checkout. Detected by
   reading `health.ts` while debugging a lint error — its content was the old Snowflake-era
   version. **Fix:** `git checkout -- frontend/src/components/BackendStatus.tsx` and deleted the
   two stray files from the old repo; re-verified `git status` there. Nothing else in the old repo
   was touched. **Prevention for future milestones:** every command and file edit in the fresh repo
   passes an explicit absolute path or `cwd`.
2. **neatlogs empty-key semantics.** `Settings()` treated `NEATLOGS_API_KEY=""` as an empty string
   credential. Two `test_config.py` failures. **Fix:** `field_validator` maps blank → `None`;
   tests re-run green.
3. **ESLint `react-hooks/set-state-in-effect`** flagged `void load()` in the health panel even
   though the setState calls resolve after the fetch. **Fix:** documented
   `eslint-disable-next-line` on the mount effect with an explanatory comment (the alternative —
   `useSyncExternalStore` — is overkill for a health panel).
4. **Vite config `test` key type error** (`TS2769`). **Fix:** vitest config moved to its own
   `vitest.config.ts` where the browser/test keys typecheck.
5. **ruff findings after first write** (3 items: `UCP035`, `F401`, `SIM108`). **Fix:** applied;
   re-ran clean.

### Changes made because of failures

- Persistent habit adopted for the rest of the build: fresh-repo edits always with explicit `cwd`;
  git-status re-check after any file write near the boundary.
- `observability.py` is deliberately the *only* file that imports neatlogs, so a mid-milestone SDK
  update (or removal) touches exactly one module.

---

## Milestone N1 — deterministic FactoryWorld and local factory state

- **Date/time:** 2026-10-10, evening session
- **Objective:** the simulated factory itself — deterministic SQLite-backed world (machines,
  telemetry, production, parts, maintenance, work orders, downtime, incidents, action ledger),
  a persisted deterministic clock, fresh CNC-03 degradation narrative, economics math, FactoryWorld
  service API, N1 REST surface, seed/scenario scripts, full test coverage.
- **Coding session:** Freebuff agent session.
- **Entire:** enabled for the whole session (`entire status` → Enabled, checkpoints sync to origin).
  `entire checkpoint list` → **0 after the N1 commit** (same root cause as N0: the Freebuff commit
  flow does not trip Entire's session capture; no failure reported by `entire doctor`). No
  checkpoint identifier fabricated — see docs/EVIDENCE/entire/README.md.

### Files created

```
backend/app/world/clock.py          fixed-epoch deterministic simulation clock (EPOCH 2026-10-05 06:00)
backend/app/world/models.py         full DDL: machines, capabilities, sensor_readings, production_jobs,
                                    maintenance_history, spare_parts, work_orders, downtime_events,
                                    incidents, actions, world_state, seed_audit
backend/app/world/database.py       plain-sqlite3 connection layer (no ORM — deliberately justified below)
backend/app/world/repositories.py   the only SQL-owning read/write layer
backend/app/world/economics.py      downtime/scrap loss + reroute feasibility (pure functions)
backend/app/world/seed.py           per-domain SHA-256 RNG streams; 23 machines; CNC-03 24-h ramp
backend/app/world/simulation.py     FactoryWorld service: snapshot/advance/reset/scenario/economics
backend/app/api/factory.py          /api/factory · /api/machines… · /api/incidents · /api/demo/*
backend/app/api/schemas_factory.py  typed response models
scripts/seed_local.py --verify      deterministic seeder + 13 validation rules + digest proof
scripts/run_demo_scenario.py        readable no-agent degradation walk
backend/tests/test_world.py         18 tests (determinism, integrity, monotonic ramp, transitions)
backend/tests/test_factory_api.py   11 tests (every endpoint incl. reset determinism + 422s)
frontend/src/lib/factory.ts(+test)  typed client + shape tests
frontend/src/components/FactoryStatus.tsx   factory proof panel (reset/advance buttons)
```

### Key design decisions

- **No ORM by design**: 12 tables, plain `sqlite3` with FK enforcement; repositories own all SQL.
  SQLAlchemy would add migration weight with zero demo value at N1 (recorded per task rule §2).
- **Per-domain seeded RNGs** (`sha256(master_seed:domain)`) — domain code can be reordered without
  cross-contaminating streams; reseed digest is stable (`76d28cc593b3`).
- **Clock**: fixed epoch 2026-10-05 06:00, persisted in `world_state`, advanced in 10-min ticks;
  never reads the wall clock.
- **CNC-03 narrative recreated fresh**: seeded 24-h history ramps vibration 2.4→~5.0 mm/s and
  bearing temp 62→70.7 °C (eased curve, monotonic, validated by tests); the seeded state is
  WARNING so the live `advance(10/30/60)` walk completes WARNING→CRITICAL and opens a
  deterministic incident (`INC-20261005-001`) with an evidence pack (telemetry + 2 prior
  BRG-AX-17 repairs + limited stock 2/reorder 3).
- **Reroute feasibility is type-restricted**: a CNC job may only move to CNC-family machines
  (capabilities table says which part numbers each *type* can make). State, queue load and
  cost/hour deltas come from stored facts — nothing invented.

### Failures encountered (rule 11)

1. **CWD drift recurred** — the editor later defaulted back to the old repo folder mid-milestone;
   the world/* files landed there once more. Detected by an ImportError on
   `app.world.simulation`; fixed by moving the files and deleting the stray directory from the
   old repo; prevention = full absolute paths for every write (held for the rest of the session).
2. **Incident ids drifted across resets** (`INC-…-002` on second seed) because the sequence lived
   on the service instance — fixed by resetting the counter in `reset_world()`; a test now pins
   identical ids across resets.
3. **`COMMIT` without transaction** on autocommit connections — replaced with `with conn:` blocks.
4. **Seeded-state mismatch**: originally seeded CNC-03 as CRITICAL *and* advanced-from-CRITICAL;
   the scenario test exposed that no incident could ever open. Re- seeded as WARNING mid-ramp so
   the demo walk genuinely transitions.
5. **Reroute candidates initially spanned all factory types** (a CNC job "rerouted" to a case
   packer) — fixed with same-type restriction + test.
6. **cross-type compatibility illusion removed from economics** so Production Agent (N3) cannot
   "invent" a move to incompatible equipment.
7. ruff fixes (unused RNGs, zip strict, contextlib.suppress), vitest eslint suppression — all
   recorded in the gates below.

### Commands run (gates)

```bash
cd backend && .venv/bin/ruff check .          # All checks passed!
.venv/bin/pytest                              # 53 passed (24 N0 + 18 world + 11 factory API)
python3.11 scripts/seed_local.py              # summary + CNC-03 scenario: VERIFIED + Validation: PASS
python3.11 scripts/seed_local.py --verify     # Determinism: VERIFIED (digest 76d28cc593b3)
python3.11 scripts/run_demo_scenario.py       # T+30→T+120 walk, incident INC-20261005-001
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
# → clean · clean · 6 passed · built in 101 ms
# live smoke: uvicorn up → GET /api/factory → POST /api/demo/advance 30 → POST /api/demo/reset
```

### Result

- N1 complete: deterministic world, no agents, no LLMs, no fake traces
  (observability module untouched since N0 — per task rule §17).

---

## N2 pre-flight — documentation reconciliation (honest corrections)

- **Stale push blockers removed from PROGRESS.md.** N1 was pushed before the N1 report was even
  printed; PROGRESS.md still claimed "N1 commit pending push" + "GitHub repo creation pending".
  Corrected: `origin/main` = `7df8fbb` (VERIFIED via `git ls-remote`) and the GitHub blocker is
  marked resolved. No seed/test data was changed to accommodate the text — files, not claims, are
  the source of truth.
- **Machine state accounting check.** Verified against the seeded database: 23 machines total →
  seeded HEALTHY 19 / WARNING 2 (CNC-03, CNC-06) / MAINTENANCE 1 (PRS-03) / OFFLINE 1 (PKG-03);
  after the scenario advance CNC-03 flips WARNING→CRITICAL giving 19/1/1/1/1 = 23. Earlier prose
  experiments in the session ("22 machines minus offline") were never committed as facts; the
  committed docs (N1 sections of PROGRESS/BUILD_LOG) already said 23 machines — verified correct,
  no numeric correction needed, only the resolution note recorded here.
- **CWD-safety rule adopted** for N2: every write in this milestone uses an absolute path under
  `/Users/khushisarawagi/Desktop/factora-agents/`; commands carry explicit cwd (drift was observed
  again at session start: pwd resolved to the OLD repo; corrected before any write).

---

## N2 — interactive Factory Digital Twin and operational UI

### How this milestone actually started (rule 11 — record failures, don't hide them)

- **N2 was found half-done and uncommitted.** When OpenCode took the milestone over, the working
  tree above `7df8fbb` already contained 11 modified tracked files plus 7 untracked N2 sources
  (`frontend/src/routes/`, `frontend/src/components/twin/`, `frontend/src/lib/twin.ts`, …) left by
  a previous coding agent that never committed.
- **Safety backup first, before touching a single N2 file:**
  ```bash
  git diff > /tmp/factora-n2-before-opencode.patch                 # 746 lines
  git ls-files --others --exclude-standard > /tmp/factora-n2-untracked-files.txt   # 15 paths
  tar -czf /tmp/factora-n2-untracked-backup/untracked.tgz -T /tmp/factora-n2-untracked-files.txt
  ```
  Both artefacts live outside the repository and are not committed.
- **Audit, not restart.** The candidate work was read end to end (backend routes + schemas +
  tests, router wiring, `lib/factory.ts`, `twin.ts`, `TwinScene`, `MachineInspector`,
  `CommandCenter`) and compared with `docs/design/mockups/01/02/04`. Good code was kept; the
  problems below were fixed in place. No wholesale rewrite.

### What was kept from the previous agent

- Backend: `GET /api/factory/lines`, `/machines/{id}/context`, `/maintenance`, `/work-orders`,
  `/production` with typed Pydantic models and 8 new TestClient tests (19 in
  `test_factory_api.py`).
- Frontend: react-router wiring (`App.tsx`, `main.tsx`), `lib/factory.ts` machine/context client,
  `lib/twin.ts` pure helpers, `TwinScene` three.js scene, `MachineInspector` Recharts panel,
  `CommandCenter`, `TwinPage`, and the lazy-loading + error-boundary policy.

### Fixes applied during the audit

1. **Inspector/selection desynced on load.** `TwinPage` pre-selected CNC-03 in the scene but never
   fetched its context, so the inspector said "Select a machine" while the floor highlighted one.
   The initial load now resolves CNC-03's context too.
2. **Lane geometry was wrong.** `FloorLanes` computed a lane width from `max(x) + footprint*scale`
   and pinned the left edge at a constant, so on the real 5-line layout most machines fell outside
   their lane. Replaced with the pure, unit-tested `lanesFor()` which bounds each lane by the
   min/max scene x of *that line's* machines.
3. **Machine bodies overlapped.** Positions scale with the world (5 m pitch → 7.43 scene units)
   while body/plinth sizes were fixed at 7/9.45 — plinths collided. Added `footprintFor()` which
   derives body size from the smallest same-line gap (→ 5.2 here), test-pinned.
4. **One shared chart axis flattened vibration.** Vibration (~5 mm/s) and bearing temperature
   (~70 °C) were plotted on the same Y axis, so the vibration trend was a flat line at the bottom.
   Split into two charts (also matches mockup 04).
5. **Perpetual spin on the selected machine.** Replaced with a static blue selection ring +
   recoloured body — the one-shot state-change pulse remains, no continuous animation.
6. **Duplicated route logic.** `machines()`, `machine_detail()` and the three sub-resource routes
   each re-mapped the same dicts and re-raised the same 404. Factored `_require_machine`,
   `_machine_out`, `_machine_detail`, `_incident_out`, `_telemetry_rows` and one row-reader per
   resource; `/context` now composes those exact readers, so the aggregated and split endpoints
   cannot drift.
7. **Dead/nonsense code removed:** `twinReadiness()` (tautological `hasCriticalPath`, never
   called), `activeIncidentFor()` (only ever exercised by its own test), `fetchIncidents()` and a
   dead `_ = Clock` import guard in `factory.py`. `machines()` now reuses `_machine_out`.
8. **`frontend/package.json` had no `dependencies` block at `7df8fbb`** while
   `package-lock.json` did — a fresh `npm ci` on the committed tree would have failed. Installing
   `react-router` restored the whole manifest; `npm ls --depth=0` is clean (26 packages).
9. **Sidebar honesty:** the N1 pill read `Degraded: 3/10 pages` (misleading wording for a
   progress count) → now `3 / 10 pages`.

### N2 additions beyond the recovered work

- **Line rail** above the canvas driven by `GET /api/factory/lines` — this is what gives that
  endpoint a real consumer: click a line to dim the rest of the floor (§6 production-line
  distinction).
- **WebGL resilience** (`§14`): `webglAvailable()` probe → non-WebGL browsers get
  `TwinFallback`, a per-line floor table of all 23 machines; the error boundary renders the same
  fallback if the canvas throws. Loading states everywhere.
- **Page-level incident strip** so the CNC-03 incident is visible without selecting anything.
- **Legend counts** from `snapshot.state_distribution`; **"Needs attention"** section on the
  Command Center listing WARNING/CRITICAL machines.
- **Inspector:** work-orders section, empty states for maintenance/jobs, consistent 384 px rail.
- **Tests:** `TwinPage.test.tsx` (renders the whole shell in jsdom — header, sim clock, scenario
  controls, line rail, legend, all 23 machines through the fallback table, and CNC-03's inspector
  with `Synthetic demo economics` + both charts). `twin.test.ts` gained `footprintFor`,
  `lanesFor`, `lineLabel`, `STATE_ORDER` coverage and lost the two dead-code suites.

### Agent-hook directories (rule 15)

`.claude/ .codex/ .cursor/ .factory/ .gemini/ .pi/ .opencode/plugins/entire.ts .github/hooks/`
were inspected before staging — every one contains only `entire enable --agent` hook wiring
(`entire hooks <agent> pre-task/post-task/session-end …`), not product code, and
`.github/hooks/entire.json` is Entire config, **not** CI. Decision: add explicit `.gitignore`
entries for exactly those paths (`.github/hooks/` only — `.github/workflows/` stays committable
if CI is added later), and commit none of them. `.entire/settings.json` (the shared Entire config)
remains tracked as at N0. `git add -A` was **not** used.

### Commands run (gates — actual output at N2 close)

```bash
cd /Users/khushisarawagi/Desktop/factora-agents/backend
.venv/bin/ruff check .                       # All checks passed!
.venv/bin/pytest                             # 61 passed, 1 warning in 51.73s

cd ../frontend
npm run typecheck                            # no findings
npm run lint                                 # no findings
npm test                                     # 21 passed (6 files)
npm run build                                # ✓ built in 511 ms
npm ls --depth=0                             # 26 packages, none missing/invalid

cd ..
python3.11 scripts/seed_local.py --verify    # Determinism: VERIFIED (digest 76d28cc593b3)
                                             # CNC-03 scenario: VERIFIED · Validation: PASS
python3.11 scripts/run_demo_scenario.py      # T+30 → CRITICAL, incident INC-20261005-001
git diff --check                             # clean (no whitespace errors)

# live API smoke against uvicorn :8000
GET  /api/factory/lines        → 5 lines (Assembly 5, CNC 8, Packaging 3, Press 4, Quality 3) = 23
GET  /api/machines             → 23, CNC-03 {state WARNING, health 63, x 16, y 18}
GET  /api/machines/CNC-03/context → 7 keys, 36 telemetry, 3 maintenance, 1 work order,
                                   2 jobs, 0 incidents, economics_note "Synthetic demo economics"
POST /api/demo/advance {30}    → clock 06:30, cnc03_state CRITICAL, open_incidents 1
     /api/factory after        → 19/1/1/1/1 = 23, INC-20261005-001 BEARING_DEGRADATION
POST /api/demo/reset {}        → clock 06:00, 23 machines, 3,312 telemetry rows
     /api/factory after        → 19/2/0/1/1 = 23, 0 incidents
```

Test totals **changed**: backend 53 → **61**, frontend 6 → **21** (3 → 6 files). The old numbers
are left in the N1 section above because they were true at N1.

### Visual verification — not claimed (rule: never claim unbuilt/unverified)

Browser tooling exists in this environment but **no desktop browser is connected to the session**
(`browser.tabs.open` → `browser.disconnected`, twice), so no screenshot or pixel-level check was
performed. Instead of asserting a visual result we did not observe, a step-by-step manual
checklist was written to **`docs/EVIDENCE/demo/manual-twin-checklist.md`** for the user to run.
What *was* verified mechanically: the full scenario through the HTTP API (above), and the
complete `/twin` DOM in jsdom including the no-WebGL fallback path.

### Entire (rule 18)

```bash
entire status            # ● Enabled · branch main · 8 agents · 7 Codex hooks need approval
entire checkpoint list   # checkpoints 0 — "No checkpoints found on this branch."
```
**Zero checkpoints.** No identifier is invented. OpenCode drives this session and Entire's
auto-generated `.opencode/plugins/entire.ts` fails to load on OpenCode v2.0.19, so session capture
never registers; recorded in `docs/EVIDENCE/entire/README.md`.

### Result

N2 complete: a genuine visual twin at `/twin`, backend-driven placement and state, working
inspector with real telemetry and charts, working Reset/Advance with the CNC-03
WARNING → CRITICAL arc and a visible incident, docs reconciled. No agents, no ML, no LLM calls,
no fabricated traces — N3 not started.

---

## N3 — Autonomous CNC-03 maintenance incident response

### Handoff reality check (rule: verify everything)

The N3 handoff claimed "no N3 product code written — planning only". The repository said otherwise:
the working tree already contained a complete uncommitted N3 implementation (agent modules, tools,
policy, verifier, coordinator, API, 540 backend tests-worth of code, frontend timeline). Actual
repo state wins; the code was audited rather than rebuilt, completed where the spec required, and
brought to green.

### Audit findings + fixes applied

- **Real spec gaps found and fixed**:
  - `place_machine_in_maintenance` did **not pause CNC-03's RUNNING production job** (spec §5).
    Added `repositories.pause_running_jobs` (RUNNING → PAUSED, reversible), exposed via
    `FactoryWorld.pause_active_jobs`, called by the containment tool, paused job ids recorded in
    the action result → they land in the `actions` ledger payload.
  - Verification had **no `active_job_paused` check** (spec §14). Added as the fourth check
    (5/5 total now: `machine_is_maintenance`, `work_order_created`, `action_recorded`,
    `active_job_paused`, `incident_contained`).
  - A duplicated `pause_running_jobs` definition and a dropped `def` line both introduced and
    removed during editing — caught by `ruff` F811 and a syntax check, fixed before any commit.
- **Model outputs in the wild**: with a real OpenRouter free model the deterministic demo tool
  filed two output-repair attempts (missing field; malformed JSON) and called `get_spare_part`
  with a wrong invented id (`SPindle_Bearing`) — the tool answered NOT_FOUND as a clean error
  envelope and the assessment still landed on BRG-AX-17 from history. The repair-once-then-
  escalate design held up under a real, sloppy free model.
- **Environment quirk**: backgrounded uvicorn processes are reaped between tool invocations in
  this harness; the live API demo was therefore executed as one script (server + both flows).

### Architecture as built

- `app/agents/watcher.py` — deterministic pre-filter, idempotent per incident, zero LLM.
- `app/agents/coordinator.py` — owns `RunRecorder` (agent_runs/agent_steps CRUD + enforced
  transitions), calls the model for exactly one decision (specialist assignment), runs policy,
  executes actions with one deterministic retry on failure, contains the incident, calls the
  verifier, and ends VERIFIED / FAILED / ESCALATED.
- `app/agents/maintenance.py` — plan (model call 1) → execute read tools → assess (model call 2);
  tool-plan output is re-bound to known ids and stripped of non-read tools before execution.
- `app/agents/policy.py` — 7 deterministic rules; the model cannot act without them.
- `app/agents/verification.py` — separate stage; re-reads persisted world state only.
- `app/agents/llm.py` — `AgentModel` protocol; OpenRouter (lazy `openai` import,
  `reasoning.exclude` for free models, 3 transient retries) vs. `DeterministicAgentModel` and
  `ScriptedAgentModel` both hard-labelled `DETERMINISTIC TEST MODEL`.
- `app/agents/tools.py` — typed read/action tools over the FactoryWorld facade; FailureInjector
  for the deterministic demo failure only.
- `app/world` — `agent_runs`/`agent_steps` DDL (schema n3), reset/drop list extended, repo CRUD;
  `_update_states` skips machines already in MAINTENANCE.

### Commands run (gates — actual output at N3 close)

```text
cd backend && .venv/bin/ruff check .         → All checks passed!
cd backend && .venv/bin/pytest               → 96 passed in ~46s
frontend npm run typecheck                   → clean
frontend npm run lint                        → clean
frontend npm test                            → Test Files 7 passed, Tests 25 passed
frontend npm run build                       → ✓ built in ~330ms
python3.11 scripts/seed_local.py --verify    → Determinism: VERIFIED (digest 76d28cc593b3)
python3.11 scripts/run_demo_scenario.py      → CNC-03 arc intact (agents untouched when not triggered)
backend/.venv/bin/python scripts/run_agent_demo.py        → normal arc: VERIFIED, 5/5 checks
backend/.venv/bin/python scripts/run_agent_demo.py --recovery → fail → RECOVERING → retry → VERIFIED
git diff --check                             → clean
```

### Live API demo (both flows in REAL LLM mode, openrouter/free)

Normal: reset → advance +30 → `watcher: escalated`, CNC-03 **MAINTENANCE**, incident
`INC-20261005-001` **RESOLVING** owned `FACTORA_AGENT/RUN-20261005-0001`, job **JB-0005 PAUSED**,
**WO-0005 source=AGENT** critical, run VERIFIED with 5/5 checks (23 steps).
Recovery (`fail_first_work_order: true`): `CREATE_URGENT_WORK_ORDER FAILED (TRANSIENT_FAILURE)` →
`ACTING → RECOVERING` → retry ok → **VERIFIED** (24 steps, both the failure and the retry kept).

### neatlogs (rule 17: verify before claiming)

- SDK 1.4.26. Instrumentation is runtime, not import-time: `Observability.lazy_span` applies
  `neatlogs.span(kind=…)` only when the wrapped function runs *and* observability was initialised
  in the FastAPI lifespan — otherwise a clean passthrough. Spans: WORKFLOW
  `factora.incident_response`, AGENT watcher/coordinator/maintenance, CHAIN action_policy and
  verification, TOOL calls in the maintenance investigation.
- Verified live with a test key: status `active`, watcher executed under a real span, batch export
  attempted (401 Unauthorized = expected for a fake key — this proves real export, not a stub).
  `neatlogs.wrap()` is applied to the OpenAI-compatible client in `OpenRouterAgentModel` when the
  SDK is initialised, tracing the actual LLM calls.
- No key ⇒ `disabled`, agents run normally, no crash, and the key is never logged anywhere.

### Entire (rule 18)

CLI **0.11.4** (upgraded from 0.10.5). `entire status` → Enabled · branch main (Claude Code hooks
out of date; 7 Codex hooks pending approval — user actions). `entire checkpoint list` →
**0 checkpoints**: Freebuff-driven commits do not trip session capture; recorded honestly, no
identifier invented.

### Result

N3 complete: one complete autonomous loop — Watcher → Coordinator → Maintenance Agent with real
tools, deterministic policy, failure + recovery, separate verification, persisted runs/steps,
neatlogs spans, auto-trigger from `/api/demo/advance`, endpoints, and a timeline inside `/twin`
that reflects containment on the twin itself. Backend 96 tests, frontend 25 tests, both gate sets
green. N4 not started.
