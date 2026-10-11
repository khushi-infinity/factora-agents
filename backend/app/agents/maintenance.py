"""Maintenance Agent — investigate one machine, recommend one response.

It is the only specialist in N3. It never receives the database in a prompt:
it asks for a tool plan, runs those tools, and builds its recommendation from
the tool results. Two model calls per investigation (plan, then assessment).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..observability import get_observability
from ..world.simulation import FactoryWorld
from .llm import (
    TASK_INVESTIGATION_PLAN,
    TASK_MAINTENANCE_ASSESSMENT,
    AgentModel,
    complete_structured,
)
from .models import (
    InvestigationPlan,
    MaintenanceAssessment,
    ToolCall,
    ToolResult,
    WatcherEscalation,
)
from .tools import TOOLS, ToolContext, describe_tools, execute_tool

MAX_TOOL_CALLS = 8

SYSTEM_PROMPT = (
    "You are Factora's maintenance specialist on a factory floor. You are "
    "conservative: you never recommend acting without evidence, you cite the "
    "numbers you retrieved, and you answer with a single JSON object only."
)


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


def plan_investigation(
    model: AgentModel,
    escalation: WatcherEscalation,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> InvestigationPlan:
    """Model call 1 — choose which read tools to run."""
    hints = {
        "incident": escalation.model_dump(include={"incident_id", "incident_type",
                                                   "severity", "summary"}),
        "machine": {"machine_id": escalation.machine_id,
                    "state": escalation.machine_state},
        "read_tools": [tool["name"] for tool in describe_tools("read")],
    }
    user = (
        f"Incident {escalation.incident_id} ({escalation.incident_type}, "
        f"severity {escalation.severity}) on {escalation.machine_id}, currently "
        f"{escalation.machine_state}.\n"
        f"Summary: {escalation.summary}\n"
        f"Available read tools:\n"
        + "\n".join(f"- {tool['name']}: {tool['description']}"
                    for tool in describe_tools("read"))
        + "\n\nPick the smallest set of tool calls that establishes what is wrong, "
          "whether it happened before, whether the part is available, and what the "
          "machine is currently doing."
    )
    plan = complete_structured(
        model, InvestigationPlan, system=SYSTEM_PROMPT, user=user,
        task=TASK_INVESTIGATION_PLAN, hints=hints, on_event=on_event)
    return _bound_plan(plan, escalation)


def _bound_plan(plan: InvestigationPlan,
                escalation: WatcherEscalation) -> InvestigationPlan:
    """Drop anything that is not a read tool and bind the known ids.

    Binding `machine_id`/`incident_id` is slot-filling, not invention: both are
    facts of the escalation already in hand, and it keeps small free models from
    emitting a well-shaped call with an empty identifier.
    """
    allowed: list = []
    for call in plan.tool_calls[:MAX_TOOL_CALLS]:
        tool = TOOLS.get(call.name)
        if tool is None or tool.kind != "read":
            continue
        fields = tool.args_model.model_fields
        if "machine_id" in fields and not call.args.get("machine_id"):
            call.args["machine_id"] = escalation.machine_id
        if "incident_id" in fields and not call.args.get("incident_id"):
            call.args["incident_id"] = escalation.incident_id
        allowed.append(call)
    plan.tool_calls = allowed or [ToolCall(
        name="get_machine", args={"machine_id": escalation.machine_id})]
    return plan


@_lazy_span(kind="AGENT", name="maintenance", goal="investigate")
def investigate(
    world: FactoryWorld,
    ctx: ToolContext,
    model: AgentModel,
    escalation: WatcherEscalation,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> tuple[InvestigationPlan, dict[str, ToolResult], MaintenanceAssessment]:
    """Plan -> run tools -> assess. Returns everything the coordinator needs."""
    plan = plan_investigation(model, escalation, on_event=on_event)

    results: dict[str, ToolResult] = {}
    for call in plan.tool_calls:
        result = execute_tool(ctx, call.name, call.args)
        results[call.name] = result
        if on_event:
            on_event("tool", {"name": call.name, "args": call.args,
                              "ok": result.ok,
                              "output": result.output,
                              "error": result.error})

    assessment = assess(model, escalation, plan, results, on_event=on_event)
    return plan, results, assessment


def assess(
    model: AgentModel,
    escalation: WatcherEscalation,
    plan: InvestigationPlan,
    results: dict[str, ToolResult],
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> MaintenanceAssessment:
    """Model call 2 — turn retrieved evidence into a structured recommendation."""
    evidence = {
        name: (result.output if result.ok else {"error": result.error})
        for name, result in results.items()
    }
    hints = {
        "incident": escalation.model_dump(include={"incident_id", "incident_type",
                                                   "severity", "summary"}),
        "machine": {"machine_id": escalation.machine_id,
                    "state": escalation.machine_state},
        "tools": evidence,
    }
    user = (
        f"Goal: establish the probable fault on {escalation.machine_id} and "
        f"recommend a safe response.\n"
        f"Your investigation plan: {plan.rationale}\n"
        f"Tool results:\n"
        + "\n".join(f"- {name}: {result_str}"
                    for name, result in results.items()
                    for result_str in [_compact_result(result)])
        + "\n\nRecommend only reversible actions. If a spare part is required, name "
          "it and report whether it is in stock. In this plant, containment of a "
          "critical machine means both: raise an urgent maintenance work order AND "
          "place the machine in MAINTENANCE."
    )
    return complete_structured(
        model, MaintenanceAssessment, system=SYSTEM_PROMPT, user=user,
        task=TASK_MAINTENANCE_ASSESSMENT, hints=hints, on_event=on_event)


def _compact_result(result: ToolResult, limit: int = 900) -> str:
    import json

    if not result.ok:
        return f"FAILED {result.error}"
    text = json.dumps(result.output, sort_keys=True, default=str)
    return text if len(text) <= limit else text[:limit] + "…"
