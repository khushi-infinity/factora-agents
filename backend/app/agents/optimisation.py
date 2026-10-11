"""Optimisation policy + verification stage #2 (N4).

Same philosophy as the maintenance containment (N3): the model proposes, this
module decides and later re-reads the *stored world state* to score whether the
factory actually changed. Rerouting is the only new autonomous action, and it
may run only when every deterministic rule below passes.

Approval threshold: reroutes whose modelled incremental cost exceeds
`MAX_AUTONOMOUS_REROUTE_COST_USD` need a human — the flagship never crosses it
(its cost is a few hundred dollars), so no approval step is fabricated for
drama.
"""

from __future__ import annotations

from ..observability import get_observability
from ..world.simulation import FactoryWorld
from .models import (
    ActionKind,
    CheckResult,
    FinanceAssessment,
    OptimisationDecision,
    ProductionAssessment,
    VerificationResult,
)

MAX_AUTONOMOUS_REROUTE_COST_USD = 2_500.0


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


@_lazy_span(kind="GUARDRAIL", name="optimisation_action_policy")
def evaluate_optimisation_policy(
    world: FactoryWorld,
    *,
    job_id: str,
    production: ProductionAssessment,
    finance: FinanceAssessment | None,
) -> tuple[OptimisationDecision, list[str], list[str]]:
    """Return (decision, allowed_reasons, blockers). Code decides, always."""
    reasons: list[str] = []
    blockers: list[str] = []

    job = world.get_job(job_id)
    if job is None:
        blockers.append(f"job {job_id} not found")
    elif job["status"] != "PAUSED":
        blockers.append(
            f"job {job_id} is {job['status']}, not the accountable paused job")
    elif not _last_action_was_containment(world, job):
        blockers.append(
            "the pause is not attributable to a verified maintenance "
            "containment — autonomous reroute applies only to that case")
    else:
        reasons.append(
            f"job {job_id} is PAUSED on the contained machine "
            f"{(world.get_incident(production.paused_job_id) or job)['machine_id']}")

    candidate = production.recommended_candidate
    machine = world.get_machine(candidate) if candidate else None
    if machine is None:
        blockers.append("production assessment names no reroute candidate")
    else:
        if machine["machine_type"] != _source_type(world, job):
            blockers.append(
                f"candidate {candidate} is a {machine['machine_type']}, not the "
                "job's machine type")
        else:
            reasons.append(f"candidate {candidate} is type-compatible")
        if machine["state"] != "HEALTHY":
            blockers.append(f"candidate {candidate} is {machine['state']}, not HEALTHY")
        else:
            reasons.append(f"candidate {candidate} is healthy")

    if finance is None:
        blockers.append("no finance assessment — significant financial impact "
                        "always needs the second specialist")
    elif finance.recommendation != "REROUTE":
        blockers.append(
            f"finance recommends {finance.recommendation}, not REROUTE "
            f"(net benefit {finance.net_benefit_usd} USD)")
    elif finance.net_benefit_usd <= 0:
        blockers.append("net benefit is not positive")
    else:
        reasons.append(
            f"finance supports the reroute (+{finance.net_benefit_usd} USD)")

    cost = production.est_incremental_cost_usd
    approval_required = False
    if cost is not None and cost > MAX_AUTONOMOUS_REROUTE_COST_USD:
        approval_required = True
        blockers.append(
            f"modelled incremental cost {cost} USD exceeds the autonomous "
            f"threshold {MAX_AUTONOMOUS_REROUTE_COST_USD} USD")
    else:
        reasons.append(
            f"incremental cost {cost} USD within the autonomous threshold")

    allowed = not blockers and not approval_required
    decision = OptimisationDecision(
        action="REROUTE_PRODUCTION_JOB" if allowed else "WAIT_FOR_REPAIR",
        target_machine=candidate if allowed else None,
        job_id=job_id,
        reason_summary=("; ".join(reasons) if allowed else "; ".join(blockers))[:900],
        production_supported=production.recommended_candidate is not None,
        finance_supported=bool(finance and finance.recommendation == "REROUTE"),
        approval_required=approval_required,
    )
    return decision, reasons, blockers


