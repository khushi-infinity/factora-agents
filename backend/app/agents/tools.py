"""Typed tool layer for the N3 agents.

Rules (N3):

  * agents never run SQL and never import repositories — every tool goes
    through the FactoryWorld service facade;
  * every tool has a name, a description, a validated argument model and a
    structured result; failures come back as explicit error envelopes so the
    coordinator can recover instead of crashing;
  * only two *action* tools exist, both safe and reversible, and both are
    reachable solely after the deterministic action policy has approved them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..world import repositories as repo
from ..world.simulation import FactoryWorld
from .models import ToolExecutionError, ToolResult

MAX_TELEMETRY_IN_TOOL = 12   # keep free-model context tiny


# ── failure injection (demo recovery scenario only) ────────────────────────
class FailureInjector:
    """Deterministic, opt-in tool failure. Never random, never on by default."""

    def __init__(self, fail_first_work_order: bool = False) -> None:
        self.fail_first_work_order = fail_first_work_order
        self._work_order_attempts = 0
        self.injected_failures: list[str] = []

    def work_order_attempt(self) -> int:
        """Consume one attempt; returns 1 on the first call when injection is on."""
        self._work_order_attempts += 1
        return self._work_order_attempts

    def maybe_fail_work_order(self) -> None:
        if not self.fail_first_work_order:
            return
        if self.work_order_attempt() == 1:
            self.injected_failures.append("create_maintenance_work_order")
            raise ToolExecutionError(
                "work-order service temporarily unavailable (injected failure)",
                code="TRANSIENT_FAILURE",
            )


# ── tool context ───────────────────────────────────────────────────────────
@dataclass
class ToolContext:
    """Everything a tool may touch. No global state, no hidden handles."""

    world: FactoryWorld
    run_id: str | None = None
    incident_id: str | None = None
    fail_injector: FailureInjector = field(default_factory=FailureInjector)
    # N4 helpers for the production/finance read tools (set per phase).
    phase_machine_id: str | None = None
    phase_paused_job_id: str | None = None

    def incident_machine_id(self) -> str:
        """The machine the run's optimisation phase is working on."""
        if self.phase_machine_id:
            return self.phase_machine_id
        if self.incident_id:
            incident = self.world.get_incident(self.incident_id)
            return (incident or {}).get("machine_id") or ""
        return ""

    def incident_paused_job_id(self) -> str | None:
        """The paused job the run's optimisation phase is working on."""
        if self.phase_paused_job_id:
            return self.phase_paused_job_id
        machine_id = self.incident_machine_id()
        if not machine_id:
            return None
        paused = [j for j in self.world.get_active_jobs_all()
                  if j["machine_id"] == machine_id and j["status"] == "PAUSED"]
        return paused[0]["job_id"] if paused else None


# ── argument models ────────────────────────────────────────────────────────
class MachineArgs(BaseModel):
    machine_id: str = Field(default="", max_length=32)


class TelemetryArgs(MachineArgs):
    limit: int = Field(default=6, ge=1, le=MAX_TELEMETRY_IN_TOOL)


class PartArgs(BaseModel):
    part_id: str = Field(min_length=3, max_length=32)


class IncidentArgs(BaseModel):
    incident_id: str = Field(min_length=3, max_length=64)


class WorkOrderArgs(MachineArgs):
    issue: str = Field(min_length=4, max_length=200)
    proposed_action: str = Field(min_length=4, max_length=300)
    priority: Literal["low", "medium", "high", "critical"] = "critical"
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, le=100_000.0)


class MaintenanceArgs(MachineArgs):
    reason: str = Field(min_length=4, max_length=400)


# ── handlers ───────────────────────────────────────────────────────────────
def _get_machine(ctx: ToolContext, args: MachineArgs) -> dict[str, Any]:
    machine = ctx.world.get_machine(args.machine_id)
    if machine is None:
        raise ToolExecutionError(f"unknown machine '{args.machine_id}'",
                                 code="NOT_FOUND")
    return {"machine": machine}


