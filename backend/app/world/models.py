"""SQLite schema for FactoryWorld — plain DDL, no ORM.

Conventions:
  * ids are TEXT codes (CNC-03, BRG-AX-17, WO-0001);
  * timestamps are naive plant-local ISO strings — deterministic by construction;
  * `economics` carries per-machine synthetic/demo cost parameters, clearly
    labelled as demo economics, never industry benchmarks;
  * `world_state` is a key/value table holding the simulation clock + seed info;
  * `incidents` and `actions` exist from N1 (schema-complete) but are only
    populated by deterministic scenario logic — agents come at N3.
"""

from __future__ import annotations

SCHEMA_VERSION = "n1"

DDL = """
CREATE TABLE IF NOT EXISTS world_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machines (
    machine_id     TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    machine_type   TEXT NOT NULL,          -- CNC / PRESS / ASSEMBLY / PACKAGING / QUALITY
    line           TEXT NOT NULL,          -- CNC_LINE / PRESS_LINE / ...
    state          TEXT NOT NULL CHECK (state IN
        ('HEALTHY','WARNING','CRITICAL','MAINTENANCE','OFFLINE')),
    health_score   INTEGER,               -- 0-100; NULL for OFFLINE
    manufacturer   TEXT,
    model          TEXT,
    installed_year INTEGER,
    x_m REAL NOT NULL, y_m REAL NOT NULL, z_m REAL NOT NULL,   -- twin placement
    ideal_cycle_time_s REAL NOT NULL,       -- drives production math
    output_per_hour     REAL NOT NULL,      -- demo economics
    cost_per_hour_usd   REAL NOT NULL,      -- demo economics
    contribution_per_unit_usd REAL NOT NULL,-- demo economics (margin per good unit)
    scrap_cost_per_unit_usd   REAL NOT NULL -- demo economics
);

CREATE TABLE IF NOT EXISTS capabilities (
    machine_type  TEXT NOT NULL,
    part_no       TEXT NOT NULL,            -- product part number the type can make
    PRIMARY KEY (machine_type, part_no)
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id  TEXT NOT NULL REFERENCES machines(machine_id),
    ts          TEXT NOT NULL,              -- ISO plant-local
    vibration_mm_s     REAL NOT NULL,
    bearing_temp_c     REAL NOT NULL,
    spindle_rpm        REAL,
    motor_current_a    REAL,
    cycle_time_s       REAL,
    production_rate_uph REAL,               -- observed output rate
    defect_rate_pct    REAL
);
CREATE INDEX IF NOT EXISTS idx_readings_machine_ts ON sensor_readings(machine_id, ts);

CREATE TABLE IF NOT EXISTS production_jobs (
    job_id        TEXT PRIMARY KEY,         -- JB-0001
    part_no       TEXT NOT NULL,
    machine_id    TEXT NOT NULL REFERENCES machines(machine_id),
    target_qty    INTEGER NOT NULL,
    produced_qty  INTEGER NOT NULL,
    good_qty      INTEGER NOT NULL,
    scrap_qty     INTEGER NOT NULL,
    status        TEXT NOT NULL CHECK (status IN
        ('QUEUED','RUNNING','PAUSED','COMPLETED','CANCELLED')),
    started_at    TEXT,                     -- NULL while QUEUED
    due_at        TEXT,
    priority      INTEGER NOT NULL DEFAULT 2   -- 1 (highest) .. 4
);
CREATE INDEX IF NOT EXISTS idx_jobs_machine ON production_jobs(machine_id);

CREATE TABLE IF NOT EXISTS maintenance_history (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id    TEXT NOT NULL REFERENCES machines(machine_id),
    event_date    TEXT NOT NULL,
    issue         TEXT NOT NULL,
    action        TEXT NOT NULL,
    part_id       TEXT REFERENCES spare_parts(part_id),
    downtime_hours REAL NOT NULL DEFAULT 0,
    cost_usd      REAL
);

CREATE TABLE IF NOT EXISTS spare_parts (
    part_id       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    compatible_types TEXT NOT NULL,         -- ';'-separated machine types
    stock_qty     INTEGER NOT NULL CHECK (stock_qty >= 0),
    reorder_point INTEGER NOT NULL,
    unit_cost_usd REAL NOT NULL,
    lead_time_days INTEGER NOT NULL,
    supplier      TEXT
);

CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id TEXT PRIMARY KEY,
    machine_id    TEXT NOT NULL REFERENCES machines(machine_id),
    issue         TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN
        ('OPEN','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED')),
    priority      TEXT NOT NULL CHECK (priority IN ('low','medium','high','critical')),
    scheduled_for TEXT,
    estimated_cost_usd REAL,
    source        TEXT NOT NULL,            -- OPERATOR / PLANNER / SCENARIO
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downtime_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id   TEXT NOT NULL REFERENCES machines(machine_id),
    start_ts     TEXT NOT NULL,
    end_ts       TEXT,                      -- NULL = ongoing
    reason       TEXT NOT NULL,
    planned      INTEGER NOT NULL,          -- 0/1
    est_production_loss_units REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id   TEXT PRIMARY KEY,
    machine_id    TEXT NOT NULL REFERENCES machines(machine_id),
    type          TEXT NOT NULL,            -- e.g. BEARING_DEGRADATION
    severity      TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    status        TEXT NOT NULL CHECK (status IN
        ('OPEN','INVESTIGATING','ACTION_PROPOSED','RESOLVING','RESOLVED','CLOSED')),
    opened_at     TEXT NOT NULL,
    resolved_at   TEXT,
    summary       TEXT NOT NULL,
    evidence      TEXT,                     -- JSON array of evidence refs
    current_owner TEXT,                     -- agent id later; 'SCENARIO' at N1
    recommended_action TEXT
);

CREATE TABLE IF NOT EXISTS actions (
    action_id    TEXT PRIMARY KEY,
    incident_id  TEXT REFERENCES incidents(incident_id),
    action_type  TEXT NOT NULL,
    proposed_by  TEXT NOT NULL,
    payload      TEXT,                      -- JSON
    risk_level   TEXT NOT NULL CHECK (risk_level IN ('low','medium','high')),
    approval_required INTEGER NOT NULL DEFAULT 0,
    approval_state    TEXT,                 -- PENDING / APPROVED / REJECTED
    executed_at  TEXT,
    verification_state TEXT,                -- PENDING / PASSED / FAILED
    result       TEXT
);

CREATE TABLE IF NOT EXISTS seed_audit (
    seed   TEXT NOT NULL,
    digest TEXT NOT NULL                    -- sha256 over canonical seeded content
);
"""