def _last_action_was_containment(world: FactoryWorld, job: dict) -> bool:
    """The pause must belong to a ledgered maintenance containment action."""
    actions = world.get_actions()
    for action in actions:
        if action.get("action_type") == ActionKind.PLACE_IN_MAINTENANCE.value \
                and action.get("executed_at") \
                and job["job_id"] in action.get("payload", ""):
            return True
    return False


def _source_type(world: FactoryWorld, job: dict | None) -> str | None:
    if not job:
        return None
    machine = world.get_machine(job["machine_id"])
    return (machine or {}).get("machine_type")


def _parts_for_type(world: FactoryWorld, machine: dict) -> list[str]:
    """Part numbers the target's machine type can produce (capabilities read)."""
    rows = world.conn.execute(
        "SELECT part_no FROM capabilities WHERE machine_type = ?",
        (machine["machine_type"],)).fetchall()
    return [r[0] for r in rows]


# ── verification stage #2 (deterministic optimisation checks) ───────────
@_lazy_span(kind="CHAIN", name="verification.optimisation")
def verify_optimisation(
    world: FactoryWorld,
    *,
    job_id: str,
    target_machine_id: str,
    expected_net_benefit_usd: float,
) -> VerificationResult:
    """Re-read stored state: did the reroute actually happen and pay off?"""
    checks: list[CheckResult] = []

    job = world.get_job(job_id)
    moved = bool(job and job["machine_id"] == target_machine_id)
    checks.append(CheckResult(
        name="job_no_longer_on_contained_machine",
        passed=moved,
        detail=(f"{job_id} now assigned to {job['machine_id']} ({job['status']})"
                if job else f"job {job_id} not found"),
    ))

    target = world.get_machine(target_machine_id) if moved else None
    # Compatibility is judged against the part's capable machine types in the
    # capabilities table (via FactoryWorld + economics), not against a candidate
    # list relative to the job's current machine — after a successful reroute
    # the job's machine_id IS the target, so a relative list would exclude it.
    candidates = world.get_compatible_machines(job_id)
    type_ok = bool(
        target
        and world.get_job(job_id)
        and (any(c["candidate_machine_id"] == target_machine_id
                 for c in candidates)
             or any(cpart == job_part
                    for cpart in _parts_for_type(world, target))
             if (job_part := (world.get_job(job_id) or {}).get("part_no"))
             else False))
    checks.append(CheckResult(
        name="job_assigned_to_compatible_machine",
        passed=type_ok,
        detail=(f"{target_machine_id} compatible for the job's part"
                if type_ok else "compatibility lookup failed or assignment lost"),
    ))

    healthy_ok = bool(target and target["state"] == "HEALTHY")
    checks.append(CheckResult(
        name="target_machine_is_healthy",
        passed=healthy_ok,
        detail=(f"{target_machine_id} state = {target['state']}" if target
                else "target machine not found"),
    ))

    runnable = bool(job and job["status"] in ("QUEUED", "RUNNING"))
    checks.append(CheckResult(
        name="production_job_is_runnable",
        passed=runnable,
        detail=(f"{job_id} status = {job['status']}" if job
                else "job missing"),
    ))

    reroute_actions = [action for action in world.get_actions()
                       if action.get("action_type")
                       == ActionKind.REROUTE_PRODUCTION_JOB.value
                       and action.get("executed_at")
                       and job_id in (action.get("payload") or "")]
    checks.append(CheckResult(
        name="reroute_action_recorded",
        passed=bool(reroute_actions),
        detail=(f"{len(reroute_actions)} ledgered reroute action(s): "
                + ", ".join(a["action_id"] for a in reroute_actions)
                if reroute_actions else "no reroute in the actions ledger"),
    ))

    positive = expected_net_benefit_usd > 0
    checks.append(CheckResult(
        name="financial_result_positive",
        passed=positive,
        detail=f"expected net benefit = {expected_net_benefit_usd} USD",
    ))

    return VerificationResult(
        passed=all(check.passed for check in checks), checks=checks)