def _get_recent_telemetry(ctx: ToolContext, args: TelemetryArgs) -> dict[str, Any]:
    readings = ctx.world.get_recent_telemetry(args.machine_id, args.limit)
    if not readings:
        raise ToolExecutionError(f"no telemetry for '{args.machine_id}'",
                                 code="NOT_FOUND")
    first, last = readings[0], readings[-1]
    trend = {
        "vibration_mm_s": {
            "first": first["vibration_mm_s"], "last": last["vibration_mm_s"],
            "delta": round(last["vibration_mm_s"] - first["vibration_mm_s"], 3),
        },
        "bearing_temp_c": {
            "first": first["bearing_temp_c"], "last": last["bearing_temp_c"],
            "delta": round(last["bearing_temp_c"] - first["bearing_temp_c"], 3),
        },
        "window_readings": len(readings),
        "from_ts": first["ts"], "to_ts": last["ts"],
    }
    return {"trend": trend, "readings": readings}


def _get_maintenance_history(ctx: ToolContext, args: MachineArgs) -> dict[str, Any]:
    return {"events": ctx.world.get_machine_history(args.machine_id)}


def _get_spare_part(ctx: ToolContext, args: PartArgs) -> dict[str, Any]:
    part = ctx.world.get_spare_part(args.part_id)
    if part is None:
        raise ToolExecutionError(f"unknown part '{args.part_id}'", code="NOT_FOUND")
    return {"part": part, "in_stock": part["stock_qty"] > 0}


def _get_open_work_orders(ctx: ToolContext, args: MachineArgs) -> dict[str, Any]:
    return {"work_orders": ctx.world.get_open_work_orders(args.machine_id)}


def _get_current_production_job(ctx: ToolContext, args: MachineArgs) -> dict[str, Any]:
    jobs = ctx.world.get_jobs(args.machine_id, status="RUNNING")
    queued = ctx.world.get_jobs(args.machine_id, status="QUEUED")
    return {"running": jobs[0] if jobs else None, "queued_count": len(queued)}


def _get_active_incident(ctx: ToolContext, args: IncidentArgs) -> dict[str, Any]:
    incident = ctx.world.get_incident(args.incident_id)
    if incident is None:
        raise ToolExecutionError(f"unknown incident '{args.incident_id}'",
                                 code="NOT_FOUND")
    return {"incident": incident, "evidence": repo.evidence_of(incident)}


def _create_maintenance_work_order(ctx: ToolContext, args: WorkOrderArgs) -> dict[str, Any]:
    if ctx.run_id is None:
        raise ToolExecutionError("action tools require an agent run",
                                 code="NO_RUN_CONTEXT")
    ctx.fail_injector.maybe_fail_work_order()

    work_order_id = repo.next_numeric_id(ctx.world.conn, "work_orders",
                                         "work_order_id", "WO")
    now_iso = ctx.world.clock().iso()
    row = {
        "work_order_id": work_order_id,
        "machine_id": args.machine_id,
        "issue": args.issue,
        "proposed_action": args.proposed_action,
        "status": "OPEN",
        "priority": args.priority,
        "scheduled_for": now_iso,
        "estimated_cost_usd": args.estimated_cost_usd,
        "source": "AGENT",
        "created_at": now_iso,
    }
    repo.insert_work_order(ctx.world.conn, row)
    return {"work_order": row, "related_incident_id": ctx.incident_id,
            "run_id": ctx.run_id}


def _place_machine_in_maintenance(ctx: ToolContext, args: MaintenanceArgs) -> dict[str, Any]:
    if ctx.run_id is None:
        raise ToolExecutionError("action tools require an agent run",
                                 code="NO_RUN_CONTEXT")
    machine = ctx.world.get_machine(args.machine_id)
    if machine is None:
        raise ToolExecutionError(f"unknown machine '{args.machine_id}'",
                                 code="NOT_FOUND")
    ctx.world.set_machine_state(args.machine_id, "MAINTENANCE",
                                machine["health_score"])
    # Containment also stops the machine's running production (reversibly):
    # the paused job ids go into the payload so observers can prove it.
    paused_jobs = ctx.world.pause_active_jobs(args.machine_id)
    return {"machine_id": args.machine_id, "state": "MAINTENANCE",
            "changed": True, "reason": args.reason, "paused_job_ids": paused_jobs}


