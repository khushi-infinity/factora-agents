"""Repository layer — the only module family that runs SQL for the world.

Quarterbacks nothing: it reads/writes rows; the service layer (simulation.py)
builds meaning on top. Future agent tools call the service layer, never these
functions directly and never the database.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def _rows(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


# ── machines ──────────────────────────────────────────────────────────────
def list_machines(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn.execute(
        "SELECT * FROM machines ORDER BY machine_id"))


def get_machine(conn: sqlite3.Connection, machine_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM machines WHERE machine_id = ?", (machine_id,)).fetchone()
    return dict(row) if row else None


def set_machine_state(conn: sqlite3.Connection, machine_id: str,
                      state: str, health_score: int | None) -> None:
    conn.execute(
        "UPDATE machines SET state = ?, health_score = ? WHERE machine_id = ?",
        (state, health_score, machine_id))


def machine_economics(conn: sqlite3.Connection, machine_id: str) -> dict | None:
    row = conn.execute(
        "SELECT ideal_cycle_time_s, output_per_hour, cost_per_hour_usd,"
        " contribution_per_unit_usd, scrap_cost_per_unit_usd FROM machines"
        " WHERE machine_id = ?", (machine_id,)).fetchone()
    return dict(row) if row else None


def types_compatible_with_part(conn: sqlite3.Connection, part_id: str) -> list[str]:
    row = conn.execute(
        "SELECT compatible_types FROM spare_parts WHERE part_id = ?", (part_id,)).fetchone()
    if not row:
        return []
    return [t.strip() for t in row["compatible_types"].split(";") if t.strip()]


# ── telemetry ─────────────────────────────────────────────────────────────
def telemetry_history(conn: sqlite3.Connection, machine_id: str,
                      limit: int = 144) -> list[dict]:
    return _rows(conn.execute(
        "SELECT * FROM sensor_readings WHERE machine_id = ? ORDER BY ts DESC LIMIT ?",
        (machine_id, limit)))


def latest_reading(conn: sqlite3.Connection, machine_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sensor_readings WHERE machine_id = ? ORDER BY ts DESC LIMIT 1",
        (machine_id,)).fetchone()
    return dict(row) if row else None


def insert_reading(conn: sqlite3.Connection, reading: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO sensor_readings(machine_id, ts, vibration_mm_s, bearing_temp_c,"
        " spindle_rpm, motor_current_a, cycle_time_s, production_rate_uph, defect_rate_pct)"
        " VALUES (:machine_id,:ts,:vibration_mm_s,:bearing_temp_c,:spindle_rpm,"
        ":motor_current_a,:cycle_time_s,:production_rate_uph,:defect_rate_pct)",
        reading)


def first_reading(conn: sqlite3.Connection, machine_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sensor_readings WHERE machine_id = ? ORDER BY ts ASC LIMIT 1",
        (machine_id,)).fetchone()
    return dict(row) if row else None


# ── production ────────────────────────────────────────────────────────────
def jobs_for_machine(conn: sqlite3.Connection, machine_id: str,
                     active_only: bool = False) -> list[dict]:
    extra = " AND status IN ('RUNNING','QUEUED','PAUSED')" if active_only else ""
    return _rows(conn.execute(
        f"SELECT * FROM production_jobs WHERE machine_id = ?{extra} ORDER BY job_id",
        (machine_id,)))


def get_job(conn: sqlite3.Connection, job_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM production_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def count_jobs(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM production_jobs").fetchone()[0])


def capable_machines_for_part(conn: sqlite3.Connection, part_no: str) -> list[str]:
    rows = conn.execute(
        "SELECT m.machine_id FROM capabilities c JOIN machines m ON m.machine_type = c.machine_type"
        " WHERE c.part_no = ? AND m.state != 'OFFLINE' ORDER BY m.machine_id",
        (part_no,)).fetchall()
    return [r["machine_id"] for r in rows]


# ── parts / history / work orders / downtime ──────────────────────────────
def get_spare_part(conn: sqlite3.Connection, part_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM spare_parts WHERE part_id = ?", (part_id,)).fetchone()
    return dict(row) if row else None


def list_spare_parts(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn.execute("SELECT * FROM spare_parts ORDER BY part_id"))


def adjust_stock(conn: sqlite3.Connection, part_id: str, delta: int) -> None:
    conn.execute(
        "UPDATE spare_parts SET stock_qty = stock_qty + ? WHERE part_id = ?",
        (delta, part_id))


def maintenance_for_machine(conn: sqlite3.Connection, machine_id: str) -> list[dict]:
    return _rows(conn.execute(
        "SELECT * FROM maintenance_history WHERE machine_id = ? ORDER BY event_date",
        (machine_id,)))


def work_orders_for_machine(conn: sqlite3.Connection, machine_id: str,
                            open_only: bool = False) -> list[dict]:
    extra = " AND status IN ('OPEN','ASSIGNED','IN_PROGRESS')" if open_only else ""
    return _rows(conn.execute(
        f"SELECT * FROM work_orders WHERE machine_id = ?{extra} ORDER BY work_order_id",
        (machine_id,)))


def insert_work_order(conn: sqlite3.Connection, wo: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO work_orders(work_order_id, machine_id, issue, proposed_action, status,"
        " priority, scheduled_for, estimated_cost_usd, source, created_at)"
        " VALUES (:work_order_id,:machine_id,:issue,:proposed_action,:status,:priority,"
        ":scheduled_for,:estimated_cost_usd,:source,:created_at)", wo)


def insert_downtime(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO downtime_events(machine_id, start_ts, end_ts, reason, planned,"
        " est_production_loss_units) VALUES (:machine_id,:start_ts,:end_ts,:reason,"
        ":planned,:est_production_loss_units)", event)


def list_downtime(conn: sqlite3.Connection, machine_id: str | None = None) -> list[dict]:
    if machine_id:
        return _rows(conn.execute(
            "SELECT * FROM downtime_events WHERE machine_id = ? ORDER BY start_ts",
            (machine_id,)))
    return _rows(conn.execute("SELECT * FROM downtime_events ORDER BY start_ts"))


# ── incidents / actions (schema from N1, scenario-populated) ──────────────
def insert_incident(conn: sqlite3.Connection, incident: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO incidents(incident_id, machine_id, type, severity, status, opened_at,"
        " resolved_at, summary, evidence, current_owner, recommended_action)"
        " VALUES (:incident_id,:machine_id,:type,:severity,:status,:opened_at,:resolved_at,"
        ":summary,:evidence,:current_owner,:recommended_action)", incident)


def update_incident(conn: sqlite3.Connection, incident_id: str,
                    updates: dict[str, Any]) -> None:
    if not updates:
        return
    cols = ", ".join(f"{key} = :{key}" for key in updates)
    conn.execute(f"UPDATE incidents SET {cols} WHERE incident_id = :incident_id",
                 {**updates, "incident_id": incident_id})


def get_incident(conn: sqlite3.Connection, incident_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
    return dict(row) if row else None


def list_incidents(conn: sqlite3.Connection, open_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM incidents"
    if open_only:
        sql += " WHERE status NOT IN ('RESOLVED','CLOSED')"
    sql += " ORDER BY opened_at"
    return _rows(conn.execute(sql))


def insert_action(conn: sqlite3.Connection, action: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO actions(action_id, incident_id, action_type, proposed_by, payload,"
        " risk_level, approval_required, approval_state, executed_at, verification_state,"
        " result) VALUES (:action_id,:incident_id,:action_type,:proposed_by,:payload,"
        ":risk_level,:approval_required,:approval_state,:executed_at,:verification_state,"
        ":result)", action)


def list_actions(conn: sqlite3.Connection, incident_id: str | None = None) -> list[dict]:
    if incident_id:
        return _rows(conn.execute(
            "SELECT * FROM actions WHERE incident_id = ? ORDER BY action_id", (incident_id,)))
    return _rows(conn.execute("SELECT * FROM actions ORDER BY action_id"))


def count_actions(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0])


def count_incidents(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0])


def count_maintenance(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM maintenance_history").fetchone()[0])


def count_work_orders(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0])


def count_telemetry(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0])


def evidence_of(incident: dict) -> list[dict]:
    try:
        return json.loads(incident.get("evidence") or "[]")
    except json.JSONDecodeError:
        return []
