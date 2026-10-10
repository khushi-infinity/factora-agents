# AGENTS.md — Operating Rules for Factora (neatHack 2026)

This file governs every AI agent (or human) contributing to `factora-agents`. Intentionally short
and non-negotiable. Where a rule conflicts with convenience, the rule wins.

## The Rules

1. **Read before changing product code.** `NEATHACK_REBUILD_PLAN.md` (in the reference repo),
   `AGENTS.md` and `PROGRESS.md` define what exists and where we are. Reconcile contradictions in
   the same change.
2. **One milestone at a time.** The build order lives in `PROGRESS.md` (and plan §K). Do not start
   the next milestone without explicit instruction; do not silently expand scope.
3. **Never claim unbuilt functionality exists.** README, PROGRESS, the UI and API docs describe only
   what is on disk and tested. "0 / 10 pages" is preferable to a fake page.
4. **Never copy implementation code from the old Factora repository**
   (https://github.com/khushi-infinity/Factora). It is a planning/design reference only — ideas,
   mockups and lessons may inform new code; lines of old source may not. See `docs/PROVENANCE.md`.
5. **Never commit secrets.** Only `.env.example` (placeholders) is tracked. API keys, tokens and
   key files stay in the environment or gitignored files. If a secret is committed, treat it as
   compromised: rotate, then remove from history.
6. **Verify official sponsor docs before changing sponsor integrations.** Do not invent neatlogs
   APIs, Entire CLI commands or cfo.ai capabilities: check the current docs (docs.neatlogs.com,
   docs.entire.io, cfo.ai) first, and record what was verified in `docs/EVIDENCE/`.
7. **Run tests before marking a milestone complete.** Backend: `cd backend && .venv/bin/ruff check . && .venv/bin/pytest`.
   Frontend: `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`.
   A milestone is not done with a red gate.
8. **Preserve the mockup design language.** Navy sidebar, light content surface, blue accent;
   state colours: green healthy, amber warning, red critical, blue/gray maintenance, gray offline
   (tokens in `frontend/src/index.css`; mockups in `docs/design/mockups/`).
9. **Keep architecture simple.** One backend process + one SPA + SQLite. No microservices, extra
   brokers or cloud services unless a milestone requirement forces one — with justification here.
10. **Update `PROGRESS.md` and `docs/BUILD_LOG.md` after every completed milestone.** Include the
    exact commands run, results, and failures encountered (rule 11).
11. **Record failures instead of hiding them.** Failed attempts, reverted changes and debug
    detours are judged evidence of process — BUILD_LOG entries say what happened, honestly.
12. **Do not start the next milestone without explicit instruction.**

## Verification protocol

| Change type | Evidence before "done" |
|---|---|
| Docs only | Presence check of required sections + secret scan |
| Backend code | `ruff check .` + `pytest` green; new route → new TestClient test |
| Frontend code | `typecheck` + `lint` + `vitest` green; build-affecting → `npm run build` green |
| Sponsor integration | Docs re-verified; integration status recorded in `docs/EVIDENCE/<sponsor>/README.md` |
| Milestone | All relevant gates green; PROGRESS.md + BUILD_LOG.md updated; commit naming the milestone |

## Repo map

```
backend/app/       FastAPI app: api/ (routes), agents/ (runtime N3+), world/ (sim N1+), ml/ (N2+)
backend/tests/     pytest suite (credential-free, offline)
frontend/src/      React SPA: routes/, components/, lib/ (typed API client + helpers)
scripts/           setup + demo scripts (seed, scenario, evidence export)
data/              raw/ + generated/ (populated at N1; fixtures at N2+)
docs/              BUILD_LOG, PROVENANCE, BUSINESS_PLAN, EVIDENCE/{entire,neatlogs,demo}, design/mockups
```
