"""Full N3→N4 demo command.

Executes the flagship autonomous flow from reset through to verified optimisation.

Normal mode:
  RESET → CNC-03 WARNING → ADVANCE → CRITICAL → Watcher → Maintenance →
  containment → verification → Production/Loss → Factory Finance → reroute →
  optimisation verification → FINAL VERIFIED STATE

Recovery mode (--recovery):
  includes work-order action failure → RECOVERING → retry → success

Usage:
  python3.11 scripts/run_full_demo.py
  python3.11 scripts/run_full_demo.py --recovery

The script calls real application/runtime services. No mock screenshots.
"""

from __future__ import annotations

import sys
import os

# Add backend to path so `app.*` imports work when script is run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def run_normal_demo():
    """Execute the normal N3→N4 autonomous flow."""
    from app.agents.coordinator import RunOptions, respond_to_escalation
    from app.agents.watcher import evaluate_world
    from app.agents import DeterministicAgentModel

    print("=" * 60)
    print("FACTORA — Full Autonomous Flow (Normal)")
    print("=" * 60)

    from app.world.simulation import FactoryWorld, reset_world_singleton
    reset_world_singleton()

    w = FactoryWorld()
    w.reset_world()
    w.advance(30)

    print(f"\nState after advance(30):")
    m = w.get_machine("CNC-03")
    print(f"  CNC-03: state={m['state']}, health={m['health_score']}")

    escalations = evaluate_world(w)
    print(f"  Escalations detected: {len(escalations)}")

    if not escalations:
        print("  No escalations — cannot proceed with critical flow")
        return False

    model = DeterministicAgentModel()
    outcome = respond_to_escalation(w, escalations[0], model, RunOptions())

    print(f"\nOutcome: {outcome.status}")

    if outcome.status != "VERIFIED":
        print("  FAILED: Expected VERIFIED outcome")
        return False

    # Summarise steps
    print(f"\nTotal steps: {len(outcome.steps)}")
    for s in outcome.steps:
        tag = s["type"].upper()
        summary = s["summary"][:60]
        print(f"  Step {s['sequence']:2}: [{tag:10}] {summary}")

    print("\n✓ Normal flow completed successfully")
    return True


def run_recovery_demo():
    """Execute the recovery flow with work-order failure."""
    from app.agents.coordinator import RunOptions, respond_to_escalation
    from app.agents.watcher import evaluate_world
    from app.agents import DeterministicAgentModel

    print("\n" + "=" * 60)
    print("FACTORA — Full Autonomous Flow (Recovery)")
    print("=" * 60)

    from app.world.simulation import FactoryWorld, reset_world_singleton
    reset_world_singleton()

    w = FactoryWorld()
    w.reset_world()
    w.advance(30)

    print(f"\nState after advance(30):")
    m = w.get_machine("CNC-03")
    print(f"  CNC-03: state={m['state']}")

    escalations = evaluate_world(w)

    model = DeterministicAgentModel()
    outcome = respond_to_escalation(w, escalations[0], model, RunOptions(fail_first_work_order=True))

    print(f"\nOutcome: {outcome.status}")

    if outcome.status != "VERIFIED":
        print("  FAILED: Expected VERIFIED outcome")
        return False

    # Show recovery steps
    print(f"\nTotal steps: {len(outcome.steps)}")
    for s in outcome.steps:
        summary = s["summary"][:50]
        # Highlight recovery-related steps
        keywords = ["FAILED", "RECOVERING", "RETRY", "SUCCESS", "VERIFIED"]
        if any(kw in summary for kw in keywords):
            tag = s["type"].upper()
            print(f"  Step {s['sequence']:2}: [{tag:10}] {summary}")

    print("\n✓ Recovery flow completed successfully")
    return True


def main():
    """Entry point for full demo command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Factora full autonomous demo (N3→N4)"
    )
    parser.add_argument(
        "--recovery",
        action="store_true",
        default=False,
        help="Run recovery flow with work-order failure injection",
    )
    args = parser.parse_args()

    if args.recovery:
        success = run_recovery_demo()
    else:
        success = run_normal_demo()

    if not success:
        print("\n✗ Demo failed")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())