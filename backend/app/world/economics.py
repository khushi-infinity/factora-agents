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
