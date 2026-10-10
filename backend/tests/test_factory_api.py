"""API contract tests for the N1 factory surface (every endpoint tested)."""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.world.simulation import reset_world_singleton


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_world_singleton()
    with TestClient(create_app()) as test_client:
        test_client.post("/api/demo/reset")     # deterministic start state per test
        yield test_client
    reset_world_singleton()




@pytest.fixture(autouse=True)
def temp_world_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test gets its own temp factory DB via the env var FactoryWorld reads."""
    handle, name = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    monkeypatch.setenv("FACTORA_DB_PATH", name)
    yield
    with contextlib.suppress(FileNotFoundError):
        os.unlink(name)


def test_factory_snapshot_shape(client: TestClient) -> None:
    body = client.get("/api/factory").json()

    assert body["machine_count"] >= 18
    assert body["clock"].startswith("2026-10-05 06:00")
    assert body["state_distribution"].get("WARNING", 0) >= 1   # seeded mid-ramp CNC-03
    assert isinstance(body["open_incidents"], list)


def test_machines_list(client: TestClient) -> None:
    machines = client.get("/api/machines").json()

    assert len(machines) >= 18
    ids = [m["machine_id"] for m in machines]
    assert "CNC-03" in ids
    assert all(m["state"] in {"HEALTHY", "WARNING", "CRITICAL", "MAINTENANCE", "OFFLINE"}
               for m in machines)


def test_machine_detail_includes_economics(client: TestClient) -> None:
    body = client.get("/api/machines/CNC-03").json()

    assert body["machine_type"] == "CNC"
    assert body["output_per_hour"] > 0
    assert body["cost_per_hour_usd"] > 0
    assert body["latest_telemetry"] is not None
    assert body["latest_telemetry"]["vibration_mm_s"] > 0


def test_machine_detail_404(client: TestClient) -> None:
    assert client.get("/api/machines/NOPE-99").status_code == 404


def test_machine_telemetry_ordering_and_limit(client: TestClient) -> None:
    body = client.get("/api/machines/CNC-03/telemetry", params={"limit": 5}).json()

    assert len(body) == 5
    timestamps = [r["ts"] for r in body]
    assert timestamps == sorted(timestamps), "oldest → newest ordering"


def test_machine_telemetry_404(client: TestClient) -> None:
    assert client.get("/api/machines/NOPE-99/telemetry").status_code == 404


def test_incidents_endpoint(client: TestClient) -> None:
    # Seeded world has no incidents yet; advance one tick to open the scenario one.
    client.post("/api/demo/advance", json={"minutes": 10})

    incidents = client.get("/api/incidents").json()
    assert len(incidents) >= 1
    incident = incidents[0]
    assert incident["machine_id"] == "CNC-03"
    assert incident["type"] == "BEARING_DEGRADATION"
    assert incident["status"] == "OPEN"


def test_demo_reset_is_deterministic(client: TestClient) -> None:
    first = client.post("/api/demo/reset").json()
    client.post("/api/demo/advance", json={"minutes": 30})
    second = client.post("/api/demo/reset").json()

    assert first["status"] == "reset"
    assert second["status"] == "reset"
    assert first["clock"] == second["clock"]
    assert first["machines"] == second["machines"]


def test_demo_advance_moves_clock_and_reports_state(client: TestClient) -> None:
    body = client.post("/api/demo/advance", json={"minutes": 60}).json()

    assert body["clock"].endswith("07:00:00")
    assert body["emitted_readings"] >= 20          # per-tick rows across live machines
    assert body["cnc03_state"] in {"HEALTHY", "WARNING", "CRITICAL", "MAINTENANCE"}
    assert isinstance(body["open_incidents"], int)


def test_demo_advance_validates_input(client: TestClient) -> None:
    assert client.post("/api/demo/advance", json={"minutes": 0}).status_code == 422
    assert client.post("/api/demo/advance", json={"minutes": -5}).status_code == 422
    assert client.post("/api/demo/advance", json={"minutes": 2000}).status_code == 422


def test_openapi_advertises_factory_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    for path in ("/api/factory", "/api/machines", "/api/machines/{machine_id}",
                 "/api/machines/{machine_id}/telemetry", "/api/machines/{machine_id}/context",
                 "/api/machines/{machine_id}/maintenance", "/api/machines/{machine_id}/work-orders",
                 "/api/machines/{machine_id}/production", "/api/factory/lines",
                 "/api/incidents", "/api/demo/reset", "/api/demo/advance"):
        assert path in paths, f"missing route in OpenAPI: {path}"


def test_factory_lines_groups_cnc(client: TestClient) -> None:
    lines = client.get("/api/factory/lines").json()

    by_line = {row["line"]: row for row in lines}
    assert set(by_line) == {"CNC_LINE", "PRESS_LINE", "ASSEMBLY_LINE",
                            "PACKAGING_LINE", "QUALITY_LINE"}
    assert by_line["CNC_LINE"]["machine_count"] == 8
    assert "CNC-03" in by_line["CNC_LINE"]["machine_ids"]


def test_machine_maintenance_history(client: TestClient) -> None:
    rows = client.get("/api/machines/CNC-03/maintenance").json()

    assert len(rows) >= 2
    parts_used = [r["part_id"] for r in rows]
    assert "BRG-AX-17" in parts_used
    assert all(r["machine_id"] == "CNC-03" for r in rows)


def test_machine_maintenance_404(client: TestClient) -> None:
    assert client.get("/api/machines/NOPE-99/maintenance").status_code == 404


def test_machine_work_orders(client: TestClient) -> None:
    rows = client.get("/api/machines/CNC-03/work-orders").json()

    assert any(r["work_order_id"] == "WO-0002" for r in rows)
    assert all(r["machine_id"] == "CNC-03" for r in rows)


def test_machine_production_jobs(client: TestClient) -> None:
    rows = client.get("/api/machines/CNC-03/production").json()

    assert len(rows) >= 1
    assert any(r["status"] == "RUNNING" for r in rows)
    assert all(r["good_qty"] + r["scrap_qty"] == r["produced_qty"] for r in rows
               if r["status"] != "QUEUED")


def test_machine_context_full_payload(client: TestClient) -> None:
    body = client.get("/api/machines/CNC-03/context").json()

    assert body["machine"]["machine_id"] == "CNC-03"
    assert len(body["telemetry"]) >= 20
    assert body["telemetry"][0]["ts"] <= body["telemetry"][-1]["ts"]  # oldest → newest
    assert any(m["part_id"] == "BRG-AX-17" for m in body["maintenance"])
    assert any(j["machine_id"] == "CNC-03" for j in body["production"])
    assert body["economics_note"] == "Synthetic demo economics"
    assert body["machine"]["cost_per_hour_usd"] > 0


def test_machine_context_404(client: TestClient) -> None:
    assert client.get("/api/machines/NOPE-99/context").status_code == 404


def test_machine_context_incidents_after_advance(client: TestClient) -> None:
    client.post("/api/demo/advance", json={"minutes": 10})

    body = client.get("/api/machines/CNC-03/context").json()

    assert len(body["incidents"]) >= 1
    assert body["incidents"][0]["type"] == "BEARING_DEGRADATION"
