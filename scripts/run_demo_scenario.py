#!/usr/bin/env python3
"""N1 demo scenario runner — environment only, no agents.

RESET → advance in beats → CNC-03 walks healthy→warning→critical → a
deterministic incident opens. Readable, concise console output.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.world import repositories as repo   # noqa: E402
from app.world.simulation import FactoryWorld  # noqa: E402


def latest_vib(world: FactoryWorld) -> float:
    reading = repo.latest_reading(world.conn, "CNC-03")
    return reading["vibration_mm_s"] if reading else float("nan")


def beat(world: FactoryWorld, minutes: int, label: str) -> None:
    before = repo.latest_reading(world.conn, "CNC-03")
    result = world.advance(minutes)
    after = repo.latest_reading(world.conn, "CNC-03")
    machine = world.get_machine("CNC-03")
    incidents = world.get_active_incidents()
    print(
        f"{label:>5}  clock {result['clock']}  "
        f"vib {before['vibration_mm_s']:.2f}→{after['vibration_mm_s']:.2f} mm/s  "
        f"temp {before['bearing_temp_c']:.1f}→{after['bearing_temp_c']:.1f} °C  "
        f"state {machine['state']}"
        + (f"  ⚠ {len(incidents)} open incident(s)" if incidents else "")
    )


def main() -> int:
    world = FactoryWorld()
    counts = world.reset_world()
    machine = world.get_machine("CNC-03")
    print("── RESET FACTORY " + "─" * 40)
    print(f"machines {counts['machines']} · telemetry {counts['telemetry_rows']:,} · "
          f"clock {world.clock().iso()}")
    print(f"CNC-03 starts {machine['state']} (health {machine['health_score']})")
    print()
    print("── DEGRADATION ARC " + "─" * 38)
    marker = 0
    for minutes, label in ((30, "T+30"), (30, "T+60"), (30, "T+90")):
        marker += minutes
        beat(world, minutes, label)
    for minutes in (10, 10, 10):        # finer steps into critical
        marker += minutes
        beat(world, minutes, f"T+{marker}")
    print()
    print("── END STATE " + "─" * 44)
    machine = world.get_machine("CNC-03")
    reading = repo.latest_reading(world.conn, "CNC-03")
    incidents = world.get_active_incidents()
    print(f"CNC-03: {machine['state']} · vib {reading['vibration_mm_s']:.2f} mm/s · "
          f"temp {reading['bearing_temp_c']:.1f} °C · clock {world.clock().iso()}")
    for incident in incidents:
        lines = incident["summary"]
        print(f"incident {incident['incident_id']} ({incident['severity']}): {lines}")
    print(f"part BRG-AX-17 stock: {world.get_spare_part('BRG-AX-17')['stock_qty']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
