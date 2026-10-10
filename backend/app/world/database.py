"""SQLite access for FactoryWorld — plain sqlite3, no ORM.

Repository modules own all SQL; nothing outside `app/world/` executes SQL
against this database (future agents get the service layer, never the DB).
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from pathlib import Path

from . import models

# Default location: the fresh repo root /data/factory.db (gitignored).
DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "factory.db"

_conn: sqlite3.Connection | None = None


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (once per process) the world database with FK enforcement on."""
    global _conn
    if _conn is None:
        env_path = os.environ.get("FACTORA_DB_PATH")
        path = Path(db_path or env_path or DEFAULT_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(path, isolation_level=None)  # autocommit; explicit txns below
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
    return _conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(models.DDL)
    set_state(conn, "schema_version", models.SCHEMA_VERSION)


def reset_schema(conn: sqlite3.Connection) -> None:
    """Drop every table then recreate — used by reset_world()/seed script."""
    tables = [
        "seed_audit", "actions", "incidents", "downtime_events", "work_orders",
        "maintenance_history", "spare_parts", "production_jobs", "sensor_readings",
        "capabilities", "machines", "world_state",
    ]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    create_schema(conn)


def reset_singleton() -> None:
    """Close and drop the cached process connection (used by test fixtures)."""
    global _conn
    if _conn is not None:
        with contextlib.suppress(Exception):   # best-effort teardown
            _conn.close()
    _conn = None


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM world_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO world_state(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
