"""Typed payloads for the N1 factory API (fresh implementation)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MachineState = Literal["HEALTHY", "WARNING", "CRITICAL", "MAINTENANCE", "OFFLINE"]


class MachineOut(BaseModel):
    machine_id: str
    name: str
    machine_type: str
    line: str
    state: MachineState
    health_score: int | None
    x_m: float
    y_m: float
    z_m: float


class TelemetryOut(BaseModel):
    machine_id: str
    ts: str
    vibration_mm_s: float
    bearing_temp_c: float
    spindle_rpm: float | None = None
    motor_current_a: float | None = None
    cycle_time_s: float | None = None
    production_rate_uph: float | None = None
    defect_rate_pct: float | None = None


class MachineDetail(MachineOut):
    manufacturer: str | None = None
    model: str | None = None
    installed_year: int | None = None
    output_per_hour: float
    cost_per_hour_usd: float
    contribution_per_unit_usd: float
    scrap_cost_per_unit_usd: float
    latest_telemetry: TelemetryOut | None = None


class IncidentOut(BaseModel):
    incident_id: str
    machine_id: str
    type: str
    severity: str
    status: str
    opened_at: str
    resolved_at: str | None = None
    summary: str
    current_owner: str | None = None
    recommended_action: str | None = None


class FactorySnapshot(BaseModel):
    clock: str
    machine_count: int
    state_distribution: dict[str, int]
    open_incidents: list[IncidentOut]


class ResetResponse(BaseModel):
    status: Literal["reset"]
    clock: str
    machines: int
    telemetry_rows: int


class AdvanceRequest(BaseModel):
    minutes: int = Field(gt=0, le=24 * 60, description="sim minutes to advance (10-min ticks)")


class AdvanceResponse(BaseModel):
    clock: str
    emitted_readings: int
    cnc03_state: MachineState | None
    open_incidents: int
