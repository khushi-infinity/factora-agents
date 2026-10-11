"""Typed payloads for the factory API (fresh implementation; N2 additions below)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .schemas_agents import AgentRunOut

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
    trigger_agents: bool = Field(
        default=True,
        description="run the Factory Watcher after advancing (autonomous response)")
    fail_first_work_order: bool = Field(
        default=False,
        description="demo recovery scenario: inject one work-order tool failure")


class AdvanceResponse(BaseModel):
    clock: str
    emitted_readings: int
    cnc03_state: MachineState | None
    open_incidents: int
    agent_runs: list[AgentRunOut] = Field(
        default_factory=list,
        description="runs started by the watcher during this advance")
    watcher: Literal["escalated", "quiet"]


# ── Spare Parts ─────────────────────────────────────────────────────────────

class SparePartOut(BaseModel):
    part_id: str
    name: str
    category: str
    compatible_types: str
    stock_qty: int
    reorder_point: int
    unit_cost_usd: float
    lead_time_days: int
    supplier: str | None = None

    @property
    def stock_status(self) -> Literal["IN_STOCK", "LOW_STOCK", "CRITICAL_STOCK"]:
        if self.stock_qty <= 0:
            return "CRITICAL_STOCK"
        if self.stock_qty <= self.reorder_point:
            return "LOW_STOCK"
        return "IN_STOCK"


# ── Work Orders ─────────────────────────────────────────────────────────────

class WorkOrderCreate(BaseModel):
    machine_id: str
    issue: str
    proposed_action: str
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    estimated_cost_usd: float | None = None


class WorkOrderUpdate(BaseModel):
    status: Literal["OPEN", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"] | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    estimated_cost_usd: float | None = None


# ── OEE ─────────────────────────────────────────────────────────────────────

class OEEBreakdown(BaseModel):
    availability: float
    performance: float
    quality: float
    oee: float

    downtime_hours: float
    planned_downtime_hours: float
    unplanned_downtime_hours: float
    lost_speed_units: float
    scrap_units: int
    total_produced: int
    good_units: int


class OEELineOut(BaseModel):
    line: str
    oee: float
    availability: float
    performance: float
    quality: float
    machines: int


class OEEMachineOut(BaseModel):
    machine_id: str
    line: str
    oee: float
    availability: float
    performance: float
    quality: float
    target_units: int
    actual_units: int
    good_units: int
    scrap_units: int
    unplanned_downtime_hours: float


class OEEFactoryOut(BaseModel):
    factory_oee: float
    lines: list[OEELineOut]
    machines: list[OEEMachineOut]
    loss_breakdown: dict[str, float]


# ── Predictive Maintenance ──────────────────────────────────────────────────

class PredictiveRiskOut(BaseModel):
    machine_id: str
    name: str
    line: str
    machine_type: str
    risk_score: float
    trend: Literal["improving", "stable", "degrading"]
    likely_issue: str | None
    evidence: list[str]
    urgency: Literal["high", "medium", "low"]
    spare_part_id: str | None
    open_work_orders: int
    risk_category: Literal["HIGH", "MEDIUM", "LOW"]


# ── Planner ──────────────────────────────────────────────────────────────────

class PlannerItemOut(BaseModel):
    work_order_id: str
    machine_id: str
    machine_name: str
    machine_type: str
    line: str
    issue: str
    priority: str
    status: str
    scheduled_for: str | None
    estimated_cost_usd: float | None
    required_parts: list[str]
    parts_available: bool
    estimated_downtime_hours: float
    estimated_cost_usd: float
    production_impact_usd: float
    source: str


# ── Agent Runs (extended) ───────────────────────────────────────────────────

class AgentRunSummary(BaseModel):
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


# ── Optimisation ─────────────────────────────────────────────────────────────

class OptimisationOut(BaseModel):
    paused_job_id: str
    source_machine_id: str
    target_machine_id: str | None
    candidates: list[dict]
    recommended_candidate: str | None
    do_nothing_cost_usd: float
    reroute_cost_usd: float
    loss_avoided_usd: float
    net_benefit_usd: float
    finance_recommendation: Literal["REROUTE", "WAIT"]
    action_taken: Literal["REROUTE", "WAIT"]
    verification: dict | None = None
