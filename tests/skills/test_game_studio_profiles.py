"""Tests for the Game Studio engine-profile installer.

Loads the script by path (it lives under the skill, not an importable package).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "creative" / "game-studio" / "scripts" / "install_profiles.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("install_profiles", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_exists():
    assert SCRIPT.is_file()


def test_plan_all_missing_on_empty_config():
    mod = _load_module()
    to_add = mod.plan({}, force=False)
    assert set(to_add) == {"game-godot", "game-ue5", "game-unity"}


def test_plan_skips_existing():
    mod = _load_module()
    existing = {"profiles": {"game-godot": {"model": "x"}}}
    to_add = mod.plan(existing, force=False)
    assert "game-godot" not in to_add
    assert "game-ue5" in to_add


def test_plan_force_includes_all():
    mod = _load_module()
    existing = {"profiles": {"game-godot": {"model": "x"}}}
    to_add = mod.plan(existing, force=True)
    assert set(to_add) == {"game-godot", "game-ue5", "game-unity"}


def test_no_model_identifier_leak():
    # Guard: the configured undercover model id must not be hard-coded.
    body = SCRIPT.read_text()
    assert "claude-opus-4-8" not in body


def test_dry_run_writes_nothing(tmp_path):
    cfg = tmp_path / "config.yaml"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(cfg)],
        cwd=str(REPO), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0
    assert "game-godot" in proc.stdout
    assert not cfg.exists(), "dry-run must not write the config"


def test_apply_merges_and_preserves_existing(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump({
        "model": {"provider": "anthropic"},
        "profiles": {"researcher": {"model": "x"}},
    }))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(cfg), "--apply", "--json"],
        cwd=str(REPO), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert set(data["added"]) == {"game-godot", "game-ue5", "game-unity"}

    written = yaml.safe_load(cfg.read_text())
    # Existing keys preserved; new profiles added.
    assert written["model"] == {"provider": "anthropic"}
    assert "researcher" in written["profiles"]
    assert "game-godot" in written["profiles"]
    # Backup created.
    assert (tmp_path / "config.yaml.bak").is_file()


def test_apply_is_idempotent(tmp_path):
    cfg = tmp_path / "config.yaml"
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(SCRIPT), "--config", str(cfg), "--apply"],
            cwd=str(REPO), capture_output=True, text=True, timeout=60,
        )
    # Second run is a no-op; re-running --apply --json reports nothing to add.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(cfg), "--apply", "--json"],
        cwd=str(REPO), capture_output=True, text=True, timeout=60,
    )
    data = json.loads(proc.stdout)
    assert data["added"] == []
