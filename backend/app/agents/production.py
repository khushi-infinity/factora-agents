"""Production/Loss Agent — the least-disruptive operational response.

N4 specialist #1. It never receives the answer in its prompt: it retrieves the
paused job and the compatible candidates with tools, and builds its assessment
from the deterministic loss/reroute economics computed over that evidence.

Model budget: 1 structured call that *narrates and picks among* deterministic
candidate scores (arithmetic stays in `economics`). When no real model is
configured the offline stand-in performs the same tool flow; the choice is
identical because it comes from the same numbers.
"""

from __future__ import annotations

from ..observability import get_observability
from ..world.simulation import FactoryWorld
from .llm import TASK_PRODUCTION_ASSESSMENT, AgentModel, complete_structured
from .models import ProductionAssessment
from .tools import ToolContext, execute_tool

SYSTEM_PROMPT = (
    "You are Factora's production/loss optimisation specialist. You minimise "
    "disruption to the factory schedule after a machine has been contained. "
    "You receive deterministic candidate scores and interpret them; you never "
    "invent numbers and never ask to delete or reorder production. Reply with "
    "a single JSON object only."
)


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


def _pick_candidate(candidates_scored: list[dict]) -> tuple[dict | None, float]:
    """Deterministic winner: only HEALTHY-compatible candidates, lowest delay
    then lowest incremental cost. Returns (candidate, delay_hours)."""
    eligible = [c for c in candidates_scored
                if c["compatible"] and c["available"]]
    if not eligible:
        return None, 0.0
    eligible.sort(key=lambda c: (c["delay_hours"],
                                 c["incremental_cost_usd"],
                                 c["machine_id"]))
    return eligible[0], eligible[0]["delay_hours"]


def _score_candidates(ctx: ToolContext, job_id: str) -> list[dict]:
    """Run the deterministic scoring for every compatible candidate via tools."""
    candidates = execute_tool(ctx, "get_reroute_candidates",
                              {"job_id": job_id})
    if not candidates.ok:
        return []
    scored: list[dict] = []
    for option in candidates.output.get("candidates", []):
        candidate_id = option["candidate_machine_id"]
        healthy = option["machine_state"] == "HEALTHY"
        # The tool derives queue hours itself (hours_behind=0 lets the tool
        # pick the candidate's actual queue absorption time deterministically).
        pricing = execute_tool(
            ctx, "calculate_reroute_cost",
            {"job_id": job_id, "candidate_machine_id": candidate_id,
             "hours_behind": 0.0})
        incremental = (pricing.output.get("total_usd")
                       if pricing.ok else None)
        queue_hours = float(pricing.output.get("queue_hours") or 0.0) \
            if pricing.ok else 0.0
        scored.append({
            "machine_id": candidate_id,
            "compatible": bool(option.get("part_compatible")),
            "available": healthy,
            "machine_state": option.get("machine_state"),
            "queue_behind_units": option.get("queue_behind_units", 0),
            "queue_hours": round(queue_hours, 2),
            "est_run_hours": pricing.output.get("est_run_hours") if pricing.ok else None,
            "incremental_cost_usd": incremental,
            "delay_hours": round(queue_hours, 2),
        })
    return scored


def _output_per_hour(ctx: ToolContext, machine_id: str) -> float:
    machine = ctx.world.get_machine(machine_id) or {}
    return float(machine.get("output_per_hour") or 0.0)


def _idle_loss(ctx: ToolContext) -> dict | None:
    do_nothing = execute_tool(ctx, "calculate_do_nothing_cost", {})
    return do_nothing.output if do_nothing.ok else None


