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
