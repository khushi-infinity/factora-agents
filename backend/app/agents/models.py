"""Typed contracts for the N3 autonomous incident-response loop.

Everything the agents exchange is a validated Pydantic model: the model output
is parsed into one of these and rejected if malformed, tool calls carry typed
arguments, and the coordinator's state machine is an enum rather than a free
string. No workflow state ever lives only inside a prompt.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    """Coordinator-owned run lifecycle. Transitions are enforced in code."""

    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    PLANNING = "PLANNING"
    ACTION_PENDING = "ACTION_PENDING"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


TERMINAL_STATUSES = frozenset(
    {RunStatus.VERIFIED, RunStatus.FAILED, RunStatus.ESCALATED})

# Explicit transition table — the model never emits these.
ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.DETECTED: frozenset({RunStatus.INVESTIGATING, RunStatus.ESCALATED}),
    RunStatus.INVESTIGATING: frozenset({RunStatus.PLANNING, RunStatus.ESCALATED}),
    RunStatus.PLANNING: frozenset(
        {RunStatus.ACTION_PENDING, RunStatus.ESCALATED}),
    RunStatus.ACTION_PENDING: frozenset(
        {RunStatus.ACTING, RunStatus.ESCALATED}),
    RunStatus.ACTING: frozenset(
        {RunStatus.VERIFYING, RunStatus.RECOVERING, RunStatus.ESCALATED}),
    RunStatus.VERIFYING: frozenset(
        {RunStatus.VERIFIED, RunStatus.RECOVERING, RunStatus.PLANNING,
         RunStatus.FAILED, RunStatus.ESCALATED}),
    RunStatus.RECOVERING: frozenset(
        {RunStatus.ACTING, RunStatus.VERIFYING, RunStatus.ESCALATED,
         RunStatus.FAILED}),
    RunStatus.VERIFIED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.ESCALATED: frozenset(),
}


class StepType(StrEnum):
    HANDOFF = "HANDOFF"
    STATUS = "STATUS"
    DECISION = "DECISION"
    TOOL = "TOOL"
    ACTION = "ACTION"
    POLICY = "POLICY"
    VERIFICATION = "VERIFICATION"
    RECOVERY = "RECOVERY"
    ERROR = "ERROR"


class AgentRole(StrEnum):
    WATCHER = "watcher"
    COORDINATOR = "coordinator"
    MAINTENANCE = "maintenance"
    PRODUCTION = "production"       # N4: production/loss optimisation
    FINANCE = "finance"             # N4: factory finance (runtime product agent)


class ActionKind(StrEnum):
    """The only actions an agent may ever take unilaterally (safe + reversible)."""

    CREATE_URGENT_WORK_ORDER = "CREATE_URGENT_WORK_ORDER"
    PLACE_IN_MAINTENANCE = "PLACE_IN_MAINTENANCE"
    REROUTE_PRODUCTION_JOB = "REROUTE_PRODUCTION_JOB"   # N4: containment recovery


AUTONOMOUS_ACTION_KINDS = frozenset(ActionKind)

# Each policy action maps to exactly one policy-gated tool.
ACTION_TOOL_NAMES: dict[ActionKind, str] = {
    ActionKind.CREATE_URGENT_WORK_ORDER: "create_maintenance_work_order",
    ActionKind.PLACE_IN_MAINTENANCE: "place_machine_in_maintenance",
    ActionKind.REROUTE_PRODUCTION_JOB: "reroute_production_job",
}

# Deterministic execution order: the repair must be on the board *before* the
# machine is taken out of service, so containment never strands an open fault.
ACTION_ORDER: dict[ActionKind, int] = {
    ActionKind.CREATE_URGENT_WORK_ORDER: 0,
    ActionKind.PLACE_IN_MAINTENANCE: 1,
    # N4: reroute runs in the optimisation phase, after maintenance VERIFIES —
    # never in the containment batch.
    ActionKind.REROUTE_PRODUCTION_JOB: 9,
}


# ── structured model output ────────────────────────────────────────────────
class SpecialistAssignment(BaseModel):
    """Coordinator decision #1 — who investigates, and with what goal."""

    specialist: Literal["maintenance"]
    goal: str = Field(min_length=8, max_length=400)
    rationale: str = Field(min_length=8, max_length=900)


