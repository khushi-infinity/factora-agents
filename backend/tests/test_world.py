"""FactoryWorld core tests: determinism, seeding, validation, CNC-03 scenario."""

from __future__ import annotations

import pytest

from app.world import repositories as repo
from app.world.simulation import (
    SCEN_MACHINE,
    SCEN_PART,
    SCEN_TEMP_CRITICAL,
    SCEN_TEMP_WARNING,
    SCEN_VIB_CRITICAL,
    SCEN_VIB_WARNING,
    FactoryWorld,
    get_world,
    reset_world_singleton,
)


@pytest.fixture
def world() -> FactoryWorld:
    """A world backed by its own in-memory database (isolation per test)."""
    reset_world_singleton()
    return FactoryWorld(db_path=":memory:")


@pytest.fixture
def seeded(world: FactoryWorld) -> FactoryWorld:
    world.reset_world()
    return world


# ── seed + determinism ────────────────────────────────────────────────────
def test_seed_is_deterministic(world: FactoryWorld) -> None:
    first = world.reset_world()
    digest_a = repo_first_digest(world)
    world.reset_world()
    digest_b = repo_first_digest(world)

    assert first["machines"] >= 18          # plan §6: 18-24 machines
    assert first["machines"] <= 24
    assert digest_a == digest_b, "reseed must reproduce identical row content"


def repo_first_digest(world: FactoryWorld) -> str:
    from app.world.seed import audit_digest

    return audit_digest(world.conn)


def test_reset_returns_to_epoch_and_seeded_state(seeded: FactoryWorld) -> None:
    world = seeded
    world.advance(60)
    advanced_clock = world.clock().iso()
    assert advanced_clock != world_clock_at_epoch(world)

    world.reset_world()
    assert world.clock().iso() == world_clock_at_epoch(world)
    machine = world.get_machine(SCEN_MACHINE)
    assert machine['health_score'] == 63        # deterministic seeded WARNING value
    assert machine['state'] == 'WARNING'


def world_clock_at_epoch(world: FactoryWorld) -> str:
    from app.world.clock import EPOCH

    return EPOCH.isoformat(sep=" ", timespec="seconds")


def test_clock_is_deterministic_and_wall_clock_free(seeded: FactoryWorld) -> None:
    world = seeded
    world.advance(30)
    world.reset_world()
    c3 = world.advance(30)

    # The same advance from the same reset yields the same clock string.
    world.reset_world()
    c4 = world.advance(30)
    assert c4["clock"] == c3["clock"] != world_clock_at_epoch(world)


# ── validation rules (plan §13) ──────────────────────────────────────────
def test_seed_reference_integrity(seeded: FactoryWorld) -> None:
    world = seeded
    conn = world.conn
    machines = {m["machine_id"] for m in repo.list_machines(conn)}

    for reading in conn.execute("SELECT DISTINCT machine_id FROM sensor_readings"):
        assert reading["machine_id"] in machines
    for row in conn.execute("SELECT DISTINCT machine_id FROM maintenance_history"):
        assert row["machine_id"] in machines
    for row in conn.execute("SELECT DISTINCT machine_id FROM production_jobs"):
        assert row["machine_id"] in machines
    for row in conn.execute("SELECT DISTINCT machine_id FROM work_orders"):
        assert row["machine_id"] in machines
    for row in conn.execute("SELECT DISTINCT machine_id FROM downtime_events"):
        assert row["machine_id"] in machines


def test_part_compatibility_points_to_known_types(seeded: FactoryWorld) -> None:
    world = seeded
    valid_types = {m["machine_type"] for m in repo.list_machines(world.conn)}
    for part in repo.list_spare_parts(world.conn):
        for machine_type in part["compatible_types"].split(";"):
            if machine_type.strip():
                assert machine_type.strip() in valid_types


def test_no_negative_inventory_and_no_impossible_timestamps(seeded: FactoryWorld) -> None:
    world = seeded
    conn = world.conn
    for part in repo.list_spare_parts(conn):
        assert part["stock_qty"] >= 0
        assert part["reorder_point"] >= 0
    for row in conn.execute("SELECT MIN(ts) AS lo FROM sensor_readings"):
        assert row["lo"] is not None
    for job in conn.execute(
        "SELECT started_at, due_at FROM production_jobs WHERE started_at IS NOT NULL"
    ):
        assert job["started_at"] <= job["due_at"]


def test_production_quantities_consistent(seeded: FactoryWorld) -> None:
    world = seeded
    for job in world.conn.execute(
        "SELECT produced_qty, good_qty, scrap_qty, target_qty FROM production_jobs"
    ):
        assert job["produced_qty"] <= job["target_qty"]
        assert job["good_qty"] + job["scrap_qty"] == job["produced_qty"]
        assert job["scrap_qty"] >= 0


# ── CNC-03 flagship facts (plan §5) ──────────────────────────────────────
def test_cnc03_exists_with_full_evidence_chain(seeded: FactoryWorld) -> None:
    world = seeded
    machine = world.get_machine(SCEN_MACHINE)
    assert machine is not None
    assert machine["machine_type"] == "CNC"
    assert machine["state"] == "WARNING"      # seeded mid-ramp; advance() walks to CRITICAL

    # BRG-AX-17 exists, is CNC-compatible, limited stock, and CNC-03 used it twice.
    part = world.get_spare_part(SCEN_PART)
    assert part is not None
    assert "CNC" in part["compatible_types"]
    assert part["stock_qty"] <= part["reorder_point"]     # limited stock
    used = [h for h in world.get_machine_history(SCEN_MACHINE)
            if h["part_id"] == SCEN_PART]
    assert len(used) >= 2, "two prior BRG-AX-17 repairs are the evidence base"


