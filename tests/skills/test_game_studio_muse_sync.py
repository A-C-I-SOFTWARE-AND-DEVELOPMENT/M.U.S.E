"""Drift + contract tests for the slice ↔ muse sync.

``slice-manifest.json`` is what muse reads as the game's element catalog; these
tests keep it byte-honest against the actual Godot project, and prove the sync
script's mission envelope satisfies the real ``AchievementBridge`` contract
(simulation mode, labeled evidence, adapter reference validation).
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from plugins.muse_universe.achievements import AchievementBridge

REPO = Path(__file__).resolve().parents[2]
SLICE = REPO / "skills" / "creative" / "game-studio" / "reference-slice"
SCRIPTS = REPO / "skills" / "creative" / "game-studio" / "scripts"
MANIFEST = json.loads((SLICE / "slice-manifest.json").read_text(encoding="utf-8"))


def _load_sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_slice_to_muse", SCRIPTS / "sync_slice_to_muse.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Manifest ↔ project drift
# ---------------------------------------------------------------------------


def test_manifest_files_exist():
    elements = MANIFEST["elements"]
    for rel in (
        *elements["scenes"],
        *elements["scripts"],
        *elements["audio"],
        elements["hero_prop_slot"],
    ):
        assert (SLICE / rel).is_file(), f"manifest names missing file {rel}"


def test_manifest_states_match_game_script():
    game = (SLICE / "scripts" / "game.gd").read_text(encoding="utf-8")
    enum_match = re.search(r"enum State \{ ([^}]+) \}", game)
    assert enum_match, "game.gd must declare the State enum"
    states = [part.strip() for part in enum_match.group(1).split(",") if part.strip()]
    assert states == MANIFEST["elements"]["states"]


def test_manifest_collectible_count_matches_main_scene():
    main = (SLICE / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    placed = main.count('instance=ExtResource("3_collectible")')
    assert placed == MANIFEST["elements"]["collectibles"]


def test_manifest_input_actions_exist_in_project():
    project = (SLICE / "project.godot").read_text(encoding="utf-8")
    for action in MANIFEST["elements"]["input_actions"]:
        assert f"{action}=" in project, f"input action {action} missing"


def test_manifest_hud_nodes_exist():
    main = (SLICE / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    for node in MANIFEST["elements"]["hud"]:
        assert f'name="{node}"' in main, f"HUD node {node} missing"


def test_manifest_graphics_flags_are_live():
    main = (SLICE / "scenes" / "Main.tscn").read_text(encoding="utf-8")
    project = (SLICE / "project.godot").read_text(encoding="utf-8")
    for flag in MANIFEST["graphics"]["environment"]:
        assert f"{flag} = true" in main, f"environment flag {flag} not enabled"
    for line in MANIFEST["graphics"]["project_rendering"]:
        assert line in project, f"project rendering setting {line} missing"
    for piece in MANIFEST["graphics"]["set_pieces"]:
        assert f'name="{piece}"' in main, f"set piece {piece} missing"


def test_manifest_export_matches_preset():
    presets = (SLICE / "export_presets.cfg").read_text(encoding="utf-8")
    assert f'name="{MANIFEST["export"]["preset"]}"' in presets
    assert f'export_path="{MANIFEST["export"]["artifact"]}"' in presets


def test_manifest_muse_block_is_simulation_labeled():
    muse = MANIFEST["muse"]
    assert muse["mode"] == "simulation"
    assert muse["evidence_label"] == "simulation"
    assert muse["realm_id"]
    assert muse["source_type"] == "game_studio_slice"


# ---------------------------------------------------------------------------
# Mission envelope ↔ AchievementBridge contract
# ---------------------------------------------------------------------------


class RecordingAdapter:
    def __init__(self) -> None:
        self.envelopes: list[dict] = []

    def record(self, evidence: dict) -> dict:
        self.envelopes.append(evidence)
        return {
            "status": "accepted",
            "record_id": "external_test",
            "dedupe_key": "k" * 64,
        }


@pytest.fixture()
def artifact(tmp_path: Path) -> Path:
    path = tmp_path / "slice.x86_64"
    path.write_bytes(b"not-a-real-elf but a non-empty artifact")
    return path


def test_build_mission_fails_closed_without_artifact(tmp_path: Path):
    sync = _load_sync_module()
    with pytest.raises(FileNotFoundError):
        sync.build_mission(MANIFEST, tmp_path / "missing.x86_64")


def test_mission_produces_simulation_outbox(artifact: Path):
    sync = _load_sync_module()
    mission = sync.build_mission(MANIFEST, artifact)
    adapter = RecordingAdapter()
    bridge = AchievementBridge(adapter=adapter)
    outbox = bridge.outbox_for(
        mission, realm_id=MANIFEST["muse"]["realm_id"], command_id="cmd-test"
    )
    assert outbox is not None
    assert outbox["kind"] == "mission.completed"
    assert outbox["mode"] == "simulation"
    assert outbox["simulation_label"] == "simulation"
    assert any(ref.startswith("sha256:") for ref in outbox["evidence_references"])
    record = bridge.record_outbox(outbox, occurred_at="2026-07-13T00:00:00+00:00")
    assert record == {
        "status": "accepted",
        "record_id": "external_test",
        "dedupe_key": "k" * 64,
    }
    assert adapter.envelopes[0]["provenance"]["realm_id"] == MANIFEST["muse"]["realm_id"]


def test_unlabeled_simulation_mission_is_dropped(artifact: Path):
    sync = _load_sync_module()
    mission = sync.build_mission(MANIFEST, artifact)
    mission["evidence_label"] = ""
    bridge = AchievementBridge(adapter=RecordingAdapter())
    assert (
        bridge.outbox_for(mission, realm_id="realm", command_id="cmd") is None
    ), "simulation missions without the simulation label must never sync"


def test_sync_dry_run_records_nothing(artifact: Path):
    sync = _load_sync_module()
    adapter = RecordingAdapter()
    result = sync.sync(artifact, bridge=AchievementBridge(adapter=adapter), dry_run=True)
    assert result["outbox"] is not None
    assert result["record"] is None
    assert result["synced"] is False
    assert adapter.envelopes == []


def test_sync_records_through_bridge(artifact: Path):
    sync = _load_sync_module()
    adapter = RecordingAdapter()
    result = sync.sync(artifact, bridge=AchievementBridge(adapter=adapter))
    assert result["synced"] is True
    assert result["record"]["status"] == "accepted"
    assert len(adapter.envelopes) == 1
