"""Factory APIs (N1): read surface for the simulated world + demo controls.

Responses are typed dicts shaped like the Pydantic models in schemas_factory.py;
the route layer never invents values — every number comes from FactoryWorld.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..world import get_world
from ..world import repositories as repo
from ..world.clock import Clock
from .schemas_factory import (
    AdvanceRequest,
    AdvanceResponse,
    FactorySnapshot,
    IncidentOut,
    MachineDetail,
    MachineOut,
    ResetResponse,
    TelemetryOut,
)

router = APIRouter(tags=["factory"])


def _world():
    world = get_world()
    world.ensure_ready()
    return world


@router.get("/factory", response_model=FactorySnapshot)
def factory_snapshot() -> FactorySnapshot:
    world = _world()
    snap = world.get_factory_snapshot()
    return FactorySnapshot(
        clock=snap["clock"],
        machine_count=snap["machine_count"],
        state_distribution=snap["state_distribution"],
        open_incidents=[
            IncidentOut(
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
            for i in snap["open_incidents"]
        ],
    )


@router.get("/machines", response_model=list[MachineOut])
def machines() -> list[MachineOut]:
    world = _world()
    return [
        MachineOut(
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
        for m in repo.list_machines(world.conn)
    ]


@router.get("/machines/{machine_id}", response_model=MachineDetail)
def machine_detail(machine_id: str) -> MachineDetail:
    world = _world()
    machine = world.get_machine(machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"unknown machine {machine_id}")
    latest = repo.latest_reading(world.conn, machine_id)
    return MachineDetail(
        **_machine_out(machine).model_dump(),
        manufacturer=machine["manufacturer"],
        model=machine["model"],
        installed_year=machine["installed_year"],
        output_per_hour=machine["output_per_hour"],
        cost_per_hour_usd=machine["cost_per_hour_usd"],
        contribution_per_unit_usd=machine["contribution_per_unit_usd"],
        scrap_cost_per_unit_usd=machine["scrap_cost_per_unit_usd"],
        latest_telemetry=TelemetryOut(**latest) if latest else None,
    )


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


@router.get("/machines/{machine_id}/telemetry", response_model=list[TelemetryOut])
def machine_telemetry(
    machine_id: str,
    limit: int = Query(default=24, ge=1, le=500),
) -> list[TelemetryOut]:
    world = _world()
    if world.get_machine(machine_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown machine {machine_id}")
    rows = world.get_recent_telemetry(machine_id, limit=limit)
    return [TelemetryOut(**r) for r in reversed(rows)]    # oldest → newest


@router.get("/incidents", response_model=list[IncidentOut])
def incidents() -> list[IncidentOut]:
    world = _world()
    return [
        IncidentOut(
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
        for i in repo.list_incidents(world.conn)
    ]


@router.post("/demo/reset", response_model=ResetResponse)
def demo_reset() -> ResetResponse:
    """Deterministic reset: reseed + clock back to epoch (no agents involved)."""
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
    world = _world()
    try:
        result = world.advance(request.minutes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    machine = world.get_machine("CNC-03")
    return AdvanceResponse(
        clock=result["clock"],
        emitted_readings=result["emitted_readings"],
        cnc03_state=machine["state"] if machine else None,
        open_incidents=len(world.get_active_incidents()),
    )


# Clock import kept for typing symmetry with simulations elsewhere in the module family.
_ = Clock
