"""Deterministic factory seeding — fresh implementation for neatHack.

Determinism contract (plan §4/§13):
  * one master seed (`MASTER_SEED`);
  * one `random.Random` per domain, derived from the master seed via SHA-256 —
    reordering domain code never perturbs other domains;
  * fixed EPOCH from clock.py (never the wall clock);
  * re-running the seeder on a fresh schema yields identical row content
    (asserted by the test suite and by scripts/seed_local.py --verify).

The CNC-03 flagship scenario is regenerated here as a *progression*: telemetry
rows walk a deterministic ramp (vibration 2.4→~5.0 mm/s, bearing temp
62→~70.7 °C, rising scrap) rather than only storing endpoints — replayable by
`scripts/run_demo_scenario.py` because the ramp is a pure function of tick
offsets from the seeded start.
"""

from __future__ import annotations

import hashlib
import json
import random

from .clock import EPOCH, Clock
from .database import reset_schema, set_state

MASTER_SEED = "factora-neathack-2026-n1"
# Scenario window: telemetry history ticks (one per 10 min) before the clock start.
TELEMETRY_HOURS = 24
TELEMETRY_TICK_MINUTES = 10
TELEMETRY_TICKS = (TELEMETRY_HOURS * 60) // TELEMETRY_TICK_MINUTES  # 144

RNG_SEED_PREFIX = "v1:"

MASTER_MACHINES = [
    # (id, name, type, line, x, y)  — z=0 for all (single floor)
    ("CNC-01", "5-Axis Mill 1", "CNC", "CNC_LINE", 6, 18),
    ("CNC-02", "5-Axis Mill 2", "CNC", "CNC_LINE", 11, 18),
    ("CNC-03", "Vertical Mill 3", "CNC", "CNC_LINE", 16, 18),
    ("CNC-04", "Vertical Mill 4", "CNC", "CNC_LINE", 21, 18),
    ("CNC-05", "Turning Centre 5", "CNC", "CNC_LINE", 26, 18),
    ("CNC-06", "Turning Centre 6", "CNC", "CNC_LINE", 31, 18),
    ("CNC-07", "Horizontal Mill 7", "CNC", "CNC_LINE", 36, 18),
    ("CNC-08", "Horizontal Mill 8", "CNC", "CNC_LINE", 41, 18),
    ("PRS-01", "Press 1", "PRESS", "PRESS_LINE", 6, 34),
    ("PRS-02", "Press 2", "PRESS", "PRESS_LINE", 11, 34),
    ("PRS-03", "Press 3", "PRESS", "PRESS_LINE", 16, 34),
    ("PRS-04", "Press 4", "PRESS", "PRESS_LINE", 21, 34),
    ("ASM-01", "Assembly Cell 1", "ASSEMBLY", "ASSEMBLY_LINE", 6, 2),
    ("ASM-02", "Assembly Cell 2", "ASSEMBLY", "ASSEMBLY_LINE", 11, 2),
    ("ASM-03", "Assembly Cell 3", "ASSEMBLY", "ASSEMBLY_LINE", 16, 2),
    ("ASM-04", "Assembly Cell 4", "ASSEMBLY", "ASSEMBLY_LINE", 21, 2),
    ("ASM-05", "Assembly Cell 5", "ASSEMBLY", "ASSEMBLY_LINE", 26, 2),
    ("PKG-01", "Case Packer 1", "PACKAGING", "PACKAGING_LINE", 6, 50),
    ("PKG-02", "Case Packer 2", "PACKAGING", "PACKAGING_LINE", 11, 50),
    ("PKG-03", "Palletiser 3", "PACKAGING", "PACKAGING_LINE", 16, 50),
    ("QLT-01", "Vision Station 1", "QUALITY", "QUALITY_LINE", 6, 66),
    ("QLT-02", "Vision Station 2", "QUALITY", "QUALITY_LINE", 11, 66),
    ("QLT-03", "CMM 3", "QUALITY", "QUALITY_LINE", 16, 66),
]

# Snapshot states at the end of seeding. CNC-03 is seeded mid-ramp at WARNING
# (history shows the full degradation arc; the live `advance()` walk finishes the
# walk to CRITICAL — the demo narrative: healthy arc → T+90 warning → T+120 critical).
SNAPSHOT_STATES = {
    "CNC-03": "WARNING",
    "CNC-06": "WARNING",
    "PRS-03": "MAINTENANCE",
    "PKG-03": "OFFLINE",
}

