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
