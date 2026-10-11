"""Agent API tests (N3): advance triggers the watcher, runs are queryable.

The suite pins OPENROUTER_API_KEY to empty in conftest, so every run here uses
the deterministic offline model — no network, no key, reproducible.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _reset(client: TestClient) -> None:
    assert client.post("/api/demo/reset").status_code == 200


def test_agent_status_reports_the_real_model_mode(client: TestClient) -> None:
    body = client.get("/api/agents/status").json()

    assert body["mode"] == "DETERMINISTIC TEST MODEL"
    assert body["model_provider"] == "deterministic"
    assert body["observability"] in {"disabled", "error"}
    assert "CREATE_URGENT_WORK_ORDER" in body["autonomous_actions"]
    assert "PLACE_IN_MAINTENANCE" in body["autonomous_actions"]


def test_no_runs_after_a_reset(client: TestClient) -> None:
    _reset(client)
    assert client.get("/api/agents/runs").json() == []


def test_advance_triggers_the_watcher_and_a_run(client: TestClient) -> None:
    _reset(client)

    body = client.post("/api/demo/advance", json={"minutes": 30}).json()

    assert body["watcher"] == "escalated"
    assert len(body["agent_runs"]) == 1
    assert body["cnc03_state"] == "MAINTENANCE"

    run = body["agent_runs"][0]
    assert run["status"] == "VERIFIED"
    assert run["incident_id"] == "INC-20261005-001"
    assert run["machine_id"] == "CNC-03"

    incidents = client.get("/api/incidents").json()
    assert incidents[0]["status"] == "RESOLVING"


def test_advance_can_skip_agents_for_a_pure_world_check(client: TestClient) -> None:
    _reset(client)

    body = client.post("/api/demo/advance",
                       json={"minutes": 30, "trigger_agents": False}).json()

    assert body["watcher"] == "quiet"
    assert body["agent_runs"] == []
    assert body["cnc03_state"] == "CRITICAL"
    assert client.get("/api/agents/runs").json() == []


def test_recovery_scenario_runs_and_still_verifies(client: TestClient) -> None:
    _reset(client)

    body = client.post("/api/demo/advance",
                       json={"minutes": 30, "fail_first_work_order": True}).json()

    run = body["agent_runs"][0]
    assert run["fail_first_work_order"] is True
    assert run["status"] == "VERIFIED"

    detail = client.get(f"/api/agents/runs/{run['run_id']}").json()
    summaries = [step["summary"] for step in detail["steps"]]
    assert any(s.startswith("CREATE_URGENT_WORK_ORDER FAILED") for s in summaries)
    assert any("ACTING → RECOVERING" in s for s in summaries)
    assert any("VERIFYING → VERIFIED" in s for s in summaries)


def test_run_detail_lists_ordered_steps(client: TestClient) -> None:
    _reset(client)
    client.post("/api/demo/advance", json={"minutes": 30})

    run_id = client.get("/api/agents/runs").json()[0]["run_id"]
    detail = client.get(f"/api/agents/runs/{run_id}").json()

    assert detail["run_id"] == run_id
    assert detail["steps"], "a verified run must have steps"
    assert [s["sequence"] for s in detail["steps"]] == list(
        range(1, len(detail["steps"]) + 1))
    tool_steps = [s for s in detail["steps"] if s["type"] == "TOOL"]
    assert all(step["tool_name"] for step in tool_steps)
    assert all(step["output"] is not None for step in tool_steps)


def test_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/agents/runs/RUN-NOPE-9999").status_code == 404


def test_manual_run_is_quiet_on_a_healthy_world(client: TestClient) -> None:
    _reset(client)

    body = client.post("/api/agents/run").json()

    assert body["escalations"] == 0
    assert body["runs"] == []
    assert "nothing to do" in body["note"]


def test_manual_run_responds_after_the_world_goes_critical(client: TestClient) -> None:
    _reset(client)
    client.post("/api/demo/advance", json={"minutes": 30, "trigger_agents": False})

    body = client.post("/api/agents/run").json()

    assert body["escalations"] == 1
    assert body["runs"][0]["status"] == "VERIFIED"


def test_openapi_advertises_the_agent_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    for path in ("/api/agents/status", "/api/agents/runs",
                 "/api/agents/runs/{run_id}", "/api/agents/run"):
        assert path in paths, f"missing route in OpenAPI: {path}"