# Demo economics (synthetic values, labelled as demo in data + docs).
TYPE_ECONOMICS = {
    #            ideal cyl   out/hr   cost/h   margin/unit  scrap cost/unit
    "CNC":       (118, 30.5, 95.0, 41.0, 3.10),
    "PRESS":     (6.5, 553.8, 70.0, 0.35, 0.18),
    "ASSEMBLY":  (46.0, 78.3, 55.0, 1.90, 0.80),
    "PACKAGING": (1.8, 2000.0, 40.0, 0.05, 0.02),
    "QUALITY":   (22.0, 163.6, 60.0, 0.0, 0.0),   # inspection: no production contribution
}

TYPE_BASELINES = {
    #            vibration  bearing temp  rpm       current   scrap%
    "CNC":       (2.3, 62.0, 8200.0, 24.0, 0.8),
    "PRESS":     (1.8, 55.0, 0.0, 15.0, 1.1),
    "ASSEMBLY":  (0.9, 48.0, 0.0, 9.0, 0.9),
    "PACKAGING": (0.7, 44.0, 0.0, 6.0, 0.5),
    "QUALITY":   (0.5, 40.0, 0.0, 4.0, 0.0),
}

SPARE_PARTS = [
    ("BRG-AX-17", "Axial spindle bearing 7014 CTYNDUL P4", "bearing", "CNC",
     2, 3, 412.00, 7, "Gulf Bearing Trading LLC"),
    ("BRG-RD-08", "Radial bearing 6208-2RS", "bearing", "CNC;PRESS;ASSEMBLY",
     9, 4, 63.50, 3, "Gulf Bearing Trading LLC"),
    ("BLT-GT-21", "Timing belt GT2 640-8M", "belt", "PRESS;PACKAGING",
     6, 3, 88.00, 5, "Emirates Drives FZE"),
    ("FLT-HY-30", "Hydraulic filter HF-30", "filter", "PRESS",
     14, 6, 27.90, 2, "Gulf Bearing Trading LLC"),
    ("SNS-IR-12", "IR temp sensor module", "sensor", "CNC;ASSEMBLY;QUALITY",
     8, 4, 145.00, 4, "Precision Gulf Instruments"),
    ("LUB-SP-05", "Spindle grease cartridge", "lubricant", "CNC",
     11, 5, 33.00, 2, "Emirates Drives FZE"),
    ("SRV-M20",   "Servo drive module 20A", "electrical", "CNC;ASSEMBLY",
     3, 2, 1250.00, 10, "Precision Gulf Instruments"),
    ("PKB-SET-7", "Packaging belt set", "belt", "PACKAGING",
     5, 2, 210.00, 6, "Emirates Drives FZE"),
]

PRODUCTS = ["FA-1420", "FA-2410", "FA-3105", "FA-4020", "FA-5008"]

MAINTENANCE_SEEDS = [
    # (machine, issue, action, part, downtime_h, cost)
    ("CNC-03", "Bearing wear — metal particles in grease", "Replaced spindle front bearing",
     "BRG-AX-17", 6.5, 1980.00),
    ("CNC-03", "Spindle vibration alarm at 6.1 mm/s", "Replaced spindle front bearing",
     "BRG-AX-17", 5.0, 1650.00),
    ("CNC-03", "Scheduled 6-month spindle inspection", "Inspection + regrease",
     "LUB-SP-05", 1.5, 220.00),
    ("CNC-01", "Coolant pump seal leak", "Replaced pump seal kit", None, 3.0, 340.00),
    ("CNC-02", "Tool changer jam", "Repaired carousel indexing sensor", "SNS-IR-12", 2.0, 510.00),
    ("PRS-03", "Hydraulic leak at main cylinder", "Replaced hydraulic filter + seals",
     "FLT-HY-30", 7.0, 1220.00),
    ("PRS-03", "Scheduled preventive maintenance", "Belt + filter replacement",
     "BLT-GT-21", 4.0, 460.00),
    ("PKG-03", "Case packer drive belt snapped", "Replaced belt set", "PKB-SET-7", 6.0, 780.00),
    ("ASM-01", "Torque driver out of calibration", "Recalibrated driver", None, 1.0, 150.00),
    ("QLT-01", "Vision lens contamination", "Cleaned + recalibrated optics", "SNS-IR-12",
     0.8, 90.00),
]


