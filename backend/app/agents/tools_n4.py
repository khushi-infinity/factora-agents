"""N4 typed tools — production recovery + finance evidence.

Extends the N3 tool registry with:

  read tools (used by the Production/Loss and Finance agents):
    * get_paused_jobs                  — jobs awaiting their contained machine
    * get_reroute_candidates           — same-type-compatible alternatives with
                                         economics attached (from FactoryWorld,
                                         which delegates to `economics`)
    * calculate_do_nothing_cost        — deterministic wait-for-repair loss
    * calculate_reroute_cost           — deterministic action cost per candidate

  action tool (policy-gated, executed only by the coordinator):
    * reroute_production_job           — verified PAUSED-source job reassignment,
                                         recorded in the actions ledger

Everything a tool knows it reads from FactoryWorld — no raw SQL, no invented
numbers. Job economics (output/hour etc.) are joined from the machine tables in
`economics`, so the model they hand to the LLM carries real values, not prose.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..world import economics
from .models import ToolExecutionError
from .tools import MachineArgs, Tool, ToolContext  # noqa: F401


# ── argument models ────────────────────────────────────────────────────
class JobArgs(BaseModel):
    job_id: str = Field(min_length=3, max_length=32)


class RerouteCalcArgs(BaseModel):
    """Price one candidate deterministically. `job_id` is optional so the
    finance agent can price *the* paused job without knowing its id; the model
    picks candidate ids, this tool does the math."""

    job_id: str = Field(default="", max_length=32)
    candidate_machine_id: str = Field(default="", max_length=32)
    hours_behind: float = Field(default=0.0, ge=0.0, le=72.0)


# ── job economics: join the machine columns a loss model needs ─────────
def _default_paused_hours(ctx: ToolContext) -> float:
    """Deterministic idle baseline for the paused job.

    The N3 containment happens during the advance that turned CNC-03 CRITICAL
    (epoch +30 min → 06:30); the demo loss model prices **0.5 h of idle** —
    'what has this outage cost so far'. A longer wait scales the same formula.
    Explicit (never wall-clock) so the flagship stays replayable.
    """
    del ctx
    return 0.5


def _job_with_economics(ctx: ToolContext, job: dict) -> dict:
    machine = ctx.world.get_machine(job["machine_id"])
    merged = dict(job)
    merged["output_per_hour_of_source"] = (machine or {}).get("output_per_hour")
    merged["cost_per_hour_usd_of_source"] = (machine or {}).get("cost_per_hour_usd")
    merged["contribution_per_unit_usd"] = (machine or {}).get(
        "contribution_per_unit_usd")
    return merged


# ── read tools (N4) ────────────────────────────────────────────────────
def _get_paused_jobs(ctx: ToolContext, args: MachineArgs) -> dict[str, Any]:
    """Active jobs stuck on one machine (status PAUSED there), with economics."""
    machine_id = args.machine_id if args.machine_id else ctx.incident_machine_id()
    jobs = [job for job in ctx.world.get_active_jobs_all()
            if job["machine_id"] == machine_id]
    paused = [_job_with_economics(ctx, job) for job in jobs
              if job["status"] == "PAUSED"]
    others = [job["job_id"] for job in jobs if job["status"] != "PAUSED"]
    if not paused and not others:
        raise ToolExecutionError(
            f"no active production jobs on '{machine_id}'", code="NOT_FOUND")
    return {"paused_jobs": paused, "other_active_jobs_on_machine": others}


def _get_reroute_candidates(ctx: ToolContext, args: JobArgs) -> dict[str, Any]:
    job = ctx.world.get_job(args.job_id)
    if job is None:
        raise ToolExecutionError(f"unknown job '{args.job_id}'", code="NOT_FOUND")
    candidates = ctx.world.get_compatible_machines(args.job_id)
    return {"job_id": args.job_id, "part_no": job["part_no"],
            "candidates": candidates}


def _calculate_do_nothing_cost(ctx: ToolContext,
                               args: RerouteCalcArgs
                               ) -> dict[str, Any]:
    """Wait-for-repair cost for one job, or for the phase's paused job by default."""
    job_id = args.job_id or ctx.incident_paused_job_id() or ""
    job = ctx.world.get_job(job_id)
    if job is None:
        raise ToolExecutionError(
            f"no paused job to price (job '{args.job_id}')", code="NOT_FOUND")
    merged = _job_with_economics(ctx, job)
    if merged.get("output_per_hour_of_source") is None:
        raise ToolExecutionError(
            "source machine economics unavailable", code="NOT_FOUND")
    # Paused duration: the N3 containment happens during the advance that
    # turned CNC-03 CRITICAL (+30 min). The deterministic demo baseline prices
    # **0.5 h of idle** — 'what has this outage cost so far'. A longer wait
    # scales the same formula.
    paused_hours = _default_paused_hours(ctx)
    return economics.do_nothing_cost(merged, paused_hours)


