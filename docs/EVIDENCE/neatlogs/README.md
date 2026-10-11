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
- since N3 the agent workflow is instrumented with **runtime** spans — `Observability.lazy_span`
  applies `neatlogs.span(kind=...)` at *call* time (import-time decoration would freeze into a
  pass-through before `init()` runs in the lifespan), so a disabled SDK costs nothing and an
  initialised one gets real spans with durations.

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
| **Runtime agent spans (N3)** | ✅ verified with a test key: status `active`, the Watcher executed under a real span, and batch export was attempted (401 Unauthorized — the expected wall for a fake key, proving real export rather than a stub) |
| **LLM-call tracing wrap (N3)** | ✅ `neatlogs.wrap()` applied to the OpenAI-compatible client in `OpenRouterAgentModel` when initialised (REAL LLM mode) |
| Doctor **probe** (round-trip to the dashboard) | ⏳ blocked: needs a real project key |
| Populated dashboard screenshots | ⏳ blocked: needs a real project key — none are claimed |

No screenshots of a populated dashboard are claimed — none exist yet. The instrumentation itself
is real and exercised (see BUILD_LOG N3); the dashboard view is the only pending piece.

## What the N3 instrumentation actually emits

```text
WORKFLOW factora.incident_response
├─ AGENT watcher        (deterministic pre-filter; spans only when it runs)
├─ AGENT coordinator    (workflow owner)
│  ├─ CHAIN action_policy     (deterministic guardrail)
│  ├─ AGENT maintenance       (specialist)
│  │  ├─ TOOL get_machine / get_recent_telemetry / get_maintenance_history /
│  │  │        get_spare_part / get_open_work_orders / get_current_production_job /
│  │  │        get_active_incident   (per planned call)
│  │  └─ (REAL LLM mode: chat.completions traced via neatlogs.wrap)
│  ├─ TOOL create_maintenance_work_order   (policy-gated action)
│  ├─ TOOL place_machine_in_maintenance    (policy-gated action)
│  └─ CHAIN verification                   (deterministic checks)
└─ run ends VERIFIED / FAILED / ESCALATED — mirror of agent_steps in SQLite
```

Failure + recovery (demo injection) shows up as the failing TOOL span followed by the retry —
the trace mirrors the persisted step list 1:1.

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
