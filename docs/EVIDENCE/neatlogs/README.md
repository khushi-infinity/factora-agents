# EVIDENCE/neatlogs — Agent Observability

Sponsor: **neatlogs** — https://docs.neatlogs.com · SDK on PyPI as `neatlogs`

## SDK / version

- **Installed:** `neatlogs 1.4.26` (Python 3.11 venv at `backend/.venv`)
- **Verified against:** docs.neatlogs.com — /docs, /docs/quickstart/introduction, /sdk/python,
  /sdk/doctor (all fetched 2026-10-10; commands below come from those pages, not memory).

## Verified setup instructions (official)

```bash
# install (verified: pip install -U neatlogs)
pip install -U neatlogs

# network-free SDK validation (verified: pass, v1.4.26, doctor/v2, schema 2)
python -m neatlogs doctor --local --json

# authenticated pipeline probe — needs a project key; NOT yet run (no key supplied)
python -m neatlogs doctor --probe --json
```

Application integration (implemented in `backend/app/observability.py`, following the official
docs for long-running servers):

- `neatlogs.init(api_key=..., workflow_name=...)` at FastAPI lifespan startup — only when a key
  is configured;
- `neatlogs.flush()` + `neatlogs.shutdown()` on server shutdown (the pattern the SDK docs
  prescribe for FastAPI rather than per-request flushing);
- future agents/tools will use `@neatlogs.span(kind="WORKFLOW"/"AGENT"/"TOOL", ...)` per the SDK
  docs — the span helper already lives in `observability.py` and is inert until init succeeds.

## Required environment variables (verified names)

| Variable | Meaning | Where documented |
|---|---|---|
| `NEATLOGS_API_KEY` | project key from the neatlogs dashboard (Settings → API Keys) | docs / MCP Integration + SDK pages; Doctor probe section |
| `NEATLOGS_WORKFLOW_NAME` | workflow label shown in the dashboard (we set `factora-agents`) | `workflow_name` init option, /sdk/python |

Both are read from the environment / repo-root `.env` only. Nothing is committed.

## Current status (honest)

| Check | Result |
|---|---|
| SDK installed + doctor **local** | ✅ pass (2026-10-10, captured in BUILD_LOG) |
| Application **boots without a key** | ✅ observability reported `disabled`, health stays `ok` |
| Health endpoint discloses state | ✅ `observability: {provider, status, detail}` |
| Doctor **probe** (round-trip to the dashboard) | ⏳ blocked: needs a real project key |
| Real agent traces | ⏳ N3+ (agents do not exist at N0) |

No screenshots of a populated dashboard are claimed — none exist yet.

## What later traces must demonstrate (demo evidence plan)

1. **Planning** — a `WORKFLOW` root span whose child `AGENT` spans show the Coordinator deciding
   and sequencing specialist work.
2. **Tool calls** — `TOOL` spans (telemetry query, history lookup, parts check, work-order create)
   nested under their agent, with inputs/outputs captured.
3. **Handoffs** — the Coordinator assigning a specialist and that specialist's spans appearing
   inside the same trace (state machine transitions visible).
4. **Failures** — an injected deterministic failure (e.g. tool timeout / missing part) captured by
   neatlogs, with the error surfaced on the span.
5. **Retries / recovery** — the Coordinator's retry or replan visible as follow-up spans after the
   failed one.
6. **Verification** — the post-action verification step as its own span, with pass/fail outcome.
7. **Before/after improvement** — two comparable traces (pre-fix vs post-fix of the same scenario)
   with latency/outcome deltas, retrievable from the dashboard for the submission.

These map 1:1 to the plan's §L flagship scenario beats.
