"""Factory Finance Agent — internal Factora runtime product agent.

N4 specialist #2. It reviews the operational options financially: does moving
the paused job beat waiting for the repair? All arithmetic lives in the
deterministic economics layer (`do_nothing_cost`, `reroute_cost`,
`reroute_benefit`); the agent retrieves the numbers with tools and returns a
structured verdict. 1 model call maximum, 0 offline.

IMPORTANT (sponsor hygiene): this is Factora's *runtime factory decision*
specialist. cfo.ai is a hackathon sponsor used separately to model Factora's
own business. Never conflate the two.
"""

from __future__ import annotations

from ..observability import get_observability
from ..world import economics
from ..world.simulation import FactoryWorld
from .llm import TASK_FINANCE_ASSESSMENT, AgentModel, complete_structured
from .models import FinanceAssessment
from .tools import ToolContext, execute_tool

SYSTEM_PROMPT = (
    "You are Factora's factory finance specialist. You compare the cost of "
    "waiting against the cost of acting, using only the deterministic figures "
    "given to you; you never invent costs and never approve spending beyond "
    "policy. Reply with a single JSON object only."
)


def _lazy_span(kind: str, **attributes):
    return get_observability().lazy_span(kind=kind, **attributes)


@_lazy_span(kind="AGENT", name="factory_finance", role="specialist")
def evaluate(
    world: FactoryWorld,
    ctx: ToolContext,
    model: AgentModel,
    *,
    job_id: str,
    candidate_machine_id: str | None,
    on_event=None,
) -> FinanceAssessment:
    """Price WAIT vs REROUTE deterministically; the model only frames it."""
    do_nothing = execute_tool(ctx, "calculate_do_nothing_cost", {})
    if not do_nothing.ok:
        raise RuntimeError(f"finance agent: {do_nothing.error}")
    idle = do_nothing.output

    if candidate_machine_id is None:
        # No viable candidate anywhere: finance can only endorse waiting.
        return FinanceAssessment(
            baseline_do_nothing_cost_usd=float(idle["total_usd"]),
            candidate_action_cost_usd=0.0,
            estimated_loss_avoided_usd=0.0,
            net_benefit_usd=0.0,
            recommendation="WAIT",
            rationale=(
                f"No healthy compatible machine exists, so the only financial "
                f"path is waiting; do-nothing exposure is "
                f"{idle['total_usd']} USD per half-hour of idleness."),
        )

    reroute = execute_tool(
        ctx, "calculate_reroute_cost",
        {"job_id": job_id, "candidate_machine_id": candidate_machine_id,
         "hours_behind": 0.0})
    if not reroute.ok:
        raise RuntimeError(f"finance agent: {reroute.error}")
    action = reroute.output
    benefit = economics.reroute_benefit(dict(_job(ctx, job_id)), idle, action)

    payload = {
        "wait_cost_usd": idle["total_usd"],
        "reroute_cost_usd": action["total_usd"],
        "loss_avoided_usd": benefit["loss_avoided_usd"],
        "net_benefit_usd": benefit["net_benefit_usd"],
        "candidate": candidate_machine_id,
    }
    user = (
        f"Factory finance review for job {job_id}:\n"
        f"- WAIT (assignment unchanged): {idle['total_usd']} USD exposure over "
        f"the modelled idle window.\n"
        f"- REROUTE to {candidate_machine_id}: {action['total_usd']} USD "
        f"operating + delay cost.\n"
        f"- Loss avoided: {benefit['loss_avoided_usd']} USD; net benefit "
        f"{benefit['net_benefit_usd']} USD.\n"
        "State the recommendation (REROUTE only when net benefit is strictly "
        "positive) with a one-paragraph rationale quoting these numbers."
    )
    hints = {"tools": payload,
             "machine": {"machine_id": ctx.incident_machine_id()},
             "job": {"job_id": job_id}}
    try:
        assessment = complete_structured(
            model, FinanceAssessment, system=SYSTEM_PROMPT, user=user,
            task=TASK_FINANCE_ASSESSMENT, hints=hints, on_event=on_event)
        # Deterministic cross-check: the model cannot flip the sign of the math.
        if ((benefit["net_benefit_usd"] > 0
             and assessment.recommendation != "REROUTE")
                or (benefit["net_benefit_usd"] <= 0
                    and assessment.recommendation != "WAIT")):
            assessment = _deterministic(payload, benefit)
    except Exception:
        assessment = _deterministic(payload, benefit)
    return assessment


def _job(ctx: ToolContext, job_id: str) -> dict:
    job = ctx.world.get_job(job_id)
    return job or {"machine_id": "", "target_qty": 0, "produced_qty": 0}


def _deterministic(payload: dict, benefit: dict) -> FinanceAssessment:
    positive = benefit["net_benefit_usd"] > 0
    return FinanceAssessment(
        baseline_do_nothing_cost_usd=payload["wait_cost_usd"],
        candidate_action_cost_usd=payload["reroute_cost_usd"],
        estimated_loss_avoided_usd=benefit["loss_avoided_usd"],
        net_benefit_usd=benefit["net_benefit_usd"],
        recommendation="REROUTE" if positive else "WAIT",
        rationale=(
            f"Waiting costs {payload['wait_cost_usd']} USD versus "
            f"{payload['reroute_cost_usd']} USD to reroute to "
            f"{payload['candidate']}; avoiding "
            f"{benefit['loss_avoided_usd']} USD of loss gives a net benefit of "
            f"{benefit['net_benefit_usd']} USD "
            f"({'reroute' if positive else 'wait recommended'})."),
    )
