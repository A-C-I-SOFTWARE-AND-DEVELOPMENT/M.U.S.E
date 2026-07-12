from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


external_evidence = _load(
    "achievement_external_evidence",
    ROOT / "dashboard" / "external_evidence.py",
)
plugin_api = _load("achievement_plugin_api_external", ROOT / "dashboard" / "plugin_api.py")


def _envelope(**overrides: object) -> dict[str, object]:
    envelope: dict[str, object] = {
        "version": 1,
        "kind": "mission.completed",
        "producer": "muse_universe",
        "mission_id": "mis_1",
        "source_type": "kanban",
        "source_id": "task_1",
        "mode": "real",
        "evidence_references": ["test:passed"],
        "provenance": {
            "realm_id": "rlm_local",
            "command_id": "cmd_complete",
            "occurred_at": "2026-07-12T12:00:00+00:00",
        },
    }
    envelope.update(overrides)
    return envelope


def test_external_evidence_is_deduplicated_and_returns_safe_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    accepted = external_evidence.record_external_evidence(_envelope())
    duplicate = external_evidence.record_external_evidence(_envelope())

    assert accepted["status"] == "accepted"
    assert duplicate == {**accepted, "status": "duplicate"}
    assert set(accepted) == {"status", "record_id", "dedupe_key"}
    records = external_evidence.list_external_evidence()
    assert len(records) == 1
    assert records[0]["mission_id"] == "mis_1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "simulation"},
        {"kind": "achievement.unlocked"},
        {"producer": "client"},
        {"evidence_references": []},
        {"scope": "admin"},
        {"provenance": {"realm_id": "rlm", "command_id": "cmd", "tools": ["shell"]}},
    ],
)
def test_external_evidence_rejects_malformed_or_authority_shaped_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with pytest.raises(ValueError):
        external_evidence.record_external_evidence(_envelope(**overrides))


def test_simulation_evidence_requires_explicit_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    receipt = external_evidence.record_external_evidence(
        _envelope(mode="simulation", simulation_label="simulation")
    )
    assert receipt["status"] == "accepted"


def test_external_evidence_never_mutates_unlock_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    state = tmp_path / "plugins" / "hermes-achievements" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"unlocks": {"existing": {"tier": "Gold"}}}))
    before = state.read_bytes()

    external_evidence.record_external_evidence(_envelope())

    assert state.read_bytes() == before


def test_evaluate_all_merges_external_records_even_from_warm_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    external_evidence.record_external_evidence(_envelope())
    cached = {
        "achievements": [],
        "aggregate": {"total_tool_calls": 0},
        "unlocked_count": 0,
        "discovered_count": 0,
        "secret_count": 0,
        "total_count": 0,
        "generated_at": int(time.time()),
    }
    plugin_api._SNAPSHOT_CACHE = cached
    plugin_api._SNAPSHOT_CACHE_AT = int(time.time())

    result = plugin_api.evaluate_all()

    assert result["external_record_count"] == 1
    assert result["external_records"][0]["mission_id"] == "mis_1"
    assert result["aggregate"] == {"total_tool_calls": 0}
    assert result["unlocked_count"] == 0
    assert "external_records" not in cached