@_lazy_span(kind="AGENT", name="production_loss", role="specialist")
def assess(
    world: FactoryWorld,
    ctx: ToolContext,
    model: AgentModel,
    *,
    job_id: str,
    on_event=None,
) -> ProductionAssessment:
    """Retrieve the paused job + candidates through tools; return the assessment."""
    paused = execute_tool(ctx, "get_paused_jobs", {"machine_id": ctx.phase_machine_id} if ctx.phase_machine_id else {})
    job = world.get_job(job_id)
    if job is None or not paused.ok:
        raise RuntimeError(
            f"production agent: paused job '{job_id}' not found on the contained "
            "machine (nothing to optimise)")

    remaining = max(0, job["target_qty"] - job["produced_qty"])
    scored = _score_candidates(ctx, job_id)
    idle = _idle_loss(ctx) or {}

    winner, delay = _pick_candidate(scored)
    loss_avoided = None
    if winner and winner["incremental_cost_usd"] is not None and idle:
        loss_avoided = max(
            0.0, float(idle.get("total_usd") or 0.0)
            - float(winner["incremental_cost_usd"]))

    # The tools own the numbers; the model (if any) only shapes the wording and
    # confirms the choice. 1 call, structured, repairable like every other one.
    notes = {
        "job_id": job_id,
        "remaining_qty": remaining,
        "recommended": winner["machine_id"] if winner else None,
        "incremental_cost_usd": (winner or {}).get("incremental_cost_usd"),
        "delay_hours": delay,
        "idle_cost_usd": idle.get("total_usd"),
    }
    user = (
        f"JB {job_id} on the contained machine has {remaining} units still to "
        f"make. Deterministic scoring of compatible candidates:\n"
        + "\n".join(
            f"- {c['machine_id']}: state={c['machine_state']} "
            f"compatible={c['compatible']} queue={c['queue_behind_units']}u "
            f"queue_hours={c['queue_hours']} "
            f"incremental_cost_usd={c['incremental_cost_usd']}"
            for c in scored)
        + f"\nDeterministic pick: {notes['recommended']} "
          f"(cost {notes['incremental_cost_usd']} USD, delay {delay} h). "
          f"Cost of doing nothing for 0.5 h: {notes['idle_cost_usd']} USD.\n"
          "Confirm the recommendation and write the one-paragraph production "
          "summary citing these numbers."
    )
    hints = {"tools": notes, "machine": {"machine_id": ctx.incident_machine_id()},
             "job": {"job_id": job_id}}
    try:
        assessment = complete_structured(
            model, ProductionAssessment, system=SYSTEM_PROMPT, user=user,
            task=TASK_PRODUCTION_ASSESSMENT, hints=hints, on_event=on_event)
        # Deterministic fields must agree with the tool math — the model's
        # story never overrides lazily computed facts.
        candidate_row = next((c for c in scored
                              if c["machine_id"] == assessment.recommended_candidate),
                             None)
        if candidate_row and not (candidate_row["compatible"]
                                  and candidate_row["available"]):
            assessment.recommended_candidate = (
                winner["machine_id"] if winner else None)
            assessment.summary += (
                " [coordinator note: model pick was overruled — candidate not "
                "healthy/compatible]")
    except Exception:
        # Offline / model failed: fall back to the fully deterministic wording.
        if winner is None and not scored:
            raise
        assessment = _deterministic_assessment(
            job_id, remaining, scored, idle, winner, delay, loss_avoided)
    return assessment


def _deterministic_assessment(
    job_id: str,
    remaining: int,
    scored: list[dict],
    idle: dict,
    winner: dict | None,
    delay: float,
    loss_avoided: float | None,
) -> ProductionAssessment:
    eligible = [c["machine_id"] for c in scored
                if c["compatible"] and c["available"]]
    if winner:
        summary = (
            f"Job {job_id} has {remaining} units remaining. {len(eligible)} "
            f"compatible machine(s) are healthy ({', '.join(eligible) or 'none'}). "
            f"Lowest-delay pick is {winner['machine_id']} with "
            f"{winner['queue_behind_units']} queued units ahead "
            f"(~{winner['queue_hours']} h wait, incremental cost "
            f"{winner['incremental_cost_usd']} USD). Doing nothing costs "
            f"{idle.get('total_usd')} USD per idle half-hour, so the reroute "
            f"avoids {loss_avoided if loss_avoided is not None else 0} USD.")
        return ProductionAssessment(
            paused_job_id=job_id,
            remaining_quantity=remaining,
            candidates=scored,
            recommended_candidate=winner["machine_id"],
            est_run_hours_on_recommended=winner.get("est_run_hours"),
            est_incremental_cost_usd=winner.get("incremental_cost_usd"),
            expected_delay_hours=delay,
            operational_loss_if_idle_usd=float(idle.get("total_usd", 0.0)),
            loss_avoided_usd=loss_avoided,
            confidence="high" if eligible else "low",
            summary=summary[:900],
        )
    return ProductionAssessment(
        paused_job_id=job_id,
        remaining_quantity=remaining,
        candidates=scored,
        recommended_candidate=None,
        operational_loss_if_idle_usd=float(idle.get("total_usd", 0.0)),
        confidence="low",
        summary=(f"Job {job_id} has {remaining} units remaining but no healthy "
                 f"compatible machine is available now; wait for the repair."),
    )
