"""Deterministic action policy — the gate between "the agent wants to" and "we do".

The model proposes; this module decides. Nothing autonomous happens unless every
rule below passes, and the decision (with its reasons) is persisted as a step so
a judge can read exactly why an action was allowed or blocked.

Allowed autonomously (N3): raise an urgent maintenance work order and take the
machine out of service. Everything that costs money, changes staffing, deletes
orders or touches finance requires human approval and is deliberately absent.
"""

from __future__ import annotations

from ..observability import get_observability
from ..world.simulation import FactoryWorld
from .models import AUTONOMOUS_ACTION_KINDS, ActionPolicyDecision, MaintenanceAssessment

WORK_BLOCKING_STATUSES = ("ASSIGNED", "IN_PROGRESS")


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


@_lazy_span(kind="CHAIN", name="action_policy", category="guardrail")
def evaluate_action_policy(
    world: FactoryWorld,
    *,
    incident: dict,
    machine: dict,
    assessment: MaintenanceAssessment,
) -> ActionPolicyDecision:
    """Return an explicit allow/deny with a reason for every rule checked."""
    reasons: list[str] = []
    blockers: list[str] = []

    # 1 — the incident itself must be critical.
    if incident["severity"] == "critical":
        reasons.append("incident severity is critical")
    else:
        blockers.append(f"incident severity is '{incident['severity']}', not critical")

    # 2 — the machine must actually be in the critical operating state.
    if machine["state"] == "CRITICAL":
        reasons.append(f"{machine['machine_id']} is in CRITICAL state")
    else:
        blockers.append(f"{machine['machine_id']} is in {machine['state']} state")

    # 3 — only reversible, low-blast-radius actions are autonomous.
    proposed = list(dict.fromkeys(assessment.recommended_actions))
    disallowed = [kind for kind in proposed if kind not in AUTONOMOUS_ACTION_KINDS]
    if disallowed:
        blockers.append(
            "actions outside the autonomous envelope: "
            + ", ".join(kind.value for kind in disallowed))
    else:
        reasons.append("all proposed actions are reversible and policy-listed")
    actions = [kind for kind in proposed if kind in AUTONOMOUS_ACTION_KINDS]

    # 4 — continued operation must look genuinely unsafe.
    if assessment.risk_of_continued_operation in ("high", "medium"):
        reasons.append(
            f"continued operation assessed as {assessment.risk_of_continued_operation} risk")
    else:
        blockers.append("continued operation assessed as low risk")

    # 5 — any required spare part must actually be on the shelf.
    if assessment.required_part_id:
        part = world.get_spare_part(assessment.required_part_id)
        if part is None:
            blockers.append(f"required part {assessment.required_part_id} is unknown")
        elif part["stock_qty"] < 1:
            blockers.append(
                f"required part {assessment.required_part_id} is out of stock")
        else:
            reasons.append(
                f"{assessment.required_part_id} in stock ({part['stock_qty']} on hand)")

    # 6 — no human may already be working on this machine.
    blocking = [
        order for order in world.get_open_work_orders(machine["machine_id"])
        if order["status"] in WORK_BLOCKING_STATUSES
    ]
    if blocking:
        blockers.append(
            "work already in progress: "
            + ", ".join(order["work_order_id"] for order in blocking))
    else:
        reasons.append("no work order already in progress on this machine")

    # 7 — an incident is contained at most once.
    executed = [
        action for action in world.get_actions(incident["incident_id"])
        if action.get("executed_at")
    ]
    if executed:
        blockers.append(
            "an action was already executed for this incident: "
            + ", ".join(action["action_id"] for action in executed))
    else:
        reasons.append("no action has been executed for this incident yet")

    allowed = not blockers
    return ActionPolicyDecision(
        allowed=allowed,
        actions=actions if allowed else [],
        reasons=reasons,
        blocked_reason="; ".join(blockers) if blockers else None,
    )
