#!/usr/bin/env python3
"""N3 autonomous demo — detect → investigate → act → verify, headless.

Two scenarios, both fully offline by default:

  1. successful autonomy   reset → +30 → CRITICAL → watcher → maintenance
                           investigates with tools → containment → VERIFIED
  2. recovery               same, but the first work-order tool call fails
                           on purpose and the coordinator retries once

The model is whichever `build_model()` selects:

  REAL MODEL MODE      OPENROUTER_API_KEY is set  → OpenRouter (free alias)
  DETERMINISTIC MODE   no key                     → labelled offline stand-in

Run:  python3.11 scripts/run_agent_demo.py [--recovery]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.agents import build_model, evaluate_world_for_escalations  # noqa: E402
from app.agents.coordinator import RunOptions, respond_to_escalation  # noqa: E402
from app.observability import get_observability  # noqa: E402
from app.world.simulation import FactoryWorld  # noqa: E402

MACHINE = "CNC-03"


def banner(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 66 - len(title)))


class _CountingModel:
    """Counts model calls so the demo can report its real token budget."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls = 0
        self.info = inner.info

    def complete(self, **kwargs) -> str:
        self.calls += 1
        return self._inner.complete(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery", action="store_true",
                        help="inject one work-order tool failure (scenario 2)")
    args = parser.parse_args()

    world = FactoryWorld()
    model = _CountingModel(build_model())

    banner("MODEL")
    print(f"provider  {model.info.provider}")
    print(f"name      {model.info.name}")
    print(f"mode      {model.info.mode.value}")
    print(f"detail    {model.info.detail}")
    print(f"neatlogs  {get_observability().status}")

    banner("STEP A — reset")
    counts = world.reset_world()
    print(f"clock {world.clock().iso()}  machines {counts['machines']}  "
          f"telemetry rows {counts['telemetry_rows']}")
    print(f"{MACHINE} state {world.get_machine(MACHINE)['state']} "
          f"(WARNING — no autonomous run yet)")
    print(f"watcher escalations: {len(evaluate_world_for_escalations(world))}")

    banner("STEP B — advance +30 sim minutes")
    result = world.advance(30)
    print(f"clock {result['clock']}  emitted {result['emitted_readings']} readings  "
          f"{MACHINE} state {world.get_machine(MACHINE)['state']}")
    escalations = evaluate_world_for_escalations(world)
    for escalation in escalations:
        print(f"watcher → {escalation.reason}")

    if not escalations:
        print("nothing to respond to")
        return 0

    banner("STEP C..H — autonomous response")
    outcome = respond_to_escalation(
        world, escalations[0], model,
        RunOptions(fail_first_work_order=args.recovery))

    print(f"run      {outcome.run_id}")
    print(f"status   {outcome.status}")
    for step in outcome.steps:
        marker = {"OK": "·", "FAILED": "✗", "PASS": "✓", "ALLOWED": "✓",
                  "REPAIR": "!", "ESCALATED": "✗", "FAIL": "✗"}.get(step["status"], "·")
        print(f"  {step['sequence']:>2} {marker} [{step['agent']:<12}] "
              f"{step['type']:<13} {step['summary']}")

    banner("RESULT")
    machine = world.get_machine(MACHINE)
    incident = world.get_incident(escalations[0].incident_id)
    orders = [order for order in world.get_work_orders(MACHINE)
              if order["source"] == "AGENT"]
    print(f"{MACHINE} state        {machine['state']}")
    print(f"incident status    {incident['status']}  owner {incident['current_owner']}")
    print(f"agent work orders  "
          + (", ".join(f"{o['work_order_id']} ({o['priority']})" for o in orders)
             or "none"))
    print(f"action ledger      "
          + ", ".join(f"{a['action_id']}:{a['action_type']}={a['verification_state']}"
                      for a in world.get_actions(incident["incident_id"])))
    print(f"outcome            {outcome.status} — {outcome.outcome}")
    print(f"model calls        {model.calls}")
    return 0 if outcome.status == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
