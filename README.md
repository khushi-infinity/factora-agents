# Factora — Autonomous Factory Operating System

**neatHack 2026 submission** — N4 complete, pushed to `main` at `aad4b56`

Factora is an autonomous factory operating system built around a digital twin and
cooperating AI agents. Agents observe simulated factory telemetry, investigate
anomalies, coordinate decisions, take controlled actions, and verify the factory
actually improved — every step traced by Neatlogs and displayed as a live timeline
inside `/twin`.

---

## N4: Coordinated Production & Financial Optimisation (latest)

The flagship autonomous flow is now complete:

```text
CNC-03 degrades
↓
Watcher detects
↓
Maintenance investigates
↓
work-order action fails
↓
Coordinator recovers
↓
machine contained
↓
maintenance verification passes
↓
production disruption detected
↓
Production/Loss Agent evaluates alternatives
↓
Factory Finance Agent evaluates economics
↓
job rerouted
↓
optimisation verification passes
```

### What N4 delivers

- **Production/Loss Agent** — retrieves paused job and compatible candidates via
  deterministic tools; assessment built from loss/reroute economics (output/hour,
  downtime, reroute cost, expected delay, remaining quantity). Candidate filtering
  excludes OFFLINE, CRITICAL, MAINTENANCE, and incompatible machines. 1 model call
  per incident; arithmetic stays in deterministic layer.

- **Factory Finance Agent** — compares WAIT vs REROUTE using code-computed values:
  do-nothing cost, reroute incremental cost, loss avoided, net benefit. Returns
  typed `FinanceAssessment: recommendation ∈ {REROUTE, WAIT}`. NOT cfo.ai —
  internal runtime specialist. All values from deterministic formulas in
  `backend/app/world/economics.py`.

- **Optimisation Policy** — autonomous reroute allowed only when: maintenance
  containment verified, job paused, target compatible+HEALTHY, net benefit positive,
  cost below `MAX_AUTONOMOUS_REROUTE_COST_USD=2500`. Otherwise BLOCKED or
  APPROVAL_REQUIRED. 6/6 deterministic optimisation verification checks.

- **Coordinator** — full handoff flow: maintenance → production assessment → finance
  assessment → policy → reroute → optimisation verification → VERIFIED.

- **3-model-call budget** per incident (1 coordinator + 1 maintenance batched + 1
  assessment). Deterministic stand-in always available; real model optional via
  `OPENROUTER_API_KEY`.

- **Recovery cycle** — `FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=true` → ACTION FAILED
  → RECOVERING → RETRY → SUCCESS → VERIFIED. Deterministic failure injection,
  never random production failure.

### Full flow story

```text
CNC-03 degrades
↓
Watcher detects critical incident
↓
Coordinator assigns Maintenance Agent
↓
Maintenance investigates with tools (telemetry, spare-part stock, work orders)
↓
PLACE_IN_MAINTENANCE: CNC-03 → MAINTENANCE, job paused
↓
5/5 maintenance verification checks pass (machine_is_maintenance, work_order_created, etc.)
↓
Production/Loss Agent: job JB-0005 PAUSED on CNC-03, 67 remaining units
↓
Compatible candidates scored (type/health/availability filtered)
↓
CNC-07 recommended (healthy, compatible, available)
↓
Factory Finance Agent: do-nothing cost 6.00 USD, reroute cost 25.00 USD,
  loss avoided 672.75 USD, net benefit 666.75 USD → REROUTE
↓
Optimisation policy: ALLOWED (job PAUSED, candidate compatible+healthy, cost within threshold)
↓
REROUTE_PRODUCTION_JOB: JB-0005 → CNC-07
↓
6/6 optimisation verification checks pass
✓ FACTORY OPTIMISED
```

---

## Sponsor integrations

| Sponsor | Role in Factora |
|---|---|
| **neatlogs** | Runtime observability: every agent run, LLM call, tool call, handoff, failure, retry and verification step traced. Real runtime spans (WORKFLOW/AGENT/TOOL/CHAIN/GUARDRAIL) in `backend/app/observability.py` + agent modules. Spans work even when `NEATLOGS_API_KEY` absent (no blocking). |
| **Entire** | Development-time checkpointing: agent sessions joined to Git commits, giving judges a verifiable build history. Enabled from the first commit. |
| **cfo.ai** | Business-plan modelling only (pricing, costs, revenue scenarios) for the submission material. Not a product runtime component. See `docs/BUSINESS_PLAN.md` — `STATUS: INPUTS PREPARED — CFO.AI MODEL STILL REQUIRED`. |