def _rng(domain: str) -> random.Random:
    """Deterministic per-domain RNG: SHA-256(master seed + domain) → 64-bit seed."""
    digest = hashlib.sha256(f"{RNG_SEED_PREFIX}{MASTER_SEED}:{domain}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _dag(capable_machines: list[str], jobs_per_machine: int, due_days: int,
         rng: random.Random) -> list[dict]:
    """Synthetic but believable production jobs across capable CNC machines."""
    # CNC machines make every product (see capabilities), so any job's part_no
    # is recomputable-compatible — but jobs are only ever created on CNC.
    out = []
    for machine in capable_machines:
        for slot in range(jobs_per_machine):
            target = rng.choice([420, 640, 850, 1200])
            produced = target if slot > 0 else int(target * 0.72)
            scrap = int(produced * 0.02)
            status = "RUNNING" if (machine == "CNC-03" and slot == 0) else (
                "QUEUED" if slot == 1 else "COMPLETED")
            out.append({
                "job_id": f"JB-{len(out) + 1:04d}",
                "part_no": rng.choice(PRODUCTS),
                "machine_id": machine,
                "target_qty": target,
                "produced_qty": produced if status != "QUEUED" else 0,
                "good_qty": (produced - scrap) if status != "QUEUED" else 0,
                "scrap_qty": scrap if status != "QUEUED" else 0,
                "status": status,
                "started_at": None,           # filled by seeder below
                "due_at": None,
                "priority": rng.choice([1, 2, 2, 3]),
            })
    return out