class ToolCall(BaseModel):
    """A single tool request emitted by an agent."""

    name: str = Field(min_length=3, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)


class InvestigationPlan(BaseModel):
    """Maintenance decision #1 — which tools to run (never a full DB dump)."""

    tool_calls: list[ToolCall] = Field(min_length=1, max_length=12)
    rationale: str = Field(min_length=8, max_length=900)


class WorkOrderDraft(BaseModel):
    issue: str = Field(min_length=4, max_length=300)
    proposed_action: str = Field(min_length=4, max_length=400)
    priority: Literal["low", "medium", "high", "critical"] = "critical"
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, le=100_000.0)


class MaintenanceAssessment(BaseModel):
    """Maintenance decision #2 — an evidence-backed recommendation."""

    probable_issue: str = Field(min_length=4, max_length=300)
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence: list[str] = Field(min_length=1, max_length=20)
    risk_of_continued_operation: Literal["low", "medium", "high"]
    recommended_actions: list[ActionKind] = Field(min_length=1, max_length=4)
    required_part_id: str | None = None
    work_order: WorkOrderDraft | None = None
    summary: str = Field(min_length=8, max_length=900)


class MalformedOutputError(RuntimeError):
    """The model produced output that failed JSON/Pydantic validation twice."""


# ── tool plumbing ──────────────────────────────────────────────────────────
class ToolResult(BaseModel):
    """Explicit success/failure envelope — errors are data, never exceptions."""

    name: str
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, str] | None = None


class ToolExecutionError(RuntimeError):
    """Raised by a tool handler; converted into a failed ToolResult."""

    def __init__(self, message: str, *, code: str = "TOOL_ERROR") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ── N4: production / finance / optimisation contracts ──────────────────

class ProductionAssessment(BaseModel):
    """Production/Loss agent output after evaluating the paused job."""

    paused_job_id: str
    remaining_quantity: int = Field(ge=0)
    candidates: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    recommended_candidate: str | None = None
    est_run_hours_on_recommended: float | None = None
    est_incremental_cost_usd: float | None = Field(default=None, ge=0)
    expected_delay_hours: float | None = Field(default=None, ge=0)
    operational_loss_if_idle_usd: float = Field(ge=0)
    loss_avoided_usd: float | None = Field(default=None, ge=0)
    confidence: Literal["low", "medium", "high"]
    summary: str = Field(min_length=8, max_length=900)


class FinanceAssessment(BaseModel):
    """Factory Finance agent output after pricing the alternatives."""

    baseline_do_nothing_cost_usd: float = Field(ge=0)
    candidate_action_cost_usd: float = Field(ge=0)
    estimated_loss_avoided_usd: float = Field(ge=0)
    net_benefit_usd: float
    recommendation: Literal["REROUTE", "WAIT"]
    rationale: str = Field(min_length=8, max_length=900)


class OptimisationDecision(BaseModel):
    """Coordinator's reconciled cross-agent decision (N4)."""

    action: Literal["REROUTE_PRODUCTION_JOB", "WAIT_FOR_REPAIR"]
    target_machine: str | None = None
    job_id: str
    reason_summary: str = Field(min_length=8, max_length=900)
    production_supported: bool
    finance_supported: bool
    approval_required: bool = False


# ── policy + verification ──────────────────────────────────────────────────
class ActionPolicyDecision(BaseModel):
    allowed: bool
    actions: list[ActionKind] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class VerificationResult(BaseModel):
    passed: bool
    checks: list[CheckResult]

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)


# ── watcher handoff ────────────────────────────────────────────────────────
class WatcherEscalation(BaseModel):
    """Structured handoff: 'something important happened' — no LLM involved."""

    machine_id: str
    incident_id: str
    severity: str
    incident_type: str
    summary: str
    reason: str
    recent_telemetry: list[dict[str, Any]] = Field(default_factory=list)
    machine_state: str