def _calculate_reroute_cost(ctx: ToolContext, args: RerouteCalcArgs) -> dict[str, Any]:
    """Price one candidate with `hours_behind` defaulting to the candidate's
    own queue absorption time — the model should never have to supply queue
    arithmetic; passing hours_behind=0 means 'no queue' (best case)."""
    job_id = args.job_id or ctx.incident_paused_job_id() or ""
    candidate_id = args.candidate_machine_id
    job = ctx.world.get_job(job_id)
    candidate = ctx.world.get_machine(candidate_id)
    if job is None:
        raise ToolExecutionError(f"unknown job '{job_id}'", code="NOT_FOUND")
    if candidate is None:
        raise ToolExecutionError(
            f"unknown machine '{candidate_id}'", code="NOT_FOUND")
    if args.hours_behind <= 0.0:
        option = next((o for o in ctx.world.get_compatible_machines(job_id)
                       if o["candidate_machine_id"] == candidate_id), None)
        if option and option.get("queue_behind_units"):
            per_hour = candidate.get("output_per_hour") or 0.0
            if per_hour:
                args.hours_behind = round(option["queue_behind_units"] / per_hour, 2)
    merged = _job_with_economics(ctx, job)
    return economics.reroute_cost(merged, candidate, hours_behind=args.hours_behind)


# NOTE: reroute args validation happens against the *source's* compatibility,
# not the type table alone — the tool cross-checks via economics functions so
# the agent cannot reroute onto an incompatible machine by luck of a shared id.


# ── action tool (N4, policy-gated) ─────────────────────────────────────
BLOCKED_FOR_REROUTE = ("CRITICAL", "MAINTENANCE", "OFFLINE")
REROUTE_TARGET_STATES = ("HEALTHY",)


class RerouteJobArgs(BaseModel):
    job_id: str = Field(min_length=3, max_length=32)
    target_machine_id: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=8, max_length=400)


def _reroute_production_job(ctx: ToolContext, args: RerouteJobArgs) -> dict[str, Any]:
    if ctx.run_id is None:
        raise ToolExecutionError("action tools require an agent run",
                                 code="NO_RUN_CONTEXT")

    job = ctx.world.get_job(args.job_id)
    if job is None:
        raise ToolExecutionError(f"unknown job '{args.job_id}'", code="NOT_FOUND")
    if job["status"] != "PAUSED":
        raise ToolExecutionError(
            f"job {args.job_id} is {job['status']}, not PAUSED — only paused "
            "production may be rerouted", code="WRONG_JOB_STATE")

    target = ctx.world.get_machine(args.target_machine_id)
    if target is None:
        raise ToolExecutionError(
            f"unknown machine '{args.target_machine_id}'", code="NOT_FOUND")
    if target["state"] not in REROUTE_TARGET_STATES:
        raise ToolExecutionError(
            f"cannot reroute onto a {target['state']} machine; "
            f"{args.target_machine_id} must be HEALTHY", code="UNHEALTHY_TARGET")

    # part compatibility: same machine type as the job's source (deterministic,
    # driven by the capabilities table via economics.reroute_feasibility).
    compatible = {option["candidate_machine_id"]: option
                  for option in ctx.world.get_compatible_machines(args.job_id)}
    option = compatible.get(args.target_machine_id)
    if option is None:
        raise ToolExecutionError(
            f"{args.target_machine_id} is not a compatible reroute target for "
            f"{args.job_id}", code="INCOMPATIBLE_TARGET")

    if option["candidate_machine_id"] == job["machine_id"]:
        raise ToolExecutionError("reroute to the same machine is a no-op",
                                 code="INVALID_TARGET")

    result = ctx.world.reroute_job(args.job_id, args.target_machine_id)
    out = {
        "job_id": args.job_id,
        "previous": result["previous"],
        "new": result["new"],
        "part_compatible": option["part_compatible"],
        "queue_behind_units": option["queue_behind_units"],
        "est_hours_to_absorb": option["est_hours_to_absorb"],
        "reason": args.reason,
    }
    return out


N4_TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool("get_paused_jobs",
             "The paused production jobs on the contained machine, with job "
             "economics (target/produced/scrap, due date, output per hour).",
             MachineArgs, _get_paused_jobs, "read"),
        Tool("get_reroute_candidates",
             "Compatible alternative machines for one production job, with "
             "state, queue and per-candidate economics — already restricted to "
             "the same machine type.",
             JobArgs, _get_reroute_candidates, "read"),
        Tool("calculate_do_nothing_cost",
             "Deterministic loss model: what waiting for the repair costs "
             "(lost contribution + idle cost). Never ask the model to do this.",
             RerouteCalcArgs, _calculate_do_nothing_cost, "read"),
        Tool("calculate_reroute_cost",
             "Deterministic price of one candidate: run hours, operating cost "
             "and delay cost for the job's remaining units.",
             RerouteCalcArgs, _calculate_reroute_cost, "read"),
        Tool("reroute_production_job",
             "ACTION (policy-gated). Move a PAUSED job to a compatible HEALTHY "
             "machine and re-queue it; reversible via the same tool once the "
             "original machine returns.",
             RerouteJobArgs, _reroute_production_job, "action"),
    )
}