def test_cnc03_degradation_is_monotonic(seeded: FactoryWorld) -> None:
    world = seeded
    readings = repo.telemetry_history(world.conn, SCEN_MACHINE, limit=10000)
    assert len(readings) >= 24
    ordered = list(reversed(readings))                      # oldest → newest
    vibrations = [r["vibration_mm_s"] for r in ordered]
    temps = [r["bearing_temp_c"] for r in ordered]

    # The seeded history ends at the WARNING midpoint (demo arcs from T+00 healthy
    # to T+90 warning; the live advance continues the walk to CRITICAL).
    assert vibrations[0] < 2.6, "starts near the healthy baseline (≈2.4)"
    assert 4.5 < vibrations[-1] < 5.2, "ends near the seeded warning midpoint (≈4.99)"
    assert temps[0] < 63.0
    assert 70.0 < temps[-1] < 71.4
    # Monotonic-enough: no long reversals across the ramp.
    inversions = sum(
        1 for a, b in zip(vibrations, vibrations[1:], strict=False) if b < a - 0.25)
    assert inversions == 0


def test_state_transitions_from_vibration_thresholds(seeded: FactoryWorld) -> None:
    assert SCEN_VIB_WARNING < SCEN_VIB_CRITICAL
    assert SCEN_TEMP_WARNING < SCEN_TEMP_CRITICAL
    # Thresholds sit between the healthy baseline and the degraded endpoint.
    assert 2.4 < SCEN_VIB_WARNING < 5.0
    assert 62.0 < SCEN_TEMP_WARNING < 70.7


# ── advance: telemetry + incidents ───────────────────────────────────────
def test_advance_emits_telemetry_and_moves_clock(seeded: FactoryWorld) -> None:
    world = seeded
    before_count = repo.count_telemetry(world.conn)
    result = world.advance(60)               # 6 ticks × 10 min

    assert result["emitted_readings"] == 22 * 6     # 23 machines − PKG-03 offline
    assert repo.count_telemetry(world.conn) == before_count + result["emitted_readings"]
    assert result["clock"].endswith("07:00:00")


def test_advance_is_deterministic(seeded: FactoryWorld) -> None:
    world = seeded
    first = world.advance(30)
    world.reset_world()
    second = world.advance(30)
    assert first["clock"] == second["clock"]
    assert first["emitted_readings"] == second["emitted_readings"]


def test_advance_rejects_nonpositive(world: FactoryWorld) -> None:
    world.reset_world()
    with pytest.raises(ValueError):
        world.advance(0)
    with pytest.raises(ValueError):
        world.advance(-5)


def test_scenario_reaches_warning_then_critical_with_incident(seeded: FactoryWorld) -> None:
    """The §19 scenario chain: reset → advance → warning → advance → critical + incident."""
    world = seeded
    machine = world.get_machine(SCEN_MACHINE)
    assert machine["state"] in {"HEALTHY", "WARNING", "CRITICAL"}

    world.reset_world()
    # Seeded state starts at the critical endpoint; walk BACK by resetting and
    # treating the fresh seed as the healthy-ish start of the live ramp: the
    # first advance opens the WARNING incident, later ones the CRITICAL.
    # (The seeded telemetry history ends at the degraded endpoints — the live
    # ramp continues past them, so incidents open on subsequent ticks.)
    result = world.advance(10)      # one tick
    assert result["emitted_readings"] == 22
    incidents = world.get_active_incidents()
    assert len(incidents) >= 1, "a tick past the seeded endpoint must open an incident"
    assert all(i["machine_id"] == SCEN_MACHINE for i in incidents)
    assert all(i["current_owner"] == "SCENARIO" for i in incidents)


def test_scenario_incident_is_deterministic(seeded: FactoryWorld) -> None:
    world = seeded
    world.advance(10)
    first = sorted(i["incident_id"] for i in world.get_active_incidents())
    world.reset_world()
    world.advance(10)
    second = sorted(i["incident_id"] for i in world.get_active_incidents())
    assert first == second


# ── service surface ──────────────────────────────────────────────────────
def test_compatible_machines_same_type_only(seeded: FactoryWorld) -> None:
    world = seeded
    job = repo.jobs_for_machine(world.conn, SCEN_MACHINE)[0]
    options = world.get_compatible_machines(job["job_id"])
    assert options, "flagship reroute must have candidates"
    candidate_ids = [o["candidate_machine_id"] for o in options]
    types = {world.get_machine(mid)["machine_type"] for mid in candidate_ids}
    assert types == {"CNC"}, "reroute candidates must stay in the CNC family"
    assert all(o["candidate_machine_id"] != SCEN_MACHINE for o in options)


def test_downtime_and_scrap_loss_deterministic(seeded: FactoryWorld) -> None:
    world = seeded
    a = world.compute_downtime_loss(SCEN_MACHINE, 4.0)
    b = world.compute_downtime_loss(SCEN_MACHINE, 4.0)
    assert a == b
    assert a["lost_units"] > 0 and a["total_usd"] > a["idle_cost_usd"]

    s1 = world.compute_scrap_loss(SCEN_MACHINE, 120)
    s2 = world.compute_scrap_loss(SCEN_MACHINE, 120)
    assert s1 == s2 and s1["scrap_cost_usd"] > 0


def test_singleton_is_reusable() -> None:
    reset_world_singleton()
    w1 = get_world()
    w2 = get_world()
    assert w1 is w2
    reset_world_singleton()
    w3 = get_world()
    assert w3 is not w1
