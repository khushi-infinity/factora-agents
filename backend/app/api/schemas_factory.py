"""Typed payloads for the factory API (fresh implementation; N2 additions below)."""

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


class MaintenanceOut(BaseModel):
    event_id: int
    machine_id: str
    event_date: str
    issue: str
    action: str
    part_id: str | None = None
    downtime_hours: float
    cost_usd: float | None = None


class WorkOrderOut(BaseModel):
    work_order_id: str
    machine_id: str
    issue: str
    proposed_action: str
    status: str
    priority: str
    scheduled_for: str | None = None
    estimated_cost_usd: float | None = None
    source: str
    created_at: str


class ProductionJobOut(BaseModel):
    job_id: str
    part_no: str
    machine_id: str
    target_qty: int
    produced_qty: int
    good_qty: int
    scrap_qty: int
    status: str
    started_at: str | None = None
    due_at: str | None = None
    priority: int


class LineOut(BaseModel):
    line: str
    machine_ids: list[str]
    machine_count: int


class MachineContext(BaseModel):
    """One-stop contextual payload for the Machine Inspector (plan §14)."""

    machine: MachineDetail
    telemetry: list[TelemetryOut] = Field(description="recent readings, oldest → newest")
    maintenance: list[MaintenanceOut]
    work_orders: list[WorkOrderOut]
    production: list[ProductionJobOut]
    incidents: list[IncidentOut]
    economics_note: Literal["Synthetic demo economics"] = "Synthetic demo economics"


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
