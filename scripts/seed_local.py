#!/usr/bin/env python3
"""Seed the local FactoryWorld database deterministically.

Usage:
    python3.11 scripts/seed_local.py            # reset + seed + validate + summary
    python3.11 scripts/seed_local.py --verify   # additionally prove determinism
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.world import repositories as repo          # noqa: E402
from app.world.simulation import FactoryWorld        # noqa: E402


def validate(world: FactoryWorld) -> list[str]:
    """Integrity assertions from plan §13; empty list = clean."""
    problems: list[str] = []
    conn = world.conn
    machine_ids = {m["machine_id"] for m in repo.list_machines(conn)}
    machine_types = {m["machine_type"] for m in repo.list_machines(conn)}

    for sql, label in (
        ("SELECT DISTINCT machine_id AS x FROM sensor_readings", "telemetry"),
        ("SELECT DISTINCT machine_id AS x FROM maintenance_history", "history"),
        ("SELECT DISTINCT machine_id AS x FROM production_jobs", "jobs"),
        ("SELECT DISTINCT machine_id AS x FROM work_orders", "work orders"),
        ("SELECT DISTINCT machine_id AS x FROM downtime_events", "downtime"),
    ):
        for row in conn.execute(sql):
            if row["x"] not in machine_ids:
                problems.append(f"{label} row references unknown machine {row['x']}")

    for part in repo.list_spare_parts(conn):
        for t in part["compatible_types"].split(";"):
            if t.strip() and t.strip() not in machine_types:
                problems.append(f"part {part['part_id']} references unknown type {t}")
        if part["stock_qty"] < 0:
            problems.append(f"part {part['part_id']} has negative stock")

    for job in conn.execute("SELECT job_id, produced_qty, good_qty, scrap_qty, target_qty FROM production_jobs"):
        if job["produced_qty"] > job["target_qty"]:
            problems.append(f"{job['job_id']} overproduced")
        if job["good_qty"] + job["scrap_qty"] != job["produced_qty"]:
            problems.append(f"{job['job_id']} unit split inconsistent")
    return problems


def summary(world: FactoryWorld) -> dict:
    counts = {
        "Machines": len(repo.list_machines(world.conn)),
        "Telemetry rows": repo.count_telemetry(world.conn),
        "Production jobs": repo.count_jobs(world.conn),
        "Parts": len(repo.list_spare_parts(world.conn)),
        "Maintenance records": repo.count_maintenance(world.conn),
        "Work orders": repo.count_work_orders(world.conn),
        "Incidents": repo.count_incidents(world.conn),
    }
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify", action="store_true",
                        help="reseed a second time and prove identical content")
    args = parser.parse_args()

    world = FactoryWorld()
    counts = world.reset_world()
    counts_summary = summary(world)
    problems = validate(world)

    machine = world.get_machine("CNC-03")
    part = world.get_spare_part("BRG-AX-17")
    scenario_ok = (
        machine is not None
        and machine["machine_type"] == "CNC"
        and part is not None
        and "CNC" in part["compatible_types"]
        and part["stock_qty"] <= part["reorder_point"]
        and len([h for h in world.get_machine_history("CNC-03")
                 if h["part_id"] == "BRG-AX-17"]) >= 2
    )

    print("Factora FactoryWorld seeded")
    print()
    for label, value in counts_summary.items():
        print(f"{label}: {value:,}")
    print()
    print(f"CNC-03 state: {machine['state']} (health {machine['health_score']})")
    print(f"BRG-AX-17: stock {part['stock_qty']} / reorder {part['reorder_point']}")
    print(f"CNC-03 scenario: {'VERIFIED' if scenario_ok else 'FAILED'}")

    if args.verify:
        digest_a = _audit(world)
        world.reset_world()
        digest_b = _audit(world)
        print(f"Determinism: {'VERIFIED' if digest_a == digest_b else 'FAILED'}"
              f" (digest {digest_a[:12]})")
        if digest_a != digest_b:
            problems.append("reseed digest mismatch")

    if problems:
        print()
        print("VALIDATION PROBLEMS:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Validation: PASS")
    return 0


def _audit(world: FactoryWorld) -> str:
    from app.world.seed import audit_digest

    return audit_digest(world.conn)


if __name__ == "__main__":
    sys.exit(main())