### Neatlogs

- SDK 1.4.26 installed; `neatlogs.wrap` supports OpenRouter
- Real spans for: Watcher, Coordinator, Maintenance, Production/Loss Agent,
  Factory Finance Agent, optimisation policy, reroute tool, optimisation verification
- Spans work even when `NEATLOGS_API_KEY` absent (no blocking / fallback disabled)
- No secrets logged; `OPENROUTER_API_KEY` never committed or exposed in prompts/traces
- SDK verification recorded in `docs/EVIDENCE/neatlogs/README.md`

### Entire

- CLI version 0.11.4; enabled on branch `main`
- 0 checkpoints at commit time (checkpoints appear after agent sessions with recording)
- Checkpoint chronology: `1d0003c` (N0) → `7df8fbb` (N1) → `1d0003c8c567c7a695ade46a0866ad8db60708fa` (N2) → `aad4b56` (N4)
- `docs/EVIDENCE/entire/N5_ENTIRE_EVIDENCE.md` recorded truthfully

### cfo.ai

- Not integrated into runtime
- `docs/BUSINESS_PLAN.md`: `STATUS: INPUTS PREPARED — CFO.AI MODEL STILL REQUIRED`
- Prepared inputs for later modelling: customer, pricing, cost assumptions,
  scenarios (downside/base/upside), gross margin, runway, inference/infra costs
- `docs/EVIDENCE/cfo-ai/USER_ACTION_REQUIRED.md` — next steps documented
- `docs/EVIDENCE/cfo-ai/README.md` — evidence placeholder

---

## Quick start

```bash
# Backend — FastAPI on :8000
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
# health: http://127.0.0.1:8000/api/health · factory: /api/factory

# Seed / inspect the deterministic factory world
python3.11 scripts/seed_local.py              # reset + seed + validate (add --verify for digest proof)
python3.11 scripts/run_demo_scenario.py       # print the CNC-03 degradation arc (no agents)
python3.11 scripts/run_agent_demo.py          # the N3+N4 autonomous loop, headless (add --recovery for failure/recovery arc)
python3.11 scripts/run_full_demo.py           # full N3→N4 flow (normal or --recovery)
python3.11 scripts/run_full_demo.py --recovery# recovery flow with work-order failure

# Frontend — Vite on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

The backend boots with **no credentials**. neatlogs tracing activates only when
`NEATLOGS_API_KEY` is set in the environment; without it the app runs normally
with observability disabled.

Real-LLM mode activates only when `OPENROUTER_API_KEY` is set
(`FACTORA_LLM_MODEL`, default `openrouter/free`); without it the agents run on a
clearly-labelled deterministic stand-in (`DETERMINISTIC TEST MODE`) so tests and
demos never need the internet.

---

## The autonomous loop (N3→N4)

```text
DETECT      Watcher (deterministic, no LLM per tick): critical incident on a CRITICAL machine
          ↓
INVESTIGATE Coordinator assigns the Maintenance Agent (1 model call)
          ↓           Maintenance Agent plans tool calls (1 model call), then fetches evidence itself:
          ↓           recent telemetry · prior bearing repairs · spare-part stock · open work orders ·
          ↓           running production job · the incident record
          ↓           then recommends from that evidence (1 model call) — structured Pydantic output
PLAN        Deterministic action policy decides what may run — the model proposes, code decides
          ↓
