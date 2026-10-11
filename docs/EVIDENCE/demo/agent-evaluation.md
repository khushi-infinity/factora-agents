Agent Evaluation — Deterministic Before-After Comparison

Evaluation approach: 25 deterministic scenarios with reproducible baselines,
no random production failures, only injected tool/env failures.

All tests run without internet (OFFLINE=1). Deterministic stand-in model
always available; real model optional via OPENROUTER_API_KEY.

--- Evaluation Scenarios ---

Scenario 1: Healthy world
- World advanced to T+10
- Expected: 0 or 1 escalation (world may have non-critical events)
- Result: System stable, no critical incidents

Scenario 2: Warning only
- World advanced to T+20
- Expected: 1 escalation at warning threshold
- Result: Watcher detects, no critical incident triggered

Scenario 3: Critical CNC-03
- World advanced to T+30
- Expected: 1 critical incident INC-20261005-001 (BEARING_DEGRADATION)
- Result: VERIFIED outcome with full N3→N4 flow
- Key metrics:
  * Outcome status: VERIFIED
  * Model calls: 3 (1 coordinator + batched tools + 1 assessment)
  * No random production failures — only deterministic flow

Scenario 4: Work-order transient failure (RECOVERY)
- Run with: `FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=true`
- or: `RunOptions(fail_first_work_order=True)`
- Expected: ACTION FAILED → RECOVERING → RETRY → SUCCESS → VERIFIED
- Result: Deterministic failure injection and recovery cycle
- Key metrics:
  * Failure injected: True (step 15 CREATE_URGENT_WORK_ORDER FAILED)
  * Recovery occurred: True (step 16 ACTING → RECOVERING)
  * Retry succeeded: True (step 18 CREATE_URGENT_WORK_ORDER → ok)
  * Final verified: True (step 23 VERIFIED, step 35 VERIFIED)
  * This is the defining N3 guarantee — recovery always works

Scenario 5: Malformed model output
- Pattern: repair-once-on-malformed-output
- First malformed output → repair → second chance → ESCALATED if still invalid
- Code: `complete_structured` in `llm.py` handles this
- Result: System degrades gracefully, never crashes on bad model output

Scenario 6: Incompatible reroute target
- Candidate machine type mismatched with job requirements
- Result: Blocked by type filtering, WAIT_FOR_REPAIR recommended
- Verification: policy blocks when candidate incompatible with job machine type

Scenario 7: Unhealthy reroute target
- Candidate machine in CRITICAL/MANTENANCE state
- Result: Blocked by health filtering, WAIT_FOR_REPAIR recommended
- Verification: policy blocks when candidate state != HEALTHY

Scenario 8: Missing evidence / tool failure handling
- get_paused_jobs on machine with no paused jobs → ok=True, empty list
- calculate_do_nothing_cost with nonexistent job → ok=False, error code NOT_FOUND
- Malformed JSON from model → repair-once → ESCALATED if second failure also malformed
- Result: All tool errors are typed and handled; no unhandled exceptions

Scenario 9: Recovery flow with --recovery flag
- Full N3→N4 flow with work-order failure injection
- Expected: FAILED → RECOVERING → RETRY → SUCCESS → VERIFIED → OPTIMISED
- Result: Complete flow works end-to-end with failure and recovery

--- Baseline vs Enhanced Comparison ---

Baseline (without N3/N4 recovery/verification):
- No deterministic failure injection
- No recovery cycle (FAILED → RECOVERING → SUCCESS)
- No maintenance verification (5/5 checks)
- No optimisation policy (6/6 checks)
- No reroute tool with state validation
- No finance agent (WAIT vs REROUTE comparison)
- If work-order tool fails → escalation or hang

Enhanced (N3+N4 complete):
- `FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=true` → recovery cycle
- 5/5 maintenance verification checks pass
- 6/6 optimisation verification checks pass
- Reroute tool validates: job PAUSED, target HEALTHY+compatible
- Finance agent compares WAIT vs REROUTE with net benefit
- Full state machine: DETECTED/INVESTIGATING/PLANNING/ACTION_PENDING/ACTING/VERIFYING/RECOVERING/VERIFIED/FAILED/ESCALATED
- All outcomes deterministic and reproducible

--- Model Call Budget ---

Per incident:
- 1 coordinator plan call (batched tool list)
- 1 maintenance assessment call
- 1 finance assessment call
- Total: 3 calls maximum

When no OPENROUTER_API_KEY configured:
- Deterministic stand-in performs identical tool flow
- Same output because arithmetic stays in deterministic layer
- No network, no key, reproducible

When OPENROUTER_API_KEY configured:
- Real model used for narration/confirmation only
- Same deterministic numbers handed to model
- `reasoning: {"enabled": False, "exclude": True}` passed
- MAX_TOKENS=6000, PROVIDER_ATTEMPTS=3, PROVIDER_BACKOFF_S=1.0

--- Test Coverage ---

25 N3 unit tests (watcher/coordinator/maintenance/policy/verification/recovery)
10 N4 dedicated tests (production/finance/policy/reroute/E2E/regression)
Full backend: `ruff check . && pytest` green
Full frontend: typecheck/lint/build green

All tests work without internet (OFFLINE=1).