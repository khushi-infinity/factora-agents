"""Typed payloads for the agent API (N3)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


def _load(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


class AgentStatusOut(BaseModel):
    """Which model actually answers, and whether tracing is on. Never faked."""

    model_provider: str
    model_name: str
    mode: str = Field(description="REAL LLM or DETERMINISTIC TEST MODEL")
    detail: str
    observability: str
    autonomous_actions: list[str]
    failure_injection_available: bool


class AgentRunOut(BaseModel):
    run_id: str
    incident_id: str
    machine_id: str
    goal: str
    status: str
    active_agent: str | None
    model_provider: str
    model_name: str
    outcome: str | None
    started_at: str
    completed_at: str | None
    fail_first_work_order: bool


class AgentStepOut(BaseModel):
    sequence: int
    agent: str
    type: str
    summary: str
    tool_name: str | None
    input: Any = None
    output: Any = None
    status: str
    timestamp: str


class AgentRunDetailOut(AgentRunOut):
    steps: list[AgentStepOut]


class AgentRunRequest(BaseModel):
    """Manual/debug run trigger. The flagship demo uses /demo/advance instead."""

    incident_id: str | None = None
    machine_id: str | None = None


class AgentRunStartedOut(BaseModel):
    runs: list[AgentRunOut]
    escalations: int
    note: str


def run_out_from_row(row: dict) -> AgentRunOut:
    """Map an `agent_runs` row onto its API shape (shared by both routers)."""
    return AgentRunOut(
        run_id=row["run_id"], incident_id=row["incident_id"],
        machine_id=row["machine_id"], goal=row["goal"], status=row["status"],
        active_agent=row["active_agent"], model_provider=row["model_provider"],
        model_name=row["model_name"], outcome=row["outcome"],
        started_at=row["started_at"], completed_at=row["completed_at"],
        fail_first_work_order=bool(row["fail_first_work_order"]))