ACT         tools: CREATE_URGENT_WORK_ORDER (source AGENT) · PLACE_IN_MAINTENANCE
          ↓           (containment also pauses the machine's RUNNING job; ids recorded in ledger)
          ↓           demo: first work-order call can fail deterministically → RECOVERING → retry once
VERIFY      separate deterministic verifier re-reads the world:
          ↓           machine_is_maintenance · work_order_created · action_recorded ·
          ↓           active_job_paused · incident_contained (RESOLVING)
          ↓           (N4 addons) production disruption detected → Production/Loss → Finance → reroute
VERIFIED    or FAILED / ESCALATED — every step persisted in agent_runs / agent_steps
```

Timeline inside `/twin` reflects containment (`CNC-03 → MAINTENANCE`) and optimisation
(job rerouted, economics card with actual stored values).

### N3 beat (single incident, no production optimisation)

Open `/twin`, select **CNC-03**, press **Advance +30 min** — the machine turns
amber → red with a one-shot pulse, the state distribution changes, and a deterministic
incident appears. In N3 the same press now triggers the watcher automatically: the
"Factora is responding" timeline plays the agent run, and CNC-03 settles into
MAINTENANCE (blue/gray) with its job paused and an AGENT-source work order.

### N4 beat (production + finance optimisation)

After N3 containment, the timeline continues:

```text
Maintenance
✓ containment verified

Production
Paused production detected

Production
Evaluating compatible machines

Production
<actual machine> recommended

Finance
WAIT vs REROUTE evaluated

Finance
Net benefit $<actual value>

Coordinator
Recommendations aligned

Action
<job> → <target machine>

Verification
6 / 6 passed

✓ FACTORY OPTIMISED
```

Reset restores the start. A single checkbox ("Demo recovery scenario") makes the
first work-order tool call fail so judges can watch the RECOVERING → retry arc.

---

## Tests

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

Test totals:
- 25 N3 unit tests (watcher/coordinator/maintenance/policy/verification/recovery) ✓
- 10 API endpoint tests ✓
- 25 N4 dedicated tests (Production/Loss/Finance/Policy/Reroute/E2E/N3 regression) ✓
- Full backend: `ruff check . && pytest` green
- Full frontend: typecheck/lint/build green
- Seed verification: digest `76d28cc593b3`
- Demo scripts: `run_agent_demo.py` (normal + `--recovery`) pass
- Optimisation demo: full N4 path demonstrated

---

## Documents

- [PROGRESS.md](./PROGRESS.md) — live milestone state
- [AGENTS.md](./AGENTS.md) — operating rules for coding agents
- [docs/PROVENANCE.md](./docs/PROVENANCE.md) — fresh-code disclosure
- [docs/BUILD_LOG.md](./docs/BUILD_LOG.md) — milestone-by-milestone build record (judging evidence)
- [docs/EVIDENCE/neatlogs/README.md](./docs/EVIDENCE/neatlogs/README.md) — SDK verification record
- [docs/EVIDENCE/entire/README.md](./docs/EVIDENCE/entire/README.md) — entire evidence
- [docs/EVIDENCE/neatlogs/N5_TRACE_EVIDENCE.md](./docs/EVIDENCE/neatlogs/N5_TRACE_EVIDENCE.md) — N5 trace evidence
- [docs/EVIDENCE/entire/N5_ENTIRE_EVIDENCE.md](./docs/EVIDENCE/entire/N5_ENTIRE_EVIDENCE.md) — N5 entire evidence
- [docs/EVIDENCE/cfo-ai/README.md](./docs/EVIDENCE/cfo-ai/README.md) — cfo.ai evidence status
- [docs/EVIDENCE/cfo-ai/USER_ACTION_REQUIRED.md](./docs/EVIDENCE/cfo-ai/USER_ACTION_REQUIRED.md) — cfo.ai action required
- [docs/EVIDENCE/demo/agent-evaluation.md](./docs/EVIDENCE/demo/agent-evaluation.md) — agent evaluation before/after
- [docs/EVIDENCE/demo/recording-checklist.md](./docs/EVIDENCE/demo/recording-checklist.md) — recording checklist
- [docs/EVIDENCE/demo/manual-twin-checklist.md](./docs/EVIDENCE/demo/manual-twin-checklist.md) — manual twin checklist
- [docs/EVIDENCE/demo/screenshots/](../docs/assets/screenshots/) — product screenshots
- [docs/BUSINESS_PLAN.md](./docs/BUSINESS_PLAN.md) — cfo.ai business plan (inputs prepared)
- [docs/SUBMISSION_CHECKLIST.md](./docs/SUBMISSION_CHECKLIST.md) — submission checklist
- [docs/demo-script.md](./docs/demo-script.md) — 3-minute demo script
- [docs/design/mockups/](./docs/design/mockups/) — the ten design reference screens