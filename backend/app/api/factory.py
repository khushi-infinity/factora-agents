"""Factory APIs: read surface for the simulated world + demo controls.

Responses are typed dicts shaped like the Pydantic models in schemas_factory.py;
the route layer never invents values — every number comes from FactoryWorld.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..agents import build_model, evaluate_world_for_escalations
from ..agents.coordinator import RunOptions, respond_to_escalation
from ..world import get_world
from ..world import repositories as repo
from .schemas_agents import AgentRunOut, run_out_from_row
from .schemas_factory import (
    AdvanceRequest,
    AdvanceResponse,
    AgentRunSummary,
    FactorySnapshot,
    IncidentOut,
    LineOut,
    MachineContext,
    MachineDetail,
    MachineOut,
    MaintenanceOut,
    OEEFactoryOut,
    OEELineOut,
    OEEMachineOut,
    OptimisationOut,
    PlannerItemOut,
    PredictiveRiskOut,
    ProductionJobOut,
    ResetResponse,
    SparePartOut,
    TelemetryOut,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderUpdate,
)

router = APIRouter(tags=["factory"])


def _world():
    world = get_world()
    world.ensure_ready()
    return world


def _require_machine(machine_id: str):
    """Resolve a machine or raise the shared 404. Every machine-scoped route uses it."""
    world = _world()
    machine = world.get_machine(machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"unknown machine {machine_id}")
    return world, machine


def _machine_out(m: dict) -> MachineOut:
    return MachineOut(
        machine_id=m["machine_id"],
        name=m["name"],
        machine_type=m["machine_type"],
        line=m["line"],
        state=m["state"],
        health_score=m["health_score"],
        x_m=m["x_m"],
        y_m=m["y_m"],
        z_m=m["z_m"],
    )


def _machine_detail(m: dict, latest: dict | None) -> MachineDetail:
    return MachineDetail(
        **_machine_out(m).model_dump(),
        manufacturer=m["manufacturer"],
        model=m["model"],
        installed_year=m["installed_year"],
        output_per_hour=m["output_per_hour"],
        cost_per_hour_usd=m["cost_per_hour_usd"],
        contribution_per_unit_usd=m["contribution_per_unit_usd"],
        scrap_cost_per_unit_usd=m["scrap_cost_per_unit_usd"],
        latest_telemetry=TelemetryOut(**latest) if latest else None,
    )


def _incident_out(i: dict) -> IncidentOut:
    return IncidentOut(
        incident_id=i["incident_id"],
        machine_id=i["machine_id"],
        type=i["type"],
        severity=i["severity"],
        status=i["status"],
        opened_at=i["opened_at"],
        resolved_at=i["resolved_at"],
        summary=i["summary"],
        current_owner=i["current_owner"],
        recommended_action=i["recommended_action"],
    )


# ── Row readers shared by the collection routes and /context ────────────────
# One definition per resource: /machines/{id}/maintenance|work-orders|production
# and the aggregated /machines/{id}/context cannot drift apart.


def _maintenance_rows(world, machine_id: str) -> list[MaintenanceOut]:
    return [MaintenanceOut(**r) for r in world.get_machine_history(machine_id)]


def _work_order_rows(world, machine_id: str, *, open_only: bool = False) -> list[WorkOrderOut]:
    return [
        WorkOrderOut(**r)
        for r in repo.work_orders_for_machine(world.conn, machine_id, open_only=open_only)
    ]


def _production_rows(world, machine_id: str) -> list[ProductionJobOut]:
    return [ProductionJobOut(**r) for r in repo.jobs_for_machine(world.conn, machine_id)]


def _incident_rows(world, machine_id: str | None = None) -> list[IncidentOut]:
    return [
        _incident_out(i)
        for i in repo.list_incidents(world.conn)
        if machine_id is None or i["machine_id"] == machine_id
    ]


def _telemetry_rows(world, machine_id: str, limit: int) -> list[TelemetryOut]:
    # world.get_recent_telemetry returns newest → oldest; invert for charts.
    rows = world.get_recent_telemetry(machine_id, limit=limit)
    return [TelemetryOut(**r) for r in reversed(rows)]


@router.get("/factory", response_model=FactorySnapshot)
def factory_snapshot() -> FactorySnapshot:
    world = _world()
    snap = world.get_factory_snapshot()
    return FactorySnapshot(
        clock=snap["clock"],
        machine_count=snap["machine_count"],
        state_distribution=snap["state_distribution"],
        open_incidents=[_incident_out(i) for i in snap["open_incidents"]],
    )


@router.get("/machines", response_model=list[MachineOut])
def machines() -> list[MachineOut]:
    world = _world()
    return [_machine_out(m) for m in repo.list_machines(world.conn)]


@router.get("/machines/{machine_id}", response_model=MachineDetail)
def machine_detail(machine_id: str) -> MachineDetail:
    world, machine = _require_machine(machine_id)
    return _machine_detail(machine, repo.latest_reading(world.conn, machine_id))


@router.get("/machines/{machine_id}/telemetry", response_model=list[TelemetryOut])
def machine_telemetry(
    machine_id: str,
    limit: int = Query(default=24, ge=1, le=500),
) -> list[TelemetryOut]:
    world, _ = _require_machine(machine_id)
    return _telemetry_rows(world, machine_id, limit)


@router.get("/factory/lines", response_model=list[LineOut])
def factory_lines() -> list[LineOut]:
    """Line groupings for the twin floor (authoritative from machines table)."""
    lines: dict[str, list[str]] = {}
    world = _world()
    for machine in repo.list_machines(world.conn):
        lines.setdefault(machine["line"], []).append(machine["machine_id"])
    return [
        LineOut(line=line, machine_ids=ids, machine_count=len(ids))
        for line, ids in sorted(lines.items())
    ]


@router.get("/machines/{machine_id}/maintenance", response_model=list[MaintenanceOut])
def machine_maintenance(machine_id: str) -> list[MaintenanceOut]:
    world, _ = _require_machine(machine_id)
    return _maintenance_rows(world, machine_id)


@router.get("/machines/{machine_id}/work-orders", response_model=list[WorkOrderOut])
def machine_work_orders(
    machine_id: str, open_only: bool = Query(default=False)
) -> list[WorkOrderOut]:
    world, _ = _require_machine(machine_id)
    return _work_order_rows(world, machine_id, open_only=open_only)


@router.get("/machines/{machine_id}/production", response_model=list[ProductionJobOut])
def machine_production(machine_id: str) -> list[ProductionJobOut]:
    world, _ = _require_machine(machine_id)
    return _production_rows(world, machine_id)


@router.get("/machines/{machine_id}/context", response_model=MachineContext)
def machine_context(machine_id: str) -> MachineContext:
    """One-stop Machine Inspector payload: identity + telemetry + history + jobs + incidents.

    Composes the same row readers as the individual sub-resource routes above,
    so the aggregated and the split views can never disagree.
    """
    world, machine = _require_machine(machine_id)
    return MachineContext(
        machine=_machine_detail(machine, repo.latest_reading(world.conn, machine_id)),
        telemetry=_telemetry_rows(world, machine_id, limit=36),
        maintenance=_maintenance_rows(world, machine_id),
        work_orders=_work_order_rows(world, machine_id),
        production=_production_rows(world, machine_id),
        incidents=_incident_rows(world, machine_id),
    )


@router.get("/incidents", response_model=list[IncidentOut])
def incidents() -> list[IncidentOut]:
    return _incident_rows(_world())


@router.post("/demo/reset", response_model=ResetResponse)
def demo_reset() -> ResetResponse:
    """Deterministic reset: reseed + clock back to epoch, agent runs cleared."""
    world = _world()
    counts = world.reset_world()
    clock = world.clock()
    return ResetResponse(
        status="reset",
        clock=clock.iso(),
        machines=counts["machines"],
        telemetry_rows=counts["telemetry_rows"],
    )


@router.post("/demo/advance", response_model=AdvanceResponse)
def demo_advance(request: AdvanceRequest) -> AdvanceResponse:
    """Advance the simulation, then let the Factory Watcher react (N3).

    No "Run Agent" button: advancing the world *is* the trigger. The watcher
    pre-filters deterministically, so a quiet world costs zero model calls.
    """
    world = _world()
    try:
        result = world.advance(request.minutes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    agent_runs: list[AgentRunOut] = []
    watcher_state: Literal["escalated", "quiet"] = "quiet"
    if request.trigger_agents:
        model = build_model()
        options = RunOptions(fail_first_work_order=request.fail_first_work_order)
        escalations = evaluate_world_for_escalations(world)
        for escalation in escalations:
            respond_to_escalation(world, escalation, model, options)
        if escalations:
            watcher_state = "escalated"
            agent_runs = [
                run_out_from_row(row)
                for row in world.get_agent_runs(escalation.incident_id)
            ]

    machine = world.get_machine("CNC-03")
    return AdvanceResponse(
        clock=result["clock"],
        emitted_readings=result["emitted_readings"],
        cnc03_state=machine["state"] if machine else None,
        open_incidents=len(world.get_active_incidents()),
        agent_runs=agent_runs,
        watcher=watcher_state,
    )


# ── Spare Parts ─────────────────────────────────────────────────────────────

@router.get("/spare-parts", response_model=list[SparePartOut])
def spare_parts() -> list[SparePartOut]:
    world = _world()
    return [SparePartOut(**r) for r in repo.list_spare_parts(world.conn)]


@router.get("/spare-parts/{part_id}", response_model=SparePartOut)
def spare_part_detail(part_id: str) -> SparePartOut:
    world = _world()
    part = repo.get_spare_part(world.conn, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"unknown part {part_id}")
    return SparePartOut(**part)


# ── Work Orders ─────────────────────────────────────────────────────────────

@router.get("/work-orders", response_model=list[WorkOrderOut])
def work_orders(open_only: bool = Query(default=False)) -> list[WorkOrderOut]:
    world = _world()
    return [WorkOrderOut(**r) for r in repo.list_work_orders(world.conn, open_only=open_only)]


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderOut)
def work_order_detail(work_order_id: str) -> WorkOrderOut:
    world = _world()
    wo = repo.list_work_orders(world.conn, open_only=False)
    found = next((r for r in wo if r["work_order_id"] == work_order_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown work order {work_order_id}")
    return WorkOrderOut(**found)


@router.post("/work-orders", response_model=WorkOrderOut)
def create_work_order(payload: WorkOrderCreate) -> WorkOrderOut:
    world = _world()
    wo = {
        "work_order_id": world.next_id("work_orders", "work_order_id", "WO"),
        "machine_id": payload.machine_id,
        "issue": payload.issue,
        "proposed_action": payload.proposed_action,
        "status": "OPEN",
        "priority": payload.priority,
        "scheduled_for": None,
        "estimated_cost_usd": payload.estimated_cost_usd,
        "source": "MANUAL",
        "created_at": world.clock().iso(),
    }
    repo.insert_work_order(world.conn, wo)
    with world.conn:
        pass
    return WorkOrderOut(**wo)


@router.patch("/work-orders/{work_order_id}", response_model=WorkOrderOut)
def update_work_order(work_order_id: str, payload: WorkOrderUpdate) -> WorkOrderOut:
    world = _world()
    wo = repo.work_orders_for_machine(world.conn, None, open_only=False)
    found = next((r for r in wo if r["work_order_id"] == work_order_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown work order {work_order_id}")
    
    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.priority is not None:
        updates["priority"] = payload.priority
    if payload.estimated_cost_usd is not None:
        updates["estimated_cost_usd"] = payload.estimated_cost_usd
    
    if updates:
        repo.update_work_order(world.conn, work_order_id, updates)
        with world.conn:
            pass
    
    wo = repo.work_orders_for_machine(world.conn, None, open_only=False)
    updated = next((r for r in wo if r["work_order_id"] == work_order_id), None)
    return WorkOrderOut(**updated)


# ── OEE ─────────────────────────────────────────────────────────────────────

@router.get("/oee", response_model=OEEFactoryOut)
def oee_factory() -> OEEFactoryOut:
    world = _world()
    oee_data = world.compute_oee()
    return OEEFactoryOut(**oee_data)


@router.get("/oee/lines", response_model=list[OEELineOut])
def oee_lines() -> list[OEELineOut]:
    world = _world()
    oee_data = world.compute_oee()
    return [OEELineOut(**line) for line in oee_data["lines"]]


@router.get("/oee/machines", response_model=list[OEEMachineOut])
def oee_machines() -> list[OEEMachineOut]:
    world = _world()
    oee_data = world.compute_oee()
    return [OEEMachineOut(**m) for m in oee_data["machines"]]


# ── Predictive Maintenance ──────────────────────────────────────────────────

@router.get("/predictive-maintenance", response_model=list[PredictiveRiskOut])
def predictive_maintenance() -> list[PredictiveRiskOut]:
    world = _world()
    risks = world.compute_predictive_risk()
    return [PredictiveRiskOut(**r) for r in risks]


# ── Planner ──────────────────────────────────────────────────────────────────

@router.get("/planner", response_model=list[PlannerItemOut])
def planner() -> list[PlannerItemOut]:
    world = _world()
    items = world.get_planner_items()
    return [PlannerItemOut(**item) for item in items]


# ── Agent Runs ──────────────────────────────────────────────────────────────

@router.get("/agent-runs", response_model=list[AgentRunSummary])
def agent_runs(incident_id: str | None = Query(default=None)) -> list[AgentRunSummary]:
    world = _world()
    runs = world.get_agent_runs(incident_id)
    return [AgentRunSummary(
        run_id=r["run_id"],
        incident_id=r["incident_id"],
        machine_id=r["machine_id"],
        goal=r["goal"],
        status=r["status"],
        active_agent=r["active_agent"],
        model_provider=r["model_provider"],
        model_name=r["model_name"],
        outcome=r["outcome"],
        started_at=r["started_at"],
        completed_at=r["completed_at"],
        fail_first_work_order=r["fail_first_work_order"],
    ) for r in runs]


@router.get("/agent-runs/{run_id}/detail", response_model=dict)
def agent_run_detail(run_id: str) -> dict:
    world = _world()
    run = world.get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown agent run {run_id}")
    steps = world.get_agent_steps(run_id)
    return {"run": run, "steps": steps}


# ── Optimisation ─────────────────────────────────────────────────────────────

@router.get("/optimisation/{incident_id}", response_model=OptimisationOut)
def optimisation_detail(incident_id: str) -> OptimisationOut:
    world = _world()
    opt = world.get_optimisation(incident_id)
    if opt is None:
        raise HTTPException(status_code=404, detail=f"no optimisation for incident {incident_id}")
    return OptimisationOut(**opt)
