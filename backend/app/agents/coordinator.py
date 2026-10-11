"""Coordinator — the owner of one autonomous incident-response run.

The workflow lives in code, not in a prompt: the coordinator holds the run
state, enforces the transition table in `models.py`, asks the model for exactly
two kinds of decision (who investigates; and it never lets the model act on its
own), applies the deterministic action policy, executes the approved tools and
then hands the result to the separate verification stage.

Budget: 1 model call to assign a specialist + 2 inside the maintenance agent =
3 calls per incident (plus at most one repair retry per decision).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import Settings, get_settings
from ..observability import get_observability
from ..world import repositories as repo
from ..world.simulation import FactoryWorld
from .llm import (
    TASK_COORDINATOR_ASSIGNMENT,
    AgentModel,
    MalformedOutputError,
    ModelInfo,
    complete_structured,
)
from .maintenance import investigate
from .models import (
    ACTION_ORDER,
    ACTION_TOOL_NAMES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    ActionKind,
    AgentRole,
    MaintenanceAssessment,
    RunStatus,
    SpecialistAssignment,
    StepType,
    ToolResult,
    VerificationResult,
    WatcherEscalation,
)
from .policy import evaluate_action_policy
from .tools import FailureInjector, ToolContext
from .verification import verify_maintenance_containment
from .watcher import evaluate_world as watcher_evaluate


def _dump_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


COORDINATOR_SYSTEM = (
    "You are Factora's incident coordinator on a factory floor. You decide which "
    "specialist owns an incident and state the goal precisely. You never act on "
    "the factory yourself. Reply with a single JSON object only."
)


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


@dataclass
class RunOptions:
    """Per-run knobs. The failure injection is demo-only and never random."""

    fail_first_work_order: bool = False


@dataclass
class RunOutcome:
    run_id: str
    status: str
    outcome: str
    steps: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "status": self.status,
                "outcome": self.outcome, "steps": self.steps}


# ── persistence + state machine ────────────────────────────────────────────
class RunRecorder:
    """Writes agent_runs/agent_steps and refuses illegal transitions."""

    def __init__(self, world: FactoryWorld, model_info: ModelInfo,
                 options: RunOptions) -> None:
        self.world = world
        self.model_info = model_info
        self.options = options
        self._sequence = 0

    def start(self, escalation: WatcherEscalation) -> str:
        run_id = self.world.next_id("agent_runs", "run_id",
                                    f"RUN-{self.world.clock().now:%Y%m%d}")
        repo.insert_agent_run(self.world.conn, {
            "run_id": run_id,
            "incident_id": escalation.incident_id,
            "machine_id": escalation.machine_id,
            "goal": f"Resolve/contain {escalation.incident_type} incident "
                    f"{escalation.incident_id} on {escalation.machine_id}",
            "status": RunStatus.DETECTED.value,
            "active_agent": AgentRole.WATCHER.value,
            "model_provider": self.model_info.provider,
            "model_name": self.model_info.name,
            "outcome": None,
            "started_at": self.world.clock().iso(),
            "completed_at": None,
            "fail_first_work_order": int(self.options.fail_first_work_order),
        })
        return run_id

    def step(self, run_id: str, *, agent: AgentRole, type: StepType,
             summary: str, tool_name: str | None = None,
             input: dict | None = None, output: Any = None,
             status: str = "OK") -> None:
        self._sequence += 1
        repo.insert_agent_step(self.world.conn, {
            "run_id": run_id,
            "sequence": self._sequence,
            "agent": agent.value,
            "type": type.value,
            "summary": summary,
            "tool_name": tool_name,
            "input": _dump_json(input) if input else None,
            "output": (_dump_json(output) if output is not None else None),
            "status": status,
            "timestamp": self.world.clock().iso(),
        })

    def transition(self, run_id: str, current: RunStatus, new: RunStatus,
                   *, agent: AgentRole, summary: str) -> RunStatus:
        if new not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"illegal run transition {current.value} -> {new.value}")
        repo.update_agent_run(self.world.conn, run_id,
                              {"status": new.value, "active_agent": agent.value})
        self.step(run_id, agent=agent, type=StepType.STATUS,
                  summary=f"{current.value} → {new.value}: {summary}")
        return new

    def finish(self, run_id: str, status: RunStatus, outcome: str) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"{status.value} is not a terminal status")
        repo.update_agent_run(self.world.conn, run_id, {
            "status": status.value, "outcome": outcome,
            "completed_at": self.world.clock().iso()})


def _step_bridge(recorder: RunRecorder, run_id: str,
                 agent: AgentRole) -> Callable[[str, dict[str, Any]], None]:
    """Turn agent/model callbacks into persisted, human-readable steps."""

    def on_event(kind: str, payload: dict[str, Any]) -> None:
        if kind == "tool":
            ok = bool(payload.get("ok"))
            name = payload.get("name", "?")
            if ok:
                summary = f"tool {name} → ok"
                output = payload.get("output")
            else:
                summary = f"tool {name} FAILED: {payload.get('error')}"
                output = payload.get("error")
            recorder.step(run_id, agent=agent, type=StepType.TOOL, summary=summary,
                          tool_name=name, input=payload.get("args"), output=output,
                          status="OK" if ok else "FAILED")
        elif kind == "output_repair":
            recorder.step(
                run_id, agent=agent, type=StepType.ERROR,
                summary=(f"model output for '{payload.get('task')}' failed "
                         f"validation ({payload.get('reason')}); retrying once"),
                status="REPAIR")

    return on_event


# ── the workflow ───────────────────────────────────────────────────────────
@_lazy_span(kind="WORKFLOW", name="factora.incident_response")
def evaluate_and_respond(world: FactoryWorld, model: AgentModel,
                         settings: Settings | None = None) -> list[RunOutcome]:
    """Watcher first; only escalations start a run. No key, no call, no run."""
    settings = settings or get_settings()
    outcomes: list[RunOutcome] = []
    for escalation in watcher_evaluate(world):
        outcomes.append(respond_to_escalation(
            world, escalation, model,
            options=RunOptions(
                fail_first_work_order=settings.demo_fail_first_work_order)))
    return outcomes


@_lazy_span(kind="AGENT", name="coordinator", role="workflow owner")
def respond_to_escalation(world: FactoryWorld, escalation: WatcherEscalation,
                          model: AgentModel,
                          options: RunOptions | None = None) -> RunOutcome:
    """Run one incident from DETECTED to a terminal status. Never raises."""
    options = options or RunOptions()
    recorder = RunRecorder(world, model.info, options)
    run_id = recorder.start(escalation)
    recorder.step(run_id, agent=AgentRole.WATCHER, type=StepType.HANDOFF,
                  summary=f"Escalated: {escalation.reason}",
                  output={"incident_id": escalation.incident_id,
                          "machine_id": escalation.machine_id,
                          "severity": escalation.severity,
                          "telemetry_points": len(escalation.recent_telemetry)})

    status = RunStatus.DETECTED
    ctx = ToolContext(world=world, run_id=run_id,
                      incident_id=escalation.incident_id,
                      fail_injector=FailureInjector(
                          fail_first_work_order=options.fail_first_work_order))
    on_event = _step_bridge(recorder, run_id, AgentRole.MAINTENANCE)

    try:
        assignment = _assign_specialist(model, escalation, on_event)
    except MalformedOutputError as exc:
        return _escalate(world, recorder, run_id, status,
                         f"coordinator could not produce a valid assignment: {exc}")

    status = recorder.transition(
        run_id, status, RunStatus.INVESTIGATING, agent=AgentRole.COORDINATOR,
        summary=f"Assigned {assignment.specialist} agent: {assignment.goal}")
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.DECISION,
                  summary=f"Goal for {assignment.specialist}: {assignment.goal}",
                  output=assignment.model_dump())

    try:
        plan, results, assessment = investigate(
            world, ctx, model, escalation, on_event=on_event)
    except MalformedOutputError as exc:
        return _escalate(world, recorder, run_id, status,
                         f"maintenance agent produced invalid output: {exc}")

    status = recorder.transition(
        run_id, status, RunStatus.PLANNING, agent=AgentRole.COORDINATOR,
        summary="Inspected the maintenance assessment")
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.DECISION,
                  summary=f"Assessment: {assessment.probable_issue} "
                          f"({assessment.confidence} confidence) — {assessment.summary}",
                  output={"assessment": assessment.model_dump(),
                          "tools_used": list(results)})

    incident = world.get_incident(escalation.incident_id)
    machine = world.get_machine(escalation.machine_id)
    if incident is None or machine is None:
        return _escalate(world, recorder, run_id, status,
                         "incident or machine disappeared before the policy check")

    decision = _lazy_policy(world, incident, machine, assessment)
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.POLICY,
                  summary=("Action policy ALLOWED: " + "; ".join(decision.reasons))
                  if decision.allowed else
                  ("Action policy BLOCKED: " + (decision.blocked_reason or "")),
                  output=decision.model_dump(),
                  status="ALLOWED" if decision.allowed else "BLOCKED")
    if not decision.allowed or not decision.actions:
        return _escalate(world, recorder, run_id, status,
                         "action policy denied autonomous action: "
                         + (decision.blocked_reason or "no permitted actions"))

    status = recorder.transition(
        run_id, status, RunStatus.ACTION_PENDING, agent=AgentRole.COORDINATOR,
        summary="Policy approved the containment plan")

    # The model advises; the coordinator plans. Containment means the machine
    # stops *and* a repair is on the board, so an order is added when the
    # specialist only asked for the machine to be taken out of service.
    actions = sorted(decision.actions, key=lambda kind: ACTION_ORDER[kind])
    if (ActionKind.PLACE_IN_MAINTENANCE in actions
            and ActionKind.CREATE_URGENT_WORK_ORDER not in actions):
        actions.append(ActionKind.CREATE_URGENT_WORK_ORDER)
        recorder.step(
            run_id, agent=AgentRole.COORDINATOR, type=StepType.DECISION,
            summary="Added CREATE_URGENT_WORK_ORDER to the containment plan: "
                    "stopping CNC-class machines without a scheduled repair "
                    "leaves the fault unowned",
            output={"assessment_actions": [a.value for a in decision.actions],
                    "plan_actions": [a.value for a in actions]})

    # ── act, with one deterministic retry on tool failure ────────────────
    status = recorder.transition(
        run_id, status, RunStatus.ACTING, agent=AgentRole.COORDINATOR,
        summary="Executing the approved containment actions")
    todo = list(actions)
    ok, failure, _executed = _execute_actions(ctx, recorder, run_id, todo,
                                              assessment, escalation)
    if not ok:
        todo = todo[len(_executed):]          # never re-run what already succeeded
        status = recorder.transition(
            run_id, status, RunStatus.RECOVERING, agent=AgentRole.COORDINATOR,
            summary=f"Tool failed ({failure}); retrying the remaining actions once")
        ok, failure, _ = _execute_actions(ctx, recorder, run_id, todo,
                                          assessment, escalation)
    if not ok:
        return _escalate(world, recorder, run_id, status,
                         "containment action failed after one retry: "
                         + (failure or "unknown tool failure"),
                         transition_from=RunStatus.RECOVERING)

    _contain_incident(world, recorder, run_id, escalation, assessment)

    # ── verify against stored world state ────────────────────────────────
    status = recorder.transition(
        run_id, status, RunStatus.VERIFYING, agent=AgentRole.COORDINATOR,
        summary="Verifying the containment against persisted world state")
    result = _lazy_verify(world, escalation.machine_id, escalation.incident_id)
    recorder.step(run_id, agent=AgentRole.COORDINATOR,
                  type=StepType.VERIFICATION,
                  summary=f"{result.passed_count}/{len(result.checks)} checks passed"
                          + (" — VERIFIED" if result.passed else " — VERIFY FAILED"),
                  output={"checks": [check.model_dump() for check in result.checks],
                          "passed": result.passed},
                  status="PASS" if result.passed else "FAIL")

    if not result.passed:
        status = recorder.transition(
            run_id, status, RunStatus.RECOVERING, agent=AgentRole.COORDINATOR,
            summary="Verification failed; remediating the specific failed check once")
        if _remediate(ctx, recorder, run_id, result, actions, assessment,
                      escalation):
            result = _lazy_verify(world, escalation.machine_id,
                                  escalation.incident_id)
            recorder.step(run_id, agent=AgentRole.COORDINATOR,
                          type=StepType.VERIFICATION,
                          summary=f"re-check {result.passed_count}/"
                                  f"{len(result.checks)} passed"
                                  + (" — VERIFIED" if result.passed else " — FAILED"),
                          output={"checks": [c.model_dump() for c in result.checks],
                                  "passed": result.passed},
                          status="PASS" if result.passed else "FAIL")
        if not result.passed:
            return _escalate(world, recorder, run_id, status,
                             "verification failed after recovery",
                             transition_from=RunStatus.RECOVERING,
                             final=RunStatus.FAILED)

    _mark_actions_verified(world, escalation.incident_id, result.passed)
    final = recorder.transition(
        run_id, status, RunStatus.VERIFIED, agent=AgentRole.COORDINATOR,
        summary=f"Run complete: {result.passed_count}/{len(result.checks)} checks passed")
    outcome = (f"{escalation.machine_id} contained for {escalation.incident_id}. "
               f"{assessment.probable_issue}. Actions: "
               + ", ".join(kind.value for kind in actions)
               + f". Model: {model.info.provider}/{model.info.name} "
                 f"({model.info.mode.value}).")
    recorder.finish(run_id, final, outcome)
    return RunOutcome(run_id=run_id, status=final.value, outcome=outcome,
                      steps=repo.list_agent_steps(world.conn, run_id))


def _assign_specialist(model: AgentModel, escalation: WatcherEscalation,
                       on_event) -> SpecialistAssignment:
    hints = {
        "incident": escalation.model_dump(
            include={"incident_id", "incident_type", "severity", "summary"}),
        "machine": {"machine_id": escalation.machine_id,
                    "state": escalation.machine_state},
    }
    user = (f"Incident {escalation.incident_id}: {escalation.summary}\n"
            f"Machine {escalation.machine_id} is {escalation.machine_state}.\n"
            f"Escalation reason: {escalation.reason}\n"
            f"Choose the specialist and state a precise, testable goal.")
    return complete_structured(
        model, SpecialistAssignment, system=COORDINATOR_SYSTEM, user=user,
        task=TASK_COORDINATOR_ASSIGNMENT, hints=hints, on_event=on_event)


def _lazy_policy(world, incident, machine, assessment):
    return evaluate_action_policy(world, incident=incident, machine=machine,
                                  assessment=assessment)


def _lazy_verify(world, machine_id, incident_id):
    return verify_maintenance_containment(world, machine_id=machine_id,
                                          incident_id=incident_id)


def _action_args(kind: ActionKind, assessment: MaintenanceAssessment,
                 escalation: WatcherEscalation) -> dict[str, Any]:
    if kind is ActionKind.CREATE_URGENT_WORK_ORDER:
        draft = assessment.work_order
        if draft is not None:
            return {"machine_id": escalation.machine_id, **draft.model_dump()}
        # Documented fallback: the model named the action but omitted the
        # draft, so build the order from its own assessment wording rather
        # than inventing evidence. Cost stays 0 until a human prices it.
        return {
            "machine_id": escalation.machine_id,
            "issue": f"{assessment.probable_issue} (autonomous containment)",
            "proposed_action": assessment.summary[:300],
            "priority": "critical",
            "estimated_cost_usd": 0.0,
        }
    return {"machine_id": escalation.machine_id,
            "reason": (f"Autonomous containment of {escalation.incident_id}: "
                       f"{assessment.probable_issue}")[:300]}


def _execute_actions(ctx: ToolContext, recorder: RunRecorder, run_id: str,
                     actions: list[ActionKind], assessment: MaintenanceAssessment,
                     escalation: WatcherEscalation) -> tuple[bool, str | None, list[ActionKind]]:
    """Run each approved action once; return (all_ok, failure, executed).

    A retry re-enters with the *remaining* actions only, so a failure on the
    second action never re-runs (and duplicates) the first.
    """
    from .tools import execute_tool

    executed: list[ActionKind] = []
    for kind in actions:
        try:
            args = _action_args(kind, assessment, escalation)
        except MalformedOutputError as exc:
            return False, f"{kind.value}: {exc}", executed
        tool_name = ACTION_TOOL_NAMES[kind]
        result: ToolResult = execute_tool(ctx, tool_name, args)
        recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.ACTION,
                      summary=(f"{kind.value} → ok"
                               if result.ok else
                               f"{kind.value} FAILED: {result.error}"),
                      tool_name=tool_name, input=args,
                      output=result.output if result.ok else result.error,
                      status="OK" if result.ok else "FAILED")
        if not result.ok:
            return False, f"{kind.value}: {(result.error or {}).get('message')}", executed
        executed.append(kind)
        _record_ledger(ctx.world, recorder, run_id, escalation, kind, args, result)
    return True, None, executed


def _record_ledger(world: FactoryWorld, recorder: RunRecorder, run_id: str,
                   escalation: WatcherEscalation, kind: ActionKind,
                   args: dict[str, Any], result: ToolResult) -> str:
    """Every executed action lands in the `actions` audit ledger."""
    action_id = world.next_id("actions", "action_id", "ACT")
    payload = {"run_id": run_id, "tool_args": args, **result.output}
    world.record_action({
        "action_id": action_id,
        "incident_id": escalation.incident_id,
        "action_type": kind.value,
        "proposed_by": f"FACTORA_AGENT/{run_id}",
        "payload": json.dumps(payload, sort_keys=True, default=str),
        "risk_level": "low",
        "approval_required": 0,
        "approval_state": "APPROVED",
        "executed_at": world.clock().iso(),
        "verification_state": "PENDING",
        "result": "executed",
    })
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.ACTION,
                  summary=f"ledgered {action_id} for {kind.value}",
                  tool_name=ACTION_TOOL_NAMES[kind],
                  output={"action_id": action_id})
    return action_id


REMEDIATION_BY_CHECK = {
    "machine_is_maintenance": ActionKind.PLACE_IN_MAINTENANCE,
    "work_order_created": ActionKind.CREATE_URGENT_WORK_ORDER,
}


def _remediate(ctx: ToolContext, recorder: RunRecorder, run_id: str,
               result: VerificationResult, actions: list[ActionKind],
               assessment: MaintenanceAssessment,
               escalation: WatcherEscalation) -> bool:
    """Re-run only the action behind each failed check, once."""
    failed = {check.name for check in result.checks if not check.passed}
    todo = [kind for kind in actions
            if kind in {REMEDIATION_BY_CHECK[name] for name in failed
                        if name in REMEDIATION_BY_CHECK}]
    if not todo:
        recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.RECOVERY,
                      summary="No automated remediation available for "
                              + ", ".join(sorted(failed)),
                      status="NONE")
        return False
    ok, failure, _ = _execute_actions(ctx, recorder, run_id, todo, assessment,
                                      escalation)
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.RECOVERY,
                  summary=(f"re-ran {', '.join(kind.value for kind in todo)}"
                           if ok else f"remediation failed: {failure}"),
                  status="OK" if ok else "FAILED")
    return ok


def _contain_incident(world: FactoryWorld, recorder: RunRecorder, run_id: str,
                      escalation: WatcherEscalation,
                      assessment: MaintenanceAssessment,
                      repeat: bool = False) -> None:
    """Move the incident to the contained state (RESOLVING) with agent ownership."""
    world.set_incident_status(
        escalation.incident_id, "RESOLVING",
        current_owner=f"FACTORA_AGENT/{run_id}",
        recommended_action=assessment.summary)
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.ACTION,
                  summary=(f"incident {escalation.incident_id} marked contained "
                           f"(RESOLVING), owner {run_id}"
                           + (" [recovery re-check]" if repeat else "")))


def _mark_actions_verified(world: FactoryWorld, incident_id: str,
                           passed: bool) -> None:
    for action in world.get_actions(incident_id):
        if action.get("executed_at"):
            world.set_action_verification(action["action_id"], "PASSED" if passed else "FAILED")


def _escalate(world: FactoryWorld, recorder: RunRecorder, run_id: str,
              status: RunStatus, reason: str,
              transition_from: RunStatus | None = None,
              final: RunStatus = RunStatus.ESCALATED) -> RunOutcome:
    """End a run that cannot continue autonomously; a human owns it from here."""
    origin = transition_from or status
    if origin in ALLOWED_TRANSITIONS and final in ALLOWED_TRANSITIONS[origin]:
        status = recorder.transition(run_id, origin, final,
                                     agent=AgentRole.COORDINATOR,
                                     summary=f"Escalated to a human operator: {reason}")
    else:  # pragma: no cover - defensive
        repo.update_agent_run(world.conn, run_id, {"status": final.value})
        status = final
    recorder.step(run_id, agent=AgentRole.COORDINATOR, type=StepType.ERROR,
                  summary=reason, status="ESCALATED")
    recorder.finish(run_id, status, reason)
    return RunOutcome(run_id=run_id, status=status.value, outcome=reason,
                      steps=repo.list_agent_steps(world.conn, run_id))
