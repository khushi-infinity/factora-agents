Build-In-Public — Draft Posts for Actual Milestones

### N0
Fresh hackathon rebuild. Factora begins as a concept for autonomous factory optimisation.

### N1
Deterministic FactoryWorld. A simulated factory with machines, telemetry, production jobs, and parts inventory — entirely deterministic, no random failures.

### N2
Interactive Digital Twin. Browser-based 3D factory floor at `/twin` with real-time state display, machine counts, and attention/incident tracking. Command Center at `/`.

### N3
Autonomous maintenance agent + recovery. When CNC-03 goes CRITICAL, the Factory Watcher detects it automatically, the Coordinator assigns the Maintenance Agent, which investigates with real tools, containment executes (urgent work order + machine into MAINTENANCE + running job paused), the first work-order call fails deterministically, the Coordinator enters RECOVERING, retries successfully, and the run ends VERIFIED. Neatlogs traces every step.

### N4
Production/Loss + Finance coordination. After N3 containment, the Production/Loss Agent evaluates compatible candidate machines using deterministic loss/reroute economics. The Factory Finance Agent compares WAIT vs REROUTE using net benefit calculation (`wait_cost - reroute_incremental_cost`). The Optimisation Policy allows autonomous rer only when: job PAUSED, candidate compatible+HEALTHY, net benefit positive, cost below $2500 threshold. Reroute executes (job → target machine), 6/6 optimisation verification checks pass, and the factory is OPTIMISED. Neatlogs spans the full flow. cfo.ai inputs prepared but not yet modelled.

### N5 (current)
Sponsor evidence, demo polish, and submission readiness. Capturing product screenshots, agent evaluation metrics, Neatlogs traces, Entire checkpoints, cfo.ai assumptions, 3-minute demo video script, and README polish for judge comprehension. See `docs/SUBMISSION_CHECKLIST.md` for complete status.

---

TODO: add actual post URL for each milestone.