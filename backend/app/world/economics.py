"""Operational economics — deterministic formulas over seeded facts.

Every function here is pure: same inputs → same numbers. Values are synthetic
demo economics (machines table columns, labelled as demo docs), not industry
benchmarks.
"""

from __future__ import annotations


def downtime_loss(machine: dict, downtime_hours: float) -> dict:
    """Units + dollars lost while a machine cannot produce."""
    uph = machine["output_per_hour"]
    units = uph * downtime_hours
    margin = machine["contribution_per_unit_usd"]
    dollars = units * margin + machine["cost_per_hour_usd"] * downtime_hours
    return {
        "machine_id": machine["machine_id"],
        "downtime_hours": round(downtime_hours, 2),
        "lost_units": round(units, 1),
        "lost_contribution_usd": round(units * margin, 2),
        "idle_cost_usd": round(machine["cost_per_hour_usd"] * downtime_hours, 2),
        "total_usd": round(dollars, 2),
    }


def scrap_loss(machine: dict, scrap_units: int) -> dict:
    """Cost of scrapped units (material + cycle investment goodwill)."""
    scrap_cost = machine["scrap_cost_per_unit_usd"]
    return {
        "machine_id": machine["machine_id"],
        "scrap_units": scrap_units,
        "scrap_cost_usd": round(scrap_units * scrap_cost, 2),
    }


def reroute_feasibility(conn, job: dict, candidate_machine_ids: list[str]) -> list[dict]:
    """Deterministic reroute evaluation restricted to the job's machine type family.

    A CNC job can only move to machines of the SAME type (the capabilities table
    says which part numbers each *type* can make; mixing dissimilar equipment
    for a reroute would fabricate feasibility).
    """
    from . import repositories as repo

    origin = repo.get_machine(conn, job["machine_id"])
    if origin is None:
        return []
    same_type = [mid for mid in candidate_machine_ids
                 if (repo.get_machine(conn, mid) or {}).get("machine_type")
                 == origin["machine_type"]]
    remaining = job["target_qty"] - job["produced_qty"]
    options = []
    for mid in same_type:
        candidate = repo.get_machine(conn, mid)
        if not candidate or mid == job["machine_id"]:
            continue
        active = repo.jobs_for_machine(conn, mid, active_only=True)
        remaining_capacity = sum(j["target_qty"] - j["produced_qty"] for j in active)
        per_hour = candidate["output_per_hour"]
        options.append({
            "candidate_machine_id": mid,
            "part_compatible": job["part_no"] in _parts_of_type(conn, candidate),
            "machine_state": candidate["state"],
            "queue_behind_units": remaining_capacity,
            "est_hours_to_absorb": round(remaining / per_hour, 2) if per_hour else None,
            "cost_delta_usd_per_hour": round(
                candidate["cost_per_hour_usd"] - origin["cost_per_hour_usd"], 2),
        })
    options.sort(key=lambda o: (
        o["machine_state"] == "MAINTENANCE",
        not o["part_compatible"],
        o["queue_behind_units"],
    ))
    return options


def _parts_of_type(conn, machine: dict) -> list[str]:
    row = conn.execute(
        "SELECT part_no FROM capabilities WHERE machine_type = ?",
        (machine["machine_type"],)).fetchall()
    return [r["part_no"] for r in row]


# ── N4: production-loss model (deterministic; the LLM interprets, never calculates) ──

def do_nothing_cost(job: dict, paused_hours: float, delay_penalty_per_hour: float = 0.0) -> dict:
    """What the factory loses if it simply waits for the paused job's machine.

    Components (all from stored synthetic demo economics):
      * lost contribution — units that would have been made while idle;
      * idle machine cost — the contained machine still burns its hourly cost;
      * optional deadline penalty — modelled per late hour, defaults to zero
        (never invented when not modelled).
    """
    machine = {
        "machine_id": job["machine_id"],
        "output_per_hour": job["output_per_hour_of_source"],
        "contribution_per_unit_usd": job["contribution_per_unit_usd"],
        "cost_per_hour_usd": job["cost_per_hour_usd_of_source"],
    }
    loss = downtime_loss(machine, paused_hours)
    penalty = delay_penalty_per_hour * paused_hours
    return {
        "machine_id": job["machine_id"],
        "paused_hours": round(paused_hours, 2),
        "lost_contribution_usd": loss["lost_contribution_usd"],
        "idle_cost_usd": loss["idle_cost_usd"],
        "deadline_penalty_usd": round(penalty, 2),
        "total_usd": round(loss["total_usd"] + penalty, 2),
    }


def reroute_cost(job: dict, candidate: dict, hours_behind: float = 0.0) -> dict:
    """True *incremental* cost of moving the paused job onto one candidate.

    The remaining units have to be produced either way, so the reroute's normal
    operating cost is NOT a loss — what is genuinely incremental is:
      * the extra run time caused by absorbing the candidate's queue first
        (`hours_behind`), priced at the job's contribution margin (production
        the factory could have been doing in those hours);
      * any per-hour cost-rate delta between candidate and source machine.
    Everything else (units, part, due date) is unchanged by the move.
    """
    remaining = max(0, job["target_qty"] - job["produced_qty"])
    per_hour = candidate["output_per_hour"] or 0
    run_hours = remaining / per_hour if per_hour else float("inf")
    source_rate = job.get("cost_per_hour_usd_of_source") \
        or job.get("cost_per_hour_usd") or 0.0
    rate_delta_per_hour = max(0.0, candidate["cost_per_hour_usd"] - source_rate)
    rate_delta_cost = rate_delta_per_hour * run_hours if run_hours != float("inf") else 0.0
    return {
        "machine_id": candidate["machine_id"],
        "remaining_qty": remaining,
        "est_run_hours": round(run_hours, 2) if run_hours != float("inf") else None,
        "normal_run_cost_usd": round(
            run_hours * candidate["cost_per_hour_usd"], 2)
        if run_hours != float("inf") else None,
        "queue_hours": round(hours_behind, 2),
        # Queue time is NOT priced as lost contribution: the queued units
        # belong to the plant's own schedule and would be produced anyway;
        # the reroute only reorders them. Only a cost-rate increase is
        # genuinely incremental. (Queue hours are still reported so callers
        # can reason about lateness.)
        "delay_cost_usd": 0.0,
        "cost_rate_delta_usd_per_hour": round(rate_delta_per_hour, 2),
        "cost_rate_delta_usd": round(rate_delta_cost, 2),
        "total_usd": round(rate_delta_cost, 2),
    }


def reroute_benefit(job: dict, do_nothing: dict, reroute: dict) -> dict:
    """Net effect of rerouting vs waiting for the repair.

    WAIT cost: the job stays paused through the repair — the modelled idle
    window produces nothing (lost contribution + idle machine cost), so that
    is the whole exposure.
    REROUTE cost: only the *incremental* part of running on another machine
    (queue delay + rate delta) — the run itself happens in both scenarios.
    Net benefit = WAIT exposure − REROUTE incremental cost.
    """
    wait_cost = do_nothing["total_usd"]
    action_cost = reroute["total_usd"]
    # The reroute avoids the WAIT exposure only when the wait actually costs
    # more than the incremental action. Positive net ⇒ reroute is worthwhile.
    net = wait_cost - action_cost
    return {
        "do_nothing_cost_usd": wait_cost,
        "reroute_cost_usd": action_cost,
        "loss_avoided_usd": round(max(0.0, net), 2),
        "net_benefit_usd": round(net, 2),
    }
