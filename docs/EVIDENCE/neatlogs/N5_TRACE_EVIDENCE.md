N5 Trace Evidence — Neatlogs Spans

SDK version: 1.4.26
Date: 2026-10-11
Scenario: Full N3→N4 autonomous maintenance + production optimisation flow
Model mode: DETERMINISTIC TEST MODEL (stand-in; OPENROUTER_API_KEY not configured)

If NEATLOGS_API_KEY is absent, system still works — spans are generated at runtime
without blocking. No real model calls are made when key is missing.

Workflow spans (normal autonomous flow — Trace A):

## Watcher
- Span: watcher hand-off on escalation
- Incident: INC-20261005-001 (BEARING_DEGRADATION, CNC-03, critical)
- Action: Assigned maintenance agent, DETECTED → INVESTIGATING
- Output: critical incident detected, maintenance agent resolved or contained

## Coordinator (N3 maintenance)
- Span: N3 maintenance containment workflow
- Steps: DETECTED → INVESTIGATING → PLANNING → ACTION_PENDING → ACTING → VERIFYING → VERIFIED
- Actions executed:
  - CREATE_URGENT_WORK_ORDER (step 15, PASSED)
  - PLACE_IN_MAINTENANCE (step 17, PASSED)
  - Incident marked contained (step 19, RESOLVING status)
  - 5/5 maintenance verification checks passed (step 21)
- Output: CNC-03 state = MAINTENANCE, incident status = RESOLVING

## Coordinator (N4 production optimisation)
- Span: production/finance coordination workflow
- Steps after maintenance: Production/Loss Agent → Factory Finance Agent → Optimisation Policy → Reroute → Optimisation Verification
- Model calls: 3 per incident (1 coordinator plan + batched tool list + 1 assessment)
- Actions executed:
  - Production assessment: recommended candidate CNC-07 (high confidence)
  - Finance assessment: REROUTE recommendation, net benefit 672.75 USD
  - Optimisation policy ALLOWED (job PAUSED, candidate compatible+healthy, cost within threshold)
  - REROUTE_PRODUCTION_JOB: JB-0005 → CNC-07 (step 29)
  - 6/6 optimisation verification checks passed (step 32)
- Output: Factory optimised: maintenance contained, JB-0005 rerouted to CNC-07, net benefit 672.75 USD

Trace A — normal autonomous flow summary:
- critical incident → maintenance → containment → verification → production disruption → Production/Loss evaluation → Factory Finance evaluation → reroute → optimisation verification → FACTORY OPTIMISED

Recovery flow spans (Trace B):

## N3 Recovery Flow
- Failure injection: FACTORA_DEMO_FAIL_FIRST_WORK_ORDER=true
- Work-order tool transient failure on first attempt
- Trace: ACTION FAILED → RECOVERY DECISION → RETRY → SUCCESS → VERIFIED

Specific steps in recovery trace:
- Step 16: CREATE_URGENT_WORK_ORDER FAILED (transient failure injected)
- Step 17: ACTING → RECOVERING (tool failed; retrying once)
- Step 18: CREATE_URGENT_WORK_ORDER → ok (retry succeeded)
- Step 19: ledgered ACT-0001 for CREATE_URGENT_WORK_ORDER
- Step 20: ACTING → VERIFYING (retry recovery)
- Step 21: 5/5 checks passed — VERIFIED

Recovery flow summary:
- Failure injected → Recovery decision → Retry → SUCCESS → VERIFIED
- Demonstrates deterministic failure injection and recovery cycle works reliably
- No random production failures — only injected tool failures

Model/Call Budget:
- Normal flow: 3 model calls per incident (coordinator plan + maintenance plan batched + assessment)
- Recovery flow: same budget; failure does not add model calls
- Deterministic stand-in always available; real model optional via OPENROUTER_API_KEY
- `reasoning: {"enabled": False, "exclude": True}` passed to prevent reasoning tokens eating completion budget
- MAX_TOKENS = 6000, PROVIDER_ATTEMPTS = 3, PROVIDER_BACKOFF_S = 1.0 for reliability

No secrets logged: OPENROUTER_API_KEY never committed or exposed in prompts/traces.
Spans work even when NEATLOGS_API_KEY absent (no blocking/fallback degradation).

Key invariants verified:
- N3 containment: CNC-03 → MAINTENANCE, incident → RESOLVING
- N3 recovery: ACTION FAILED → RECOVERING → RETRY → SUCCESS → VERIFIED
- N4 optimisation: 6/6 verification checks pass
- Job reroute: JB-0005 → CNC-07 (compatible, healthy target)
- Net benefit: 672.75 USD (positive → REROUTE recommended)
- All steps traced with agent/type/status for root-cause debugging