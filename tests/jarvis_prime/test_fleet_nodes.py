"""Tests for the Nero-Fleet telemetry overlay."""

from __future__ import annotations

from hermes_cli.jarvis_prime.fleet.registry import FleetRegistry, reset_registry
from hermes_cli.jarvis_prime.fleet.solar_map import solar_system_view, transit_from_job_stage


def setup_function() -> None:
    reset_registry()


def test_registry_has_four_command_nodes() -> None:
    reg = FleetRegistry()
    snap = reg.snapshot()
    kinds = {n["kind"] for n in snap["nodes"]}
    assert kinds >= {"admiralty", "flagship", "tactical", "intelligence"}


def test_register_and_release_ship() -> None:
    reg = FleetRegistry()
    reg.register_ship("ship-a", "Worker A", job_id="job-1", task_class="build")
    snap = reg.snapshot()
    assert snap["active_ships"] == 1
    reg.release_ship("ship-a")
    assert reg.snapshot()["active_ships"] == 0


def test_job_stage_creates_transit_mapping() -> None:
    t = transit_from_job_stage("job-abc", "worker", task_class="build", latency_ms=120)
    assert t.job_id == "job-abc"
    assert t.dest_id == "planet-worker"
    assert t.latency_ms == 120
    assert 0.0 <= t.progress <= 1.0


def test_solar_system_view_has_sun_and_planets() -> None:
    reg = FleetRegistry()
    view = solar_system_view(reg.snapshot())
    assert view["skin"] == "nero_solar"
    roles = {b["role"] for b in view["bodies"]}
    assert "sun" in roles
    assert "planet" in roles
    sun = next(b for b in view["bodies"] if b["role"] == "sun")
    assert sun["id"] == "sun-nero"


def test_record_job_stage_releases_on_terminal() -> None:
    reg = FleetRegistry()
    reg.record_job_stage("job-x", "worker", task_class="review")
    assert reg.snapshot()["active_ships"] == 1
    reg.record_job_stage("job-x", "done")
    assert reg.snapshot()["active_ships"] == 0