# ── registry ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], dict[str, Any]]
    kind: Literal["read", "action"]

    def spec(self) -> dict[str, Any]:
        """Public description handed to the model (name, purpose, arguments)."""
        return {
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "arguments": self.args_model.model_json_schema(),
        }


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool("get_machine", "Current state, health score and line of one machine.",
             MachineArgs, _get_machine, "read"),
        Tool("get_recent_telemetry",
             f"Last N sensor readings for one machine (max {MAX_TELEMETRY_IN_TOOL}) "
             "plus a first/last trend summary.",
             TelemetryArgs, _get_recent_telemetry, "read"),
        Tool("get_maintenance_history",
             "Past maintenance events for one machine, including parts replaced.",
             MachineArgs, _get_maintenance_history, "read"),
        Tool("get_spare_part",
             "Stock, reorder point, lead time and supplier for one spare part.",
             PartArgs, _get_spare_part, "read"),
        Tool("get_open_work_orders",
             "Open/assigned/in-progress work orders for one machine.",
             MachineArgs, _get_open_work_orders, "read"),
        Tool("get_current_production_job",
             "The running production job for one machine and queued job count.",
             MachineArgs, _get_current_production_job, "read"),
        Tool("get_active_incident",
             "One incident with its structured evidence list.",
             IncidentArgs, _get_active_incident, "read"),
        Tool("create_maintenance_work_order",
             "ACTION (policy-gated). Raise an urgent maintenance work order that "
             "a technician will schedule; reversible by cancelling it.",
             WorkOrderArgs, _create_maintenance_work_order, "action"),
        Tool("place_machine_in_maintenance",
             "ACTION (policy-gated). Take a machine out of service into MAINTENANCE "
             "so it stops producing; reversible by returning it to service.",
             MaintenanceArgs, _place_machine_in_maintenance, "action"),
    )
}

# N4 tools register alongside the N3 set. The import must happen here, at the
# bottom, because tools_n4 imports arg models back from this module — a top-of-
# file import would hit this module half-initialised (ImportError → silent,
# tools missing at runtime, exactly the bug to avoid).
from .tools_n4 import N4_TOOLS  # noqa: E402  (deliberate bottom import)

TOOLS.update(N4_TOOLS)


def describe_tools(kind: Literal["read", "action"] | None = None) -> list[dict]:
    specs = [tool.spec() for tool in TOOLS.values()]
    if kind is None:
        return specs
    return [spec for spec, tool in zip(specs, TOOLS.values(), strict=False) if tool.kind == kind]


def execute_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> ToolResult:
    """Run one tool call. Never raises: errors become explicit result envelopes."""
    tool = TOOLS.get(name)
    if tool is None:
        return ToolResult(name=name, ok=False, error={
            "code": "UNKNOWN_TOOL", "message": f"no tool named '{name}'"})

    try:
        validated = tool.args_model.model_validate(args)
    except ValidationError as exc:
        return ToolResult(name=name, ok=False, error={
            "code": "INVALID_ARGUMENTS",
            "message": "; ".join(
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()[:4])})

    try:
        output = tool.handler(ctx, validated)
    except ToolExecutionError as exc:
        return ToolResult(name=name, ok=False, error={
            "code": exc.code, "message": exc.message})
    except Exception as exc:  # pragma: no cover - defensive, never expected
        return ToolResult(name=name, ok=False, error={
            "code": "INTERNAL_ERROR", "message": f"{type(exc).__name__}: {exc}"})

    return ToolResult(name=name, ok=True, output=_compact(output))


def _compact(value: Any, depth: int = 0) -> Any:
    """Trim payloads so a tool result stays small enough for a free model."""
    if depth > 3:
        return "…"
    if isinstance(value, dict):
        return {key: _compact(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [_compact(item, depth + 1) for item in value[:MAX_TELEMETRY_IN_TOOL]]
    if isinstance(value, float):
        return round(value, 3)
    return value


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)
