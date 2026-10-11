## N4 RESULT

## Production/Loss Agent
The Production/Loss Agent retrieves the paused job and compatible candidates via deterministic tools, then builds its assessment from loss/reroute economics (output/hour, downtime, reroute cost, expected delay, remaining quantity). Candidate filtering excludes OFFLINE, CRITICAL, MAINTENANCE, and incompatible machines. Economics arithmetic stays in the deterministic layer - the model only narrates and confirms.

Model calls: 1 per incident (batched tool list). No network required for tests.

## Factory Finance Agent
The Finance Agent compares WAIT vs REROUTE using code-computed values:
- do-nothing loss (idle cost per N3 economics)
- reroute incremental cost
- loss avoided
- net benefit = wait_cost - reroute_incremental_cost
- recommendation: REROUTE if net benefit > 0, else WAIT

The agent is NOT cfo.ai - it is Factora's internal runtime specialist. All values come from deterministic formulas in `backend/app/world/economics.py`.

## Coordinated Flow
CNC-03 critical → maintenance containment → verification passes → paused production job detected → Production/Loss Agent → candidate machines evaluated → Factory Finance Agent → WAIT vs REROUTE compared → Coordinator reconciles → optimisation policy → reroute_production_job → optimisation verification → FACTORY OPTIMISED

## Selected Candidate
Candidate machines filtered by: compatible type, HEALTHY state, available capacity, not same machine as source. The coordinator executes reroute_production_job which moves the job to the target machine and records the action in the ledger.

## Economics
- loss if idle: determined by `do_nothing_cost()` formula (output/hour × idle hours)
- reroute cost: incremental cost from `calculate_reroute_cost()` (queue delay delta + rate delta)
- loss avoided: deterministic calculation based on idle cost vs reroute cost
- net benefit: wait_cost - reroute_incremental_cost (positive → REROUTE, non-positive → WAIT)

Threshold: `MAX_AUTONOMOUS_REROUTE_COST_USD=2500`; flagship costs are a few hundred → never crosses approval boundary.

## Action
- `CREATE_URGENT_WORK_ORDER` (reversible, policy-listed)
- `PLACE_IN_MAINTENANCE` (pauses machine + active jobs, recorded in ledger)
- `REROUTE_PRODUCTION_JOB` (validates: job PAUSED, target HEALTHY+compatible, not same machine, records in ledger)

## Optimisation Verification
6/6 deterministic checks:
1. job_no_longer_on_source
2. job_on_compatible_target
3. target_machine_is_healthy
4. job_runnable
5. reroute_action_recorded
6. financial_result_positive

All checks re-read persisted world state - not trusted from tool results alone.

## N3 Recovery Regression
- Failure injection: `FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=true`
- Trace: ACTION FAILED → RECOVERY DECISION → RETRY → SUCCESS
- Outcome: VERIFIED
- Work-order tool transient failure handled with retry
- Maintenance containment still works after N4 additions

## LLM
- mode: openrouter/free (configurable via `FACTORA_LLM_MODEL` env)
- model: openrouter/openrouter/free (default); other models via env
- calls per incident: 3 total (1 coordinator plan + 1 maintenance plan batched + 1 assessment)
- `reasoning: {"enabled": False, "exclude": True}` passed to prevent reasoning tokens eating budget
- Deterministic stand-in always available; real model optional via API key
- Never logs `OPENROUTER_API_KEY` in prompts or traces

## neatlogs
- SDK 1.4.26 installed; `neatlogs.wrap` supports OpenRouter
- Real spans for: Watcher, Coordinator, Maintenance, Production/Loss Agent, Factory Finance Agent, optimisation policy, reroute tool, optimisation verification
- Spans work even when `NEATLOGS_API_KEY` absent (no blocking)
- No secrets logged; `OPENROUTER_API_KEY` never committed or exposed
- SDK verification recorded in `docs/EVIDENCE/neatlogs/README.md`

## Entire
- Checkpoints truthfully recorded; may be 0 at commit time
- `SCHEMA_VERSION = "n3"` stored in world_state
- `entire` status and checkpoint list recorded after commit
- BUSINESS_PLAN.md: `STATUS: INPUTS PREPARED — CFO.AI MODEL STILL REQUIRED`

## Tests
- 25 N3 unit tests green (watcher/coordinator/maintenance/policy/verification/recovery)
- 10 API endpoint tests green
- 25 N4 dedicated tests green (Production/Finance/Policy/Reroute/E2E/N3 regression)
- Full backend: `ruff check . && pytest` green
- Full frontend: typecheck/lint/build green
- Seed verification: digest `76d28cc593b3`
- Demo scripts: `run_agent_demo.py` (normal + `--recovery`) pass
- Optimisation demo: full N4 path demonstrated

## Git
- Commit: `N4: coordinated production and financial optimisation`
- Push: `git push origin main` (never force-push)
- Remote HEAD equals local HEAD: `aad4b56`
- No unresolved blockers

## CFO.AI
preparation status
- STATUS: INPUTS PREPARED — CFO.AI MODEL STILL REQUIRED
- Labelled inputs prepared for later cfo.ai modelling:
  - Customer scenario, pricing, number of factories, inference cost, infrastructure, support, gross margin, acquisition
  - Downside/base/upside scenarios
- No cfo.ai integration yet; no real evidence exists

## Blockers
- None (all gates green; no unresolved blockers)

## Next
N5 — sponsor evidence, screenshots, cfo.ai, demo polish and submission readiness

Then STOP. Do NOT begin N5.