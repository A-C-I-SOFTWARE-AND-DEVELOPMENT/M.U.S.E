"""
Smoke tests for the Game Studio Godot 4 reference slice.

Two tiers (the darwinian-evolver philosophy — CI has no engine):
  1. Always-on structural asserts — the project files exist and parse as the
     text formats Godot expects, the asset slot is a real GLB, the GDScript
     controller has the expected entry points.
  2. A `godot`-gated test that actually loads the project headlessly to prove it
     is runnable (skipped when no `godot` binary is on PATH).
"""
from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

import pytest

SLICE = (
    Path(__file__).resolve().parents[2]
    / "skills" / "creative" / "game-studio" / "reference-slice"
)


# ---------------------------------------------------------------------------
# Tier 1 — structural (always run)
# ---------------------------------------------------------------------------


def test_slice_dir_exists():
    assert SLICE.is_dir(), f"missing slice: {SLICE}"


def test_required_files_present():
    for rel in (
        "project.godot",
        "export_presets.cfg",
        "scenes/Main.tscn",
        "scenes/Player.tscn",
        "scripts/player.gd",
        "assets/prop.glb",
        "README.md",
    ):
        assert (SLICE / rel).is_file(), f"missing {rel}"


def test_project_godot_main_scene():
    body = (SLICE / "project.godot").read_text()
    assert "config_version=5" in body
    assert 'run/main_scene="res://scenes/Main.tscn"' in body
    assert 'renderer/rendering_method="forward_plus"' in body
    for action in ("move_forward", "move_back", "move_left", "move_right", "jump"):
        assert action in body, f"input action {action!r} missing from project.godot"


def test_export_preset_named_linux():
    body = (SLICE / "export_presets.cfg").read_text()
    assert 'name="linux"' in body
    assert 'export_path="build/slice.x86_64"' in body


def test_main_scene_has_sota_lighting_and_player():
    body = (SLICE / "scenes" / "Main.tscn").read_text()
    assert 'type="WorldEnvironment"' in body
    assert "sdfgi_enabled = true" in body
    assert "ssao_enabled = true" in body
    assert 'type="DirectionalLight3D"' in body
    assert 'type="StaticBody3D"' in body
    assert 'name="HeroProp"' in body
    assert "Player.tscn" in body


def test_player_scene_references_script():
    body = (SLICE / "scenes" / "Player.tscn").read_text()
    assert "res://scripts/player.gd" in body
    assert 'type="CharacterBody3D"' in body
    assert 'type="Camera3D"' in body


def test_player_script_has_controller_entrypoints():
    body = (SLICE / "scripts" / "player.gd").read_text()
    assert "extends CharacterBody3D" in body
    assert "_physics_process" in body
    assert "move_and_slide" in body
    assert "res://assets/prop.glb" in body


def test_gameplay_loop_present():
    # Round 3: the slice is an actual game loop (collect → win), not just a walk.
    assert (SLICE / "scripts" / "game.gd").is_file()
    assert (SLICE / "scripts" / "collectible.gd").is_file()
    assert (SLICE / "scenes" / "Collectible.tscn").is_file()

    game = (SLICE / "scripts" / "game.gd").read_text()
    assert "func collect" in game
    assert "win" in game.lower()

    collectible = (SLICE / "scripts" / "collectible.gd").read_text()
    assert "collectibles" in collectible
    assert "is_in_group(\"player\")" in collectible

    main = (SLICE / "scenes" / "Main.tscn").read_text()
    assert "scripts/game.gd" in main
    assert 'type="CanvasLayer"' in main          # HUD
    assert 'name="Status"' in main               # score label
    assert "Collectible.tscn" in main            # objective instances

    player = (SLICE / "scripts" / "player.gd").read_text()
    assert 'add_to_group("player")' in player


def test_prop_glb_is_valid_glb_header():
    raw = (SLICE / "assets" / "prop.glb").read_bytes()
    assert len(raw) >= 12
    magic, version, length = struct.unpack("<4sII", raw[:12])
    assert magic == b"glTF"
    assert version == 2
    assert length == len(raw)


# ---------------------------------------------------------------------------
# Tier 2 — engine-gated (skipped without a godot binary)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("godot") is None, reason="godot binary not installed")
def test_project_loads_headlessly():
    """A stronger proof: Godot can import + open the project without errors.

    Validates the project is genuinely loadable (scenes parse, script compiles)
    without needing export templates for a full build.
    """
    proc = subprocess.run(  # noqa: S603,S607
        ["godot", "--headless", "--path", str(SLICE), "--quit"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"godot failed to open project:\n{combined[-3000:]}"
    assert "SCRIPT ERROR" not in combined.upper(), combined[-3000:]
