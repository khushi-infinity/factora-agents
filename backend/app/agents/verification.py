"""Deterministic verification — a separate stage from acting.

The agent never declares its own success. After the action tools run, this
module re-reads the *stored world state* and reports one boolean per check, so
"VERIFIED" means the factory actually changed, not that the model said so.

Mapping note: N1's incident vocabulary has no CONTAINED/MITIGATED literal; the
contained state is `status = "RESOLVING"` (the incident is no longer open and
unowned, but the repair itself is not finished). The check is still named
`incident_contained` because that is the operational meaning.
"""

from __future__ import annotations

from ..observability import get_observability
from ..world.simulation import FactoryWorld
from .models import CheckResult, VerificationResult

CONTAINED_INCIDENT_STATUS = "RESOLVING"


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


@_lazy_span(kind="CHAIN", name="verification")
def verify_maintenance_containment(
    world: FactoryWorld,
    *,
    machine_id: str,
    incident_id: str,
) -> VerificationResult:
    """Re-read persisted state and score each containment expectation."""
    checks: list[CheckResult] = []

    machine = world.get_machine(machine_id)
    checks.append(CheckResult(
        name="machine_is_maintenance",
        passed=bool(machine and machine["state"] == "MAINTENANCE"),
        detail=(f"{machine_id} state = {machine['state']}" if machine
                else f"{machine_id} not found"),
    ))

    actions = [action for action in world.get_actions(incident_id)
               if action.get("executed_at")]
    work_orders = []
    for action in actions:
        payload = _payload(action)
        work_order_id = (payload.get("work_order_id")
                         or (payload.get("work_order") or {}).get("work_order_id"))
        if work_order_id:
            found = next((order for order in world.get_work_orders(machine_id)
                          if order["work_order_id"] == work_order_id), None)
            if found:
                work_orders.append(found)
    checks.append(CheckResult(
        name="work_order_created",
        passed=bool(work_orders),
        detail=(f"{work_orders[0]['work_order_id']} "
                f"({work_orders[0]['status']}, source={work_orders[0]['source']})"
                if work_orders else "no agent work order recorded against the incident"),
    ))

    checks.append(CheckResult(
        name="action_recorded",
        passed=bool(actions),
        detail=(f"{len(actions)} executed action(s): "
                + ", ".join(action["action_id"] for action in actions)
                if actions else "no executed action in the ledger"),
    ))

    running_jobs = world.get_jobs(machine_id, status="RUNNING")
    paused_ids = [job["job_id"] for job in world.get_jobs(machine_id,
                                                          status="PAUSED")]
    checks.append(CheckResult(
        name="active_job_paused",
        passed=not running_jobs,
        detail=(f"no RUNNING job on {machine_id} (paused: "
                f"{', '.join(paused_ids) or 'none'})")
        if not running_jobs else
        f"job(s) {', '.join(job['job_id'] for job in running_jobs)} "
        f"on {machine_id} are still RUNNING",
    ))

    incident = world.get_incident(incident_id)
    contained = bool(incident
                     and incident["status"] == CONTAINED_INCIDENT_STATUS)
    checks.append(CheckResult(
        name="incident_contained",
        passed=contained,
        detail=(f"{incident_id} status = {incident['status']} "
                f"(contained = {CONTAINED_INCIDENT_STATUS})"
                if incident else f"{incident_id} not found"),
    ))

    return VerificationResult(
        passed=all(check.passed for check in checks), checks=checks)


def _payload(action: dict) -> dict:
    import json

    try:
        return json.loads(action.get("payload") or "{}")
    except json.JSONDecodeError:
        return {}
