"""Factory Watcher — "something important happened", nothing more.

The watcher is deliberately not a language model: it pre-filters world state
deterministically and only escalates a *critical* incident whose machine is
actually in the CRITICAL operating state and that no agent run has picked up
yet. A healthy world, or a plain WARNING, produces no escalation and therefore
costs zero model calls — a simulation tick never invokes an LLM.
"""

from __future__ import annotations

from ..observability import get_observability
from ..world.simulation import FactoryWorld
from .models import WatcherEscalation

ESCALATION_SEVERITY = "critical"
ESCALATION_MACHINE_STATE = "CRITICAL"
TELEMETRY_FOR_HANDOFF = 3


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


@_lazy_span(kind="AGENT", name="watcher", role="observer")
def evaluate_world(world: FactoryWorld) -> list[WatcherEscalation]:
    """Return the incidents that deserve an autonomous response right now."""
    escalations: list[WatcherEscalation] = []

    for incident in world.get_active_incidents():
        if incident["severity"] != ESCALATION_SEVERITY:
            continue

        machine = world.get_machine(incident["machine_id"])
        if not machine or machine["state"] != ESCALATION_MACHINE_STATE:
            continue

        # Idempotency: one autonomous run per incident, ever.
        if world.get_agent_runs(incident["incident_id"]):
            continue

        escalations.append(WatcherEscalation(
            machine_id=machine["machine_id"],
            incident_id=incident["incident_id"],
            severity=incident["severity"],
            incident_type=incident["type"],
            summary=incident["summary"],
            reason=(f"{incident['severity']} incident {incident['incident_id']} "
                    f"({incident['type']}) on {machine['machine_id']}, which is in "
                    f"{machine['state']} state at health score "
                    f"{machine['health_score']}."),
            recent_telemetry=world.get_recent_telemetry(
                machine["machine_id"], TELEMETRY_FOR_HANDOFF),
            machine_state=machine["state"],
        ))

    return escalations
