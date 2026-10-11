"""Agent API: observability of the autonomous loop + a manual trigger.

The flagship demo does not use the manual trigger — `POST /api/demo/advance`
runs the watcher after every world advance and starts a run when it escalates.
This router exists so the UI can render runs and so a developer can replay a
single incident on demand.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..agents import build_model, evaluate_world_for_escalations
from ..agents.coordinator import RunOptions, respond_to_escalation
from ..agents.models import ActionKind
from ..observability import get_observability
from ..world import get_world
from .schemas_agents import (
    AgentRunDetailOut,
    AgentRunOut,
    AgentRunStartedOut,
    AgentStatusOut,
    AgentStepOut,
    _load,
    run_out_from_row,
)

router = APIRouter(tags=["agents"])


def _world():
    world = get_world()
    world.ensure_ready()
    return world


def _run_out(row: dict) -> AgentRunOut:
    return run_out_from_row(row)


def _step_out(row: dict) -> AgentStepOut:
    return AgentStepOut(
        sequence=row["sequence"], agent=row["agent"], type=row["type"],
        summary=row["summary"], tool_name=row["tool_name"],
        input=_load(row["input"]), output=_load(row["output"]),
        status=row["status"], timestamp=row["timestamp"])


@router.get("/agents/status", response_model=AgentStatusOut)
def agent_status() -> AgentStatusOut:
    """Which model would answer right now — never faked."""
    model = build_model()
    return AgentStatusOut(
        model_provider=model.info.provider,
        model_name=model.info.name,
        mode=model.info.mode.value,
        detail=model.info.detail,
        observability=get_observability().status,
        autonomous_actions=[kind.value for kind in ActionKind],
        failure_injection_available=True,
    )


@router.get("/agents/runs", response_model=list[AgentRunOut])
def list_runs(incident_id: str | None = None) -> list[AgentRunOut]:
    return [_run_out(row) for row in _world().get_agent_runs(incident_id)]


@router.get("/agents/runs/{run_id}", response_model=AgentRunDetailOut)
def get_run(run_id: str) -> AgentRunDetailOut:
    world = _world()
    row = world.get_agent_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
    return AgentRunDetailOut(**_run_out(row).model_dump(),
                             steps=[_step_out(step)
                                    for step in world.get_agent_steps(run_id)])


@router.post("/agents/run", response_model=AgentRunStartedOut)
def manual_run() -> AgentRunStartedOut:
    """Debug/manual trigger: run the watcher now and respond to any escalation."""
    world = _world()
    model = build_model()
    escalations = evaluate_world_for_escalations(world)
    [respond_to_escalation(world, escalation, model, RunOptions())
                for escalation in escalations]
    runs = [_run_out(row) for row in world.get_agent_runs()]
    note = (f"{len(escalations)} escalation(s) found" if escalations
            else "nothing to do: no critical incident needs an autonomous response")
    return AgentRunStartedOut(runs=runs, escalations=len(escalations), note=note)
