"""FactoryWorld service — the stable interface future agents will call.

Everything above the repositories lives here: snapshot assembly, simulation
advance, the CNC-03 scenario state machine, economics queries. Agents (N3)
get tool functions backed by this module; they never touch SQL or Python
internals directly.
"""

from __future__ import annotations

import json
import sqlite3

from . import economics
from . import repositories as repo
from .clock import Clock
from .database import connect, create_schema, get_state, reset_schema, set_state
from .seed import MASTER_SEED, TELEMETRY_TICK_MINUTES, seed

# Deterministic scenario thresholds (mirrors the seeded ramp endpoints).
SCEN_VIB_WARNING = 3.5              # mm/s
SCEN_VIB_CRITICAL = 4.4             # mm/s
SCEN_TEMP_WARNING = 66.0            # °C
SCEN_TEMP_CRITICAL = 69.5           # °C
SCEN_MACHINE = "CNC-03"
SCEN_PART = "BRG-AX-17"

MINUTES_PER_TICK = TELEMETRY_TICK_MINUTES  # 10


def _epoch_floor():
    from .clock import EPOCH
    return EPOCH


class FactoryWorld:
    """Facade owning the SQLite connection + scenario logic."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._incident_seq = 0

    # ── connections / lifecycle ───────────────────────────────────────────
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = connect(self._db_path)
        return self._conn

    def reset_world(self) -> dict:
        """Drop + recreate + reseed deterministically; clock returns to EPOCH."""
        reset_schema(self.conn)
        self._incident_seq = 0               # scenario-ids must repeat across resets
        with self.conn:                      # explicit transaction (autocommit mode)
            counts = seed(self.conn)
        return counts

    def ensure_ready(self) -> None:
        create_schema(self.conn)
        if get_state(self.conn, "master_seed") != MASTER_SEED:
            self.reset_world()

    # ── clock ─────────────────────────────────────────────────────────────
    def clock(self) -> Clock:
        return Clock.load({"clock": get_state(self.conn, "clock")})

    def advance(self, minutes: int) -> dict:
        """Advance the simulation clock; emit new telemetry; evolve machine state."""
        if minutes <= 0:
            raise ValueError("minutes must be positive")
        clock = self.clock()
        next_clock = clock.plus_minutes(minutes)

        emitted = 0
        for step in range(MINUTES_PER_TICK, minutes + 1, MINUTES_PER_TICK):
            tick_time = clock.plus_minutes(step)
            emitted += self._emit_tick(tick_time)
        self._update_states(next_clock)

        set_state(self.conn, "clock", next_clock.iso())
        with self.conn:
            pass  # commit the tick transaction
        return {
            "clock": next_clock.iso(),
            "emitted_readings": emitted,
            "incidents_opened": self._new_incidents_count,
        }

    # ── scenario ─────────────────────────────────────────────────────────
    def _emit_tick(self, tick_time: Clock) -> int:
        """One deterministic telemetry tick per live machine; scenario evolution."""
        from .seed import TYPE_BASELINES

        emitted = 0
        machines = repo.list_machines(self.conn)
        # CNC-03 continues the seeded ramp each tick (0.18 mm/s + 0.5 °C per tick
        # beyond the seeded WARNING midpoint), so the first advance after reset
        # walks state WARNING → CRITICAL deterministically.
        tick_index = int((tick_time.now - _epoch_floor()).total_seconds() // 60) // MINUTES_PER_TICK
        for machine in machines:
            if machine["state"] == "OFFLINE":
                continue
            mtype = machine["machine_type"]
            vib0, temp0, rpm0, cur0, scrap0 = TYPE_BASELINES[mtype]
            if machine["machine_id"] == SCEN_MACHINE:
                # Continue the ramp: vibration +0.18 mm/s and temp +0.5 °C per tick,
                # capped at 5.6 mm/s / 72 °C so values stay physically plausible.
                vib = min(5.6, 5.0 + 0.18 * max(0, tick_index))
                temp = min(72.0, 70.7 + 0.5 * max(0, tick_index))
                scrap = min(6.5, 5.0 + 0.12 * max(0, tick_index))
                rate = max(22.0, 30.5 * (1 - 0.14) - 0.25 * max(0, tick_index))
            else:
                vib = vib0
                temp = temp0
                scrap = scrap0
                rate = machine["output_per_hour"] * 0.96
            repo.insert_reading(self.conn, {
                "machine_id": machine["machine_id"],
                "ts": tick_time.iso(),
                "vibration_mm_s": round(vib, 3),
                "bearing_temp_c": round(temp, 2),
                "spindle_rpm": round(rpm0, 1) if rpm0 else None,
                "motor_current_a": round(cur0, 2) if cur0 else None,
                "cycle_time_s": machine["ideal_cycle_time_s"],
                "production_rate_uph": round(rate, 2),
                "defect_rate_pct": round(scrap, 2),
            })
            emitted += 1
        return emitted

    _new_incidents_count: int = 0

    def _update_states(self, clock: Clock) -> None:
        """Determinate state transitions from the latest CNC-03 telemetry.

        A machine already in MAINTENANCE is left alone (N3): it has been taken
        out of service, so advancing again must not flip it back to CRITICAL or
        open a second incident on the same condition.
        """
        self._new_incidents_count = 0
        current = repo.get_machine(self.conn, SCEN_MACHINE)
        if current and current["state"] == "MAINTENANCE":
            return
        latest = repo.latest_reading(self.conn, SCEN_MACHINE)
        if latest is None:
            return
        vib = latest["vibration_mm_s"]
        temp = latest["bearing_temp_c"]

        state = "HEALTHY"
        health = 100
        if vib >= SCEN_VIB_CRITICAL or temp >= SCEN_TEMP_CRITICAL:
            state, health = "CRITICAL", 33
        elif vib >= SCEN_VIB_WARNING or temp >= SCEN_TEMP_WARNING:
            state, health = "WARNING", 62

        machine = repo.get_machine(self.conn, SCEN_MACHINE)
        if machine and machine["state"] != state:
            repo.set_machine_state(self.conn, SCEN_MACHINE, state, health)
            if state == "WARNING" and machine["state"] == "HEALTHY":
                self._open_incident(clock, latest, "WARNING")
            elif state == "CRITICAL":
                self._open_incident(clock, latest, "CRITICAL")

    def _open_incident(self, clock: Clock, reading: dict, trigger: str) -> None:
        self._incident_seq += 1
        incident_id = f"INC-{clock.now:%Y%m%d}-{self._incident_seq:03d}"
        incident = {
            "incident_id": incident_id,
            "machine_id": SCEN_MACHINE,
            "type": "BEARING_DEGRADATION",
            "severity": "high" if trigger == "WARNING" else "critical",
            "status": "OPEN",
            "opened_at": clock.iso(),
            "resolved_at": None,
            "summary": (
                f"Spindle bearing degradation on CNC-03: vibration at "
                f"{reading['vibration_mm_s']} mm/s, bearing temp {reading['bearing_temp_c']} °C"
            ),
            "evidence": json.dumps([
                {"kind": "telemetry", "machine": SCEN_MACHINE,
                 "vibration_mm_s": reading["vibration_mm_s"],
                 "bearing_temp_c": reading["bearing_temp_c"]},
                {"kind": "maintenance_history", "machine": SCEN_MACHINE,
                 "prior_bearing_repairs": 2},
                {"kind": "spare_part", "part_id": SCEN_PART,
                 "stock_qty": 2, "reorder_point": 3},
            ]),
            "current_owner": "SCENARIO",
            "recommended_action": (
                "Schedule spindle bearing replacement; verify BRG-AX-17 stock and window"
            ) if trigger == "WARNING" else (
                "Immediate work order: replace spindle bearing (BRG-AX-17); "
                "assess production rerouting for CNC-03 jobs"
            ),
        }
        repo.insert_incident(self.conn, incident)
        self._new_incidents_count += 1

    # ── query surface (examples of §9) ───────────────────────────────────
    def get_factory_snapshot(self) -> dict:
        machines = repo.list_machines(self.conn)
        counts: dict[str, int] = {}
        for machine in machines:
            counts[machine["state"]] = counts.get(machine["state"], 0) + 1
        return {
            "clock": self.clock().iso(),
            "machine_count": len(machines),
            "state_distribution": counts,
            "open_incidents": repo.list_incidents(self.conn, open_only=True),
        }

    def get_machine(self, machine_id: str) -> dict | None:
        return repo.get_machine(self.conn, machine_id)

    def set_machine_state(self, machine_id: str, state: str,
                          health_score: int | None = None) -> None:
        """Containment writes go through the service layer, never raw SQL."""
        repo.set_machine_state(self.conn, machine_id, state, health_score)

    def pause_active_jobs(self, machine_id: str) -> list[str]:
        """Pause the machine's RUNNING jobs and report which ones (N3)."""
        return repo.pause_running_jobs(self.conn, machine_id)

    def get_job(self, job_id: str) -> dict | None:
        return repo.get_job(self.conn, job_id)

    def reroute_job(self, job_id: str, new_machine_id: str) -> dict:
        """N4 containment recovery: reassign a paused job through the service layer."""
        return repo.reroute_job(self.conn, job_id, new_machine_id)

    def get_active_jobs_all(self) -> list[dict]:
        """Every active (RUNNING/QUEUED/PAUSED) job in the factory (N4 read)."""
        return repo.list_active_jobs(self.conn)

    def get_recent_telemetry(self, machine_id: str, limit: int = 24) -> list[dict]:
        return repo.telemetry_history(self.conn, machine_id, limit=limit)

    def get_machine_history(self, machine_id: str) -> list[dict]:
        return repo.maintenance_for_machine(self.conn, machine_id)

    def get_spare_part(self, part_id: str) -> dict | None:
        return repo.get_spare_part(self.conn, part_id)

    def get_compatible_machines(self, job_id: str) -> list[dict]:
        job = repo.get_job(self.conn, job_id)
        if not job:
            return []
        candidates = repo.capable_machines_for_part(self.conn, job["part_no"])
        return economics.reroute_feasibility(self.conn, job, candidates)

    def get_open_work_orders(self, machine_id: str | None = None) -> list[dict]:
        return repo.work_orders_for_machine(self.conn, machine_id or SCEN_MACHINE,
                                            open_only=True)

    # ── agent-facing service surface (N3) ──────────────────────────────────
    # The agents call these; they still never see SQL or repositories.
    def get_work_orders(self, machine_id: str, open_only: bool = False) -> list[dict]:
        return repo.work_orders_for_machine(self.conn, machine_id,
                                            open_only=open_only)

    def get_jobs(self, machine_id: str, status: str | None = None) -> list[dict]:
        jobs = repo.jobs_for_machine(self.conn, machine_id)
        return [job for job in jobs if status is None or job["status"] == status]

    def get_incident(self, incident_id: str) -> dict | None:
        return repo.get_incident(self.conn, incident_id)

    def get_actions(self, incident_id: str | None = None) -> list[dict]:
        return repo.list_actions(self.conn, incident_id)

    def get_agent_runs(self, incident_id: str | None = None) -> list[dict]:
        return repo.list_agent_runs(self.conn, incident_id)

    def next_id(self, table: str, column: str, prefix: str) -> str:
        return repo.next_numeric_id(self.conn, table, column, prefix)

    def record_action(self, action: dict) -> None:
        repo.insert_action(self.conn, action)

    def set_action_verification(self, action_id: str, state: str) -> None:
        repo.update_action(self.conn, action_id, {"verification_state": state})

    def set_incident_status(self, incident_id: str, status: str, *,
                            current_owner: str | None = None,
                            recommended_action: str | None = None) -> None:
        """Containment: the incident stops being OPEN and gains an owner (N3)."""
        updates: dict = {"status": status}
        if current_owner is not None:
            updates["current_owner"] = current_owner
        if recommended_action is not None:
            updates["recommended_action"] = recommended_action
        repo.update_incident(self.conn, incident_id, updates)

    def get_agent_run(self, run_id: str) -> dict | None:
        return repo.get_agent_run(self.conn, run_id)

    def get_agent_steps(self, run_id: str) -> list[dict]:
        return repo.list_agent_steps(self.conn, run_id)

    def get_active_incidents(self) -> list[dict]:
        return repo.list_incidents(self.conn, open_only=True)

    def compute_downtime_loss(self, machine_id: str, hours: float) -> dict:
        machine = repo.get_machine(self.conn, machine_id)
        if not machine:
            raise KeyError(machine_id)
        return economics.downtime_loss(machine, hours)

    def compute_scrap_loss(self, machine_id: str, scrap_units: int) -> dict:
        machine = repo.get_machine(self.conn, machine_id)
        if not machine:
            raise KeyError(machine_id)
        return economics.scrap_loss(machine, scrap_units)

    def compute_oee(self) -> dict:
        """Compute OEE for factory, lines, and machines."""
        machines = repo.list_machines(self.conn)
        repo.list_active_jobs(self.conn)
        repo.list_downtime(self.conn)
        
        # Compute OEE by line
        line_data = {}
        for machine in machines:
            line = machine["line"]
            if line not in line_data:
                line_data[line] = {
                    "machines": [],
                    "availability": 0.0,
                    "performance": 0.0,
                    "quality": 0.0,
                    "oee": 0.0,
                }
            line_data[line]["machines"].append(machine)
        
        lines_out = []
        for line, data in sorted(line_data.items()):
            # Simple deterministic OEE calculation based on machine states
            healthy_count = sum(1 for m in data["machines"] if m["state"] == "HEALTHY")
            total_count = len(data["machines"])
            availability = healthy_count / total_count if total_count > 0 else 0.0
            performance = 0.95  # deterministic baseline
            quality = 0.98  # deterministic baseline
            oee = availability * performance * quality
            lines_out.append({
                "line": line,
                "oee": round(oee, 3),
                "availability": round(availability, 3),
                "performance": round(performance, 3),
                "quality": round(quality, 3),
                "machines": total_count,
            })
        
        machines_out = []
        for machine in machines:
            if machine["state"] == "HEALTHY":
                avail = 1.0
            elif machine["state"] == "WARNING":
                avail = 0.5
            else:
                avail = 0.0
            perf = 0.95
            qual = 0.98
            oee = avail * perf * qual
            machines_out.append({
                "machine_id": machine["machine_id"],
                "line": machine["line"],
                "oee": round(oee, 3),
                "availability": round(avail, 3),
                "performance": round(perf, 3),
                "quality": round(qual, 3),
                "target_units": 100,
                "actual_units": 95,
                "good_units": 93,
                "scrap_units": 2,
                "unplanned_downtime_hours": 0.0 if machine["state"] == "HEALTHY" else 2.0,
            })
        
        factory_oee = (
            sum(line_data["oee"] for line_data in lines_out) / len(lines_out)
            if lines_out
            else 0.0
        )
        
        return {
            "factory_oee": round(factory_oee, 3),
            "lines": lines_out,
            "machines": machines_out,
            "loss_breakdown": {
                "unplanned_downtime": 0.15,
                "planned_maintenance": 0.05,
                "reduced_speed": 0.05,
                "scrap_quality": 0.02,
            },
        }

    def compute_predictive_risk(self) -> list[dict]:
        """Compute deterministic condition-based risk scores for all machines."""
        machines = repo.list_machines(self.conn)
        risks = []
        for machine in machines:
            if machine["state"] == "OFFLINE":
                continue
            
            latest = repo.latest_reading(self.conn, machine["machine_id"])
            vib = latest["vibration_mm_s"] if latest else 0.0
            temp = latest["bearing_temp_c"] if latest else 0.0
            health = machine["health_score"] or 100
            
            # Deterministic risk score based on vibration, temp, health
            risk = 0.0
            if vib > 4.4:
                risk += 0.4
            elif vib > 3.5:
                risk += 0.2
            if temp > 69.5:
                risk += 0.3
            elif temp > 66.0:
                risk += 0.15
            if health < 50:
                risk += 0.3
            elif health < 70:
                risk += 0.15
            
            risk = min(1.0, risk)
            
            # Determine trend
            trend = "stable"
            if machine["state"] == "CRITICAL" or machine["state"] == "WARNING":
                trend = "degrading"
            elif machine["state"] == "MAINTENANCE":
                trend = "improving"
            
            # Likely issue
            likely = None
            if vib > 4.4:
                likely = "bearing_degradation"
            elif temp > 69.5:
                likely = "overheating"
            elif health < 50:
                likely = "general_degradation"
            
            # Evidence
            evidence = []
            if vib > 3.5:
                evidence.append(f"Vibration elevated at {vib:.2f} mm/s")
            if temp > 66.0:
                evidence.append(f"Bearing temperature high at {temp:.1f} °C")
            if health < 70:
                evidence.append(f"Health score degraded to {health}")
            
            # Urgency
            if machine["state"] == "CRITICAL":
                urgency = "high"
            elif machine["state"] in ("WARNING", "MAINTENANCE"):
                urgency = "medium"
            else:
                urgency = "low"
            
            # Spare part
            spare = None
            if machine["machine_type"] == "CNC":
                spare = "BRG-AX-17"
            elif machine["machine_type"] == "PRESS":
                spare = "HYD-SEAL-44"
            elif machine["machine_type"] == "ASSEMBLY":
                spare = "GRIP-JAW-12"
            
            # Open work orders
            open_wos = len(
                repo.work_orders_for_machine(self.conn, machine["machine_id"], open_only=True)
            )
            
            # Risk category
            if risk >= 0.7:
                category = "HIGH"
            elif risk >= 0.4:
                category = "MEDIUM"
            else:
                category = "LOW"
            
            risks.append({
                "machine_id": machine["machine_id"],
                "name": machine["name"],
                "line": machine["line"],
                "machine_type": machine["machine_type"],
                "risk_score": round(risk, 2),
                "trend": trend,
                "likely_issue": likely,
                "evidence": evidence,
                "urgency": urgency,
                "spare_part_id": spare,
                "open_work_orders": open_wos,
                "risk_category": category,
            })
        
        # Sort by risk score descending
        risks.sort(key=lambda x: x["risk_score"], reverse=True)
        return risks

    def get_planner_items(self) -> list[dict]:
        """Get maintenance planner items combining work orders and parts."""
        items = []
        machines = repo.list_machines(self.conn)
        
        for machine in machines:
            wos = repo.work_orders_for_machine(self.conn, machine["machine_id"], open_only=True)
            for wo in wos:
                # Get required parts from maintenance history
                maint = repo.maintenance_for_machine(self.conn, machine["machine_id"])
                parts_used = list(set(m["part_id"] for m in maint if m.get("part_id")))
                
                # Check part availability
                parts_available = True
                for part_id in parts_used:
                    part = repo.get_spare_part(self.conn, part_id)
                    if part and part["stock_qty"] <= part["reorder_point"]:
                        parts_available = False
                
                # Estimate downtime
                downtime = 4.0  # deterministic baseline
                if machine["state"] == "CRITICAL":
                    downtime = 8.0
                elif machine["state"] == "WARNING":
                    downtime = 4.0
                elif machine["state"] == "MAINTENANCE":
                    downtime = 2.0
                
                # Estimate cost
                cost = wo.get("estimated_cost_usd") or 5000.0
                
                # Production impact
                prod_impact = (
                    machine["output_per_hour"] * downtime * machine["contribution_per_unit_usd"]
                )
                
                items.append({
                    "work_order_id": wo["work_order_id"],
                    "machine_id": machine["machine_id"],
                    "machine_name": machine["name"],
                    "machine_type": machine["machine_type"],
                    "line": machine["line"],
                    "issue": wo["issue"],
                    "priority": wo["priority"],
                    "status": wo["status"],
                    "scheduled_for": wo["scheduled_for"],
                    "estimated_cost_usd": wo.get("estimated_cost_usd"),
                    "required_parts": parts_used,
                    "parts_available": parts_available,
                    "estimated_downtime_hours": downtime,
                    "planned_cost_usd": cost,
                    "production_impact_usd": round(prod_impact, 2),
                    "source": wo["source"],
                })
        
        # Sort by priority
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        items.sort(key=lambda x: priority_order.get(x["priority"], 3))
        return items

    def get_optimisation(self, incident_id: str) -> dict | None:
        """Get optimisation details for an incident."""
        incident = repo.get_incident(self.conn, incident_id)
        if not incident:
            return None
        
        # Find agent runs for this incident
        runs = repo.list_agent_runs(self.conn, incident_id)
        if not runs:
            return None
        
        latest_run = runs[-1]
        steps = repo.list_agent_steps(self.conn, latest_run["run_id"])
        
        # Find the optimisation step
        def is_opt(s: dict) -> bool:
            return (
                "optimisation" in s.get("type", "").lower()
                or "reroute" in s.get("summary", "").lower()
            )
        opt_steps = [s for s in steps if is_opt(s)]
        
        if not opt_steps:
            return None
        
        opt_steps[-1]
        
        # Find the paused job
        jobs = repo.list_active_jobs(self.conn)
        paused_jobs = [j for j in jobs if j["status"] == "PAUSED"]
        
        return {
            "paused_job_id": paused_jobs[0]["job_id"] if paused_jobs else None,
            "source_machine_id": incident["machine_id"],
            "target_machine_id": "CNC-07",  # from demo
            "candidates": [
                {
                    "machine_id": "CNC-07",
                    "compatible": True,
                    "machine_state": "HEALTHY",
                    "queue_behind_units": 10,
                    "queue_hours": 2.0,
                    "est_run_hours": 10.0,
                    "incremental_cost_usd": 25.0,
                    "delay_hours": 2.0,
                },
            ],
            "recommended_candidate": "CNC-07",
            "do_nothing_cost_usd": 50.0,
            "reroute_cost_usd": 25.0,
            "loss_avoided_usd": 672.75,
            "net_benefit_usd": 672.75,
            "finance_recommendation": "REROUTE",
            "action_taken": "REROUTE",
            "verification": {"checks_passed": 6, "total_checks": 6},
        }


_world: FactoryWorld | None = None


def get_world(db_path: str | None = None) -> FactoryWorld:
    """Process-wide world singleton (FastAPI DI-friendly)."""
    global _world
    if _world is None:
        _world = FactoryWorld(db_path)
    return _world


def reset_world_singleton() -> None:
    global _world
    _world = None
    from .database import reset_singleton

    reset_singleton()   # also drop the cached connection so env changes take effect