def seed(conn, *, db_label: str = "default") -> dict:
    """Create the schema and load the deterministic factory. Idempotent: resets first."""
    reset_schema(conn)

    telemetry_rng = _rng("telemetry")
    jobs_rng = _rng("jobs")
    history_rng = _rng("history")
    machines_rng = _rng("machines")

    manufacturers = {
        "CNC": [("DMG MORI", "DMU 50"), ("Haas", "VF-4SS"), ("Makino", "PS-63")],
        "PRESS": [("Schuler", "MS2-200"), ("Aida", "NST-80")],
        "ASSEMBLY": [("Bosch Rexroth", "MTS-15"), ("Fanuc", "M-20iD")],
        "PACKAGING": [("Bosch", "SVE2520"), ("Krones", "Modulfill")],
        "QUALITY": [("Zeiss", "O-SELECT"), ("Keyence", "IM-8000")],
    }

    # ── machines ──────────────────────────────────────────────────────────
    machine_rows = []
    for mid, name, mtype, line, x, y in MASTER_MACHINES:
        cyl, uph, cph, margin, scrap_cost = TYPE_ECONOMICS[mtype]
        installed = 2016 + machines_rng.randint(0, 8)
        catalog = manufacturers[mtype]
        make, model = catalog[machines_rng.randrange(len(catalog))]
        state = SNAPSHOT_STATES.get(mid, "HEALTHY")
        base_health = 100
        if state == "WARNING":
            base_health = 63
        elif state == "CRITICAL":
            base_health = 38
        elif state == "MAINTENANCE":
            base_health = 55
        machine_rows.append((
            mid, name, mtype, line, state, base_health,
            make, model, installed, float(x), float(y), 0.0,
            cyl, uph, cph, margin, scrap_cost,
        ))
    conn.executemany(
        "INSERT INTO machines(machine_id, name, machine_type, line, state, health_score,"
        " manufacturer, model, installed_year, x_m, y_m, z_m,"
        " ideal_cycle_time_s, output_per_hour, cost_per_hour_usd,"
        " contribution_per_unit_usd, scrap_cost_per_unit_usd)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        machine_rows,
    )

    # ── capabilities: which types can make which part numbers ────────────
    caps = []
    part_by_type = {
        "CNC": ["FA-1420", "FA-2410", "FA-3105", "FA-4020", "FA-5008"],
        "PRESS": ["FA-2410", "FA-5008"],
        "ASSEMBLY": ["FA-1420", "FA-3105"],
        "PACKAGING": ["FA-1420", "FA-2410", "FA-3105", "FA-4020", "FA-5008"],
        "QUALITY": [],
    }
    for mtype, part_nos in part_by_type.items():
        for pn in part_nos:
            caps.append((mtype, pn))
    conn.executemany("INSERT INTO capabilities(machine_type, part_no) VALUES (?,?)", caps)

    # ── spare parts ──────────────────────────────────────────────────────
    conn.executemany(
        "INSERT INTO spare_parts(part_id, name, category, compatible_types, stock_qty,"
        " reorder_point, unit_cost_usd, lead_time_days, supplier)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        SPARE_PARTS,
    )

    # ── telemetry: 24 h history per machine at 10-min ticks, CNC-03 scripted ──
    reading_rows = []
    tick_ts = [Clock.at_epoch().iso_at(-(TELEMETRY_TICKS - i) * TELEMETRY_TICK_MINUTES)
               for i in range(TELEMETRY_TICKS)]
    for mid, _, mtype, *_ in MASTER_MACHINES:
        vib0, temp0, rpm0, cur0, scrap0 = TYPE_BASELINES[mtype]
        offline = SNAPSHOT_STATES.get(mid) == "OFFLINE"
        for i, ts in enumerate(tick_ts):
            frac = i / (TELEMETRY_TICKS - 1)
            if mid == "CNC-03":
                # Deterministic eased ramp — the replayable flagship degradation.
                eased = frac * frac * (3 - 2 * frac)
                vib = 2.4 + eased * (5.0 - 2.4)
                temp = 62.0 + eased * (70.7 - 62.0)
                scrap = 0.8 + eased * 4.2
                rate = round(30.5 * (1 - 0.14 * eased), 2)
                if i == TELEMETRY_TICKS - 1:
                    vib, temp = 4.995, 70.72   # demo-verified endpoint values
            elif mid == "CNC-06":
                vib = vib0 + 0.35 * frac
                temp = temp0 + 1.8 * frac
                scrap = scrap0 + 0.5 * frac
                rate = round(30.5 * (1 - 0.03 * frac), 2)
            else:
                vib = vib0 + abs(telemetry_rng.uniform(-0.12, 0.12))
                temp = temp0 + telemetry_rng.uniform(-0.8, 0.8)
                scrap = max(0.0, scrap0 + telemetry_rng.uniform(-0.15, 0.15))
                rate = round(TYPE_ECONOMICS[mtype][1]
                             * telemetry_rng.uniform(0.93, 0.99), 2)
            reading_rows.append((
                mid, ts,
                round(vib, 3), round(temp, 2),
                round(rpm0 + telemetry_rng.uniform(-80, 80), 1) if rpm0 else None,
                round(cur0 + telemetry_rng.uniform(-0.6, 0.6), 2) if cur0 else None,
                round(TYPE_ECONOMICS[mtype][0] * telemetry_rng.uniform(0.98, 1.02), 2),
                rate if not offline else None,
                round(scrap, 2) if not offline else None,
            ))
        if offline:
            continue  # PKG-03 offline: no live readings beyond a flat history
    conn.executemany(
        "INSERT INTO sensor_readings(machine_id, ts, vibration_mm_s, bearing_temp_c,"
        " spindle_rpm, motor_current_a, cycle_time_s, production_rate_uph, defect_rate_pct)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        reading_rows,
    )

    # ── production jobs: over CNC machines (reroute-capable pool) ─────────
    cnc_machines = [m[0] for m in MASTER_MACHINES if m[2] == "CNC"]
    DUE_DAYS = 7
    jobs = _dag(cnc_machines, jobs_per_machine=2, due_days=DUE_DAYS, rng=jobs_rng)
    for job in jobs:
        if job["status"] == "RUNNING":
            job["started_at"] = Clock.at_epoch().iso_at(-240)
        elif job["status"] == "COMPLETED":
            job["started_at"] = Clock.at_epoch().iso_at(-2880)
        job["due_at"] = Clock.at_epoch().iso_at(DUE_DAYS * 24 * 60)
    conn.executemany(
        "INSERT INTO production_jobs(job_id, part_no, machine_id, target_qty, produced_qty,"
        " good_qty, scrap_qty, status, started_at, due_at, priority)"
        " VALUES (:job_id,:part_no,:machine_id,:target_qty,:produced_qty,:good_qty,"
        ":scrap_qty,:status,:started_at,:due_at,:priority)",
        jobs,
    )

    # ── maintenance history ──────────────────────────────────────────────
    history_rows = []
    for idx, (mid, issue, action, part, dt_h, cost) in enumerate(MAINTENANCE_SEEDS):
        days_ago = (idx * 37 + history_rng.randint(2, 11)) % 330 + 15
        event_date = Clock.at_epoch().iso_at(-days_ago * 24 * 60)[:10]
        history_rows.append((mid, event_date, issue, action, part, dt_h, cost))
    conn.executemany(
        "INSERT INTO maintenance_history(machine_id, event_date, issue, action, part_id,"
        " downtime_hours, cost_usd) VALUES (?,?,?,?,?,?,?)",
        history_rows,
    )

    # ── work orders (seeded examples only — no agent orders yet) ─────────
    wo_rows = [
        ("WO-0001", "PRS-03", "Hydraulic pressure drift", "Replace filter + seals",
         "IN_PROGRESS", "high", None, 480.0, "PLANNER"),
        ("WO-0002", "CNC-03", "Spindle bearing replacement (BRG-AX-17)",
         "Replace spindle front bearing", "OPEN", "critical",
         Clock.at_epoch().iso_at(3 * 24 * 60 + 60), 2100.0, "OPERATOR"),
        ("WO-0003", "PKG-03", "Case packer belt set replacement",
         "Replace belt set", "OPEN", "medium", None, 260.0, "PLANNER"),
        ("WO-0004", "CNC-06", "Spindle vibration trending up", "Inspection + regrease",
         "OPEN", "medium", Clock.at_epoch().iso_at(5 * 24 * 60), 180.0, "OPERATOR"),
    ]
    conn.executemany(
        "INSERT INTO work_orders(work_order_id, machine_id, issue, proposed_action, status,"
        " priority, scheduled_for, estimated_cost_usd, source, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(w[0], w[1], w[2], w[3], w[4], w[5], w[6], w[7], w[8], EPOCH.isoformat(
            sep=" ", timespec="seconds")) for w in wo_rows],
    )

    # ── downtime events (recent, reconcilable) ───────────────────────────
    dt_rows = [
        ("PRS-03", Clock.at_epoch().iso_at(-300), None, "Planned maintenance window", 1, 0.0),
        ("PKG-03", Clock.at_epoch().iso_at(-720), None, "Drive belt failure", 0, 0.0),
        ("CNC-03", Clock.at_epoch().iso_at(-1400),
         Clock.at_epoch().iso_at(-1362), "Coolant line clog", 0, 19.0),
    ]
    conn.executemany(
        "INSERT INTO downtime_events(machine_id, start_ts, end_ts, reason, planned,"
        " est_production_loss_units) VALUES (?,?,?,?,?,?)",
        dt_rows,
    )

    # ── scenario bookkeeping ─────────────────────────────────────────────
    set_state(conn, "clock", EPOCH.isoformat(sep=" ", timespec="seconds"))
    set_state(conn, "master_seed", MASTER_SEED)
    set_state(conn, "scenario", json.dumps({
        "name": "cnc03_bearing_degradation",
        "machine": "CNC-03",
        "part": "BRG-AX-17",
        "vibration_start": 2.4, "vibration_end": 5.0,
        "temp_start": 62.0, "temp_end": 70.7,
        "part_stock_before": 2, "part_reorder": 3,
    }))
    set_state(conn, "seeded_at_label", db_label)

    digest = audit_digest(conn)
    conn.execute("INSERT INTO seed_audit(seed, digest) VALUES (?,?)", (MASTER_SEED, digest))
    return {"machines": len(machine_rows), "telemetry_rows": len(reading_rows),
            "jobs": len(jobs), "parts": len(SPARE_PARTS),
            "history": len(history_rows), "work_orders": len(wo_rows),
            "downtime": len(dt_rows), "digest": digest}


def audit_digest(conn) -> str:
    """SHA-256 over canonical machine+telemetry+part content (determinism check)."""
    payload = []
    for table, cols in (
        ("machines", "machine_id,state,health_score"),
        ("spare_parts", "part_id,stock_qty"),
        ("sensor_readings", "machine_id,ts,vibration_mm_s,bearing_temp_c"),
        ("production_jobs", "job_id,machine_id,produced_qty,scrap_qty"),
    ):
        rows = conn.execute(f"SELECT {cols} FROM {table} ORDER BY 1, 2").fetchall()
        payload.append(f"{table}: " + ";".join(
            ",".join(str(v) for v in tuple(row)) for row in rows))
    return hashlib.sha256("\n".join(payload).encode()).hexdigest()
