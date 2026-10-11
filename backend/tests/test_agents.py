"""N3 autonomous loop tests: watcher, coordinator, maintenance, policy,
verification, recovery, invalid model output and persistence.

Everything here runs offline on the deterministic model (or a scripted test
double). No test opens a socket: conftest pins OPENROUTER_API_KEY to empty.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.agents import tools as tools_module
from app.agents.coordinator import RunOptions, respond_to_escalation
from app.agents.llm import DeterministicAgentModel, ModelMode, ScriptedAgentModel
from app.agents.models import ActionKind, RunStatus, StepType
from app.agents.policy import evaluate_action_policy
from app.agents.tools import TOOLS, ToolContext, execute_tool
from app.agents.verification import verify_maintenance_containment
from app.agents.watcher import evaluate_world
from app.world import repositories as repo
from app.world.simulation import FactoryWorld, reset_world_singleton

# N3 actions only — REROUTE_PRODUCTION_JOB arrives with N4 and must never
# appear inside a pure maintenance containment run.
N3_ACTION_KINDS = frozenset(
    k for k in ActionKind if k is not ActionKind.REROUTE_PRODUCTION_JOB)

MACHINE = "CNC-03"
INCIDENT = "INC-20261005-001"


@pytest.fixture
def world() -> FactoryWorld:
    reset_world_singleton()
    return FactoryWorld(db_path=":memory:")


@pytest.fixture
def critical_world(world: FactoryWorld) -> FactoryWorld:
    """Seeded world advanced to the CRITICAL incident (+30 sim minutes)."""
    world.reset_world()
    world.advance(30)
    return world


def _escalation(w: FactoryWorld):
    found = evaluate_world(w)
    assert len(found) == 1
    return found[0]


# ── watcher ────────────────────────────────────────────────────────────────
def test_watcher_is_silent_on_a_healthy_world(world: FactoryWorld) -> None:
    world.reset_world()
    assert evaluate_world(world) == []


def test_watcher_ignores_a_warning_only_condition(world: FactoryWorld) -> None:
    """CNC-03 is seeded mid-ramp at WARNING with no incident: nothing to do."""
    world.reset_world()
    assert world.get_machine(MACHINE)["state"] == "WARNING"
    assert world.get_active_incidents() == []
    assert evaluate_world(world) == []


def test_watcher_escalates_the_critical_incident(critical_world: FactoryWorld) -> None:
    escalation = _escalation(critical_world)

    assert escalation.machine_id == MACHINE
    assert escalation.incident_id == INCIDENT
    assert escalation.severity == "critical"
    assert escalation.machine_state == "CRITICAL"
    assert len(escalation.recent_telemetry) == 3
    assert MACHINE in escalation.reason


def test_watcher_never_uses_a_model_and_never_repeats(critical_world: FactoryWorld) -> None:
    """A run on the incident makes the watcher quiet again (idempotent)."""
    respond_to_escalation(critical_world, _escalation(critical_world),
                          DeterministicAgentModel(), RunOptions())
    assert evaluate_world(critical_world) == []


# ── coordinator: the flagship containment ──────────────────────────────────
def test_full_run_reaches_verified_and_contains_the_machine(
        critical_world: FactoryWorld) -> None:
    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    DeterministicAgentModel(), RunOptions())

    assert outcome.status == RunStatus.VERIFIED.value
    assert critical_world.get_machine(MACHINE)["state"] == "MAINTENANCE"
    assert critical_world.get_incident(INCIDENT)["status"] == "RESOLVING"

    orders = [order for order in critical_world.get_work_orders(MACHINE)
              if order["source"] == "AGENT"]
    assert len(orders) == 1 and orders[0]["priority"] == "critical"

    actions = critical_world.get_actions(INCIDENT)
    # N4 note: the same run now continues into the optimisation phase, which
    # may add REROUTE_PRODUCTION_JOB to the ledger; containment must always
    # contribute the two N3 actions.
    action_types = {a["action_type"] for a in actions}
    assert {kind.value for kind in N3_ACTION_KINDS} <= action_types
    assert action_types <= {kind.value for kind in ActionKind}
    assert all(a["verification_state"] == "PASSED" for a in actions)
    assert all(a["executed_at"] for a in actions)


def test_run_steps_tell_the_story_in_order(critical_world: FactoryWorld) -> None:
    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    DeterministicAgentModel(), RunOptions())
    steps = outcome.steps

    assert [s["sequence"] for s in steps] == list(range(1, len(steps) + 1))
    types = [s["type"] for s in steps]
    assert types[0] == StepType.HANDOFF.value
    assert StepType.TOOL.value in types
    assert StepType.POLICY.value in types
    assert StepType.VERIFICATION.value in types
    assert any(s["status"] == "PASS" and s["type"] == StepType.VERIFICATION.value
               for s in steps)
    assert any("→ VERIFIED" in s["summary"] for s in steps)

    agents = {s["agent"] for s in steps}
    assert {"watcher", "coordinator", "maintenance"} <= agents
    # No hidden reasoning is ever stored - only actions, evidence and outcomes.
    assert all("chain of thought" not in s["summary"].lower() for s in steps)


def test_run_is_persisted_and_reloadable(critical_world: FactoryWorld) -> None:
    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    DeterministicAgentModel(), RunOptions())

    run = critical_world.get_agent_run(outcome.run_id)
    assert run is not None
    assert run["status"] == RunStatus.VERIFIED.value
    assert run["model_provider"] == "deterministic"
    assert run["completed_at"] is not None
    assert critical_world.get_agent_steps(outcome.run_id) == outcome.steps


def test_reset_world_clears_agent_runs(critical_world: FactoryWorld) -> None:
    respond_to_escalation(critical_world, _escalation(critical_world),
                          DeterministicAgentModel(), RunOptions())
    critical_world.reset_world()
    assert critical_world.get_agent_runs() == []


def test_containment_survives_later_advances(critical_world: FactoryWorld) -> None:
    """A contained machine must not be flipped back to CRITICAL by the sim."""
    respond_to_escalation(critical_world, _escalation(critical_world),
                          DeterministicAgentModel(), RunOptions())
    critical_world.advance(60)
    assert critical_world.get_machine(MACHINE)["state"] == "MAINTENANCE"
    assert len(critical_world.get_agent_runs()) == 1


# ── maintenance agent ──────────────────────────────────────────────────────
def test_maintenance_agent_investigates_with_tools_and_cites_evidence(
        critical_world: FactoryWorld) -> None:
    from app.agents.maintenance import investigate

    seen: list[tuple[str, dict[str, Any]]] = []
    ctx = ToolContext(world=critical_world)
    plan, results, assessment = investigate(
        critical_world, ctx, DeterministicAgentModel(), _escalation(critical_world),
        on_event=lambda kind, payload: seen.append((kind, payload)))

    assert all(TOOLS[call.name].kind == "read" for call in plan.tool_calls)
    assert {"get_recent_telemetry", "get_maintenance_history"} <= set(results)
    assert assessment.risk_of_continued_operation == "high"
    assert any("mm/s" in item for item in assessment.evidence)
    assert assessment.required_part_id is not None
    assert assessment.work_order is not None
    # the part named in the assessment really is the one history points at
    assert assessment.required_part_id in json.dumps(assessment.evidence)


def test_tools_never_touch_sql_and_report_errors_as_data(
        critical_world: FactoryWorld) -> None:
    ctx = ToolContext(world=critical_world)

    unknown = execute_tool(ctx, "drop_everything", {})
    assert unknown.ok is False and unknown.error["code"] == "UNKNOWN_TOOL"

    bad_args = execute_tool(ctx, "get_machine", {"machine_id": "nope-9999"})
    assert bad_args.ok is False and bad_args.error["code"] == "NOT_FOUND"

    missing = execute_tool(ctx, "get_spare_part", {"part_id": "NOPE-1"})
    assert missing.ok is False and missing.error["code"] == "NOT_FOUND"

    ok = execute_tool(ctx, "get_machine", {"machine_id": MACHINE})
    assert ok.ok is True and ok.output["machine"]["machine_id"] == MACHINE


def test_action_tools_refuse_to_run_outside_a_run(critical_world: FactoryWorld) -> None:
    ctx = ToolContext(world=critical_world)     # no run_id
    result = execute_tool(ctx, "place_machine_in_maintenance",
                          {"machine_id": MACHINE, "reason": "test"})
    assert result.ok is False and result.error["code"] == "NO_RUN_CONTEXT"


# ── action policy ──────────────────────────────────────────────────────────
def _assessment(**overrides):
    from app.agents.models import MaintenanceAssessment

    payload = {
        "probable_issue": "Spindle bearing degradation",
        "confidence": "high",
        "evidence": ["vibration 2.0 -> 5.5 mm/s"],
        "risk_of_continued_operation": "high",
        "recommended_actions": ["CREATE_URGENT_WORK_ORDER", "PLACE_IN_MAINTENANCE"],
        "required_part_id": "BRG-AX-17",
        "work_order": {"issue": "bearing", "proposed_action": "replace"},
        "summary": "contain now",
    }
    payload.update(overrides)
    return MaintenanceAssessment.model_validate(payload)


def test_policy_allows_the_canonical_containment(critical_world: FactoryWorld) -> None:
    decision = evaluate_action_policy(
        critical_world,
        incident=critical_world.get_incident(INCIDENT),
        machine=critical_world.get_machine(MACHINE),
        assessment=_assessment())

    assert decision.allowed is True
    assert decision.blocked_reason is None
    assert len(decision.reasons) >= 4


def test_policy_blocks_when_the_required_part_is_out_of_stock(
        critical_world: FactoryWorld) -> None:
    repo.adjust_stock(critical_world.conn, "BRG-AX-17", -2)

    decision = evaluate_action_policy(
        critical_world,
        incident=critical_world.get_incident(INCIDENT),
        machine=critical_world.get_machine(MACHINE),
        assessment=_assessment())

    assert decision.allowed is False
    assert "out of stock" in decision.blocked_reason


def test_policy_blocks_when_the_incident_is_not_critical(
        critical_world: FactoryWorld) -> None:
    incident = dict(critical_world.get_incident(INCIDENT), severity="high")

    decision = evaluate_action_policy(
        critical_world, incident=incident,
        machine=critical_world.get_machine(MACHINE), assessment=_assessment())

    assert decision.allowed is False
    assert "not critical" in decision.blocked_reason


def test_policy_blocks_when_a_technician_is_already_working(
        critical_world: FactoryWorld) -> None:
    repo.insert_work_order(critical_world.conn, {
        "work_order_id": "WO-9001", "machine_id": MACHINE,
        "issue": "bearing", "proposed_action": "replace", "status": "IN_PROGRESS",
        "priority": "high", "scheduled_for": None, "estimated_cost_usd": 100.0,
        "source": "OPERATOR", "created_at": critical_world.clock().iso()})

    decision = evaluate_action_policy(
        critical_world,
        incident=critical_world.get_incident(INCIDENT),
        machine=critical_world.get_machine(MACHINE),
        assessment=_assessment())

    assert decision.allowed is False
    assert "in progress" in decision.blocked_reason


def test_denied_policy_escalates_instead_of_acting(critical_world: FactoryWorld) -> None:
    repo.adjust_stock(critical_world.conn, "BRG-AX-17", -2)

    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    DeterministicAgentModel(), RunOptions())

    assert outcome.status == RunStatus.ESCALATED.value
    assert "action policy denied" in outcome.outcome
    assert critical_world.get_machine(MACHINE)["state"] == "CRITICAL"
    assert critical_world.get_actions(INCIDENT) == []


# ── verification ───────────────────────────────────────────────────────────
def test_verification_reports_every_check(critical_world: FactoryWorld) -> None:
    result = verify_maintenance_containment(critical_world, machine_id=MACHINE,
                                            incident_id=INCIDENT)

    assert result.passed is False
    assert [check.name for check in result.checks] == [
        "machine_is_maintenance", "work_order_created", "action_recorded",
        "active_job_paused", "incident_contained"]
    assert result.passed_count == 0


def test_verification_passes_only_after_real_state_changes(
        critical_world: FactoryWorld) -> None:
    respond_to_escalation(critical_world, _escalation(critical_world),
                          DeterministicAgentModel(), RunOptions())

    result = verify_maintenance_containment(critical_world, machine_id=MACHINE,
                                            incident_id=INCIDENT)
    assert result.passed is True and result.passed_count == 5


def test_verification_fails_when_the_work_order_is_missing(
        critical_world: FactoryWorld) -> None:
    """Simulate a tool that claims success without persisting anything."""
    real_insert = repo.insert_work_order

    def _no_op(*args, **kwargs):   # pragma: no cover - never called successfully
        return None

    repo.insert_work_order = _no_op          # type: ignore[assignment]
    try:
        outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                        DeterministicAgentModel(), RunOptions())
    finally:
        repo.insert_work_order = real_insert  # type: ignore[assignment]

    assert outcome.status == RunStatus.FAILED.value
    assert "verification failed" in outcome.outcome


# ── failure injection + recovery ───────────────────────────────────────────
def test_first_work_order_failure_is_recovered(critical_world: FactoryWorld) -> None:
    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    DeterministicAgentModel(),
                                    RunOptions(fail_first_work_order=True))

    assert outcome.status == RunStatus.VERIFIED.value
    summaries = [s["summary"] for s in outcome.steps]

    failed = next(i for i, s in enumerate(summaries)
                  if s.startswith("CREATE_URGENT_WORK_ORDER FAILED"))
    recovering = next(i for i, s in enumerate(summaries)
                      if "ACTING → RECOVERING" in s)
    retried = next(i for i, s in enumerate(summaries)
                   if s == "CREATE_URGENT_WORK_ORDER → ok")
    assert failed < recovering < retried

    orders = [o for o in critical_world.get_work_orders(MACHINE)
              if o["source"] == "AGENT"]
    assert len(orders) == 1           # the retry created exactly one order


def test_unrecoverable_tool_failure_escalates(critical_world: FactoryWorld) -> None:
    """If the tool keeps failing, the run must end ESCALATED, never silently."""
    real_execute = tools_module.execute_tool

    def _always_fails(ctx, name, args):
        if name == "create_maintenance_work_order":
            return real_execute(ctx, name, {})   # returns INVALID_ARGUMENTS
        return real_execute(ctx, name, args)

    tools_module.execute_tool = _always_fails     # type: ignore[assignment]
    try:
        outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                        DeterministicAgentModel(), RunOptions())
    finally:
        tools_module.execute_tool = real_execute  # type: ignore[assignment]

    assert outcome.status == RunStatus.ESCALATED.value
    assert critical_world.get_machine(MACHINE)["state"] == "CRITICAL"


# ── malformed model output ─────────────────────────────────────────────────
def _assignment() -> str:
    return json.dumps({"specialist": "maintenance",
                       "goal": "Contain CNC-03 bearing degradation",
                       "rationale": "critical machine condition needs containment"})


def _plan() -> str:
    return json.dumps({
        "rationale": "gather condition evidence",
        "tool_calls": [{"name": "get_machine", "args": {"machine_id": MACHINE}}]})


def _assessment_json() -> str:
    return json.dumps({
        "probable_issue": "Spindle bearing degradation", "confidence": "high",
        "evidence": ["vibration 5.5 mm/s", "2 prior BRG-AX-17 replacements"],
        "risk_of_continued_operation": "high",
        "recommended_actions": ["CREATE_URGENT_WORK_ORDER", "PLACE_IN_MAINTENANCE"],
        "required_part_id": "BRG-AX-17",
        "work_order": {"issue": "bearing degradation", "proposed_action": "replace bearing"},
        "summary": "contain CNC-03 now"})


def test_repeatedly_malformed_output_escalates(critical_world: FactoryWorld) -> None:
    model = ScriptedAgentModel(["i am not json", "{still broken"])

    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    model, RunOptions())

    assert outcome.status == RunStatus.ESCALATED.value
    assert "failed" in outcome.outcome.lower()
    repairs = [s for s in outcome.steps if s["status"] == "REPAIR"]
    assert len(repairs) == 1            # exactly one repair attempt was made
    assert critical_world.get_machine(MACHINE)["state"] == "CRITICAL"


def test_one_repair_attempt_is_enough(critical_world: FactoryWorld) -> None:
    model = ScriptedAgentModel(["not json", _assignment(), _plan(),
                                _assessment_json()])

    outcome = respond_to_escalation(critical_world, _escalation(critical_world),
                                    model, RunOptions())

    assert outcome.status == RunStatus.VERIFIED.value
    assert model.calls[0] == model.calls[1]   # same task retried once


# ── model labelling ────────────────────────────────────────────────────────
def test_offline_model_is_labelled_as_not_a_live_llm() -> None:
    assert DeterministicAgentModel().info.mode is ModelMode.DETERMINISTIC
    assert "DETERMINISTIC" in DeterministicAgentModel().info.mode.value
