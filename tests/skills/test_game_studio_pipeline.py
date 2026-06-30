"""Smoke test for the Game Studio pipeline runner.

Runs the runner offline (stub-only) as a subprocess so it exercises the real
`StudioOrchestrator.produce_game` DAG end-to-end without network or spend.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "skills" / "creative" / "game-studio" / "scripts" / "run_pipeline.py"


def test_runner_exists():
    assert RUNNER.is_file()


def test_pipeline_runs_offline(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(RUNNER),
         "--title", "Aether Drift", "--genre", "sci-fi explorer",
         "--engine", "godot", "--core-loop", "scan, salvage, upgrade",
         "--out", str(tmp_path / "out"), "--offline", "--json"],
        cwd=str(REPO), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"runner failed:\n{proc.stdout}\n{proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["title"] == "Aether Drift"
    assert data["engine"] == "godot"
    assert data["stage_count"] >= 10
    assert data["failed"] == []
    # Stages should include the key production capabilities.
    stages = {s["stage"] for s in data["stages"]}
    assert "gdd" in stages
    assert "mesh3d" in stages


def test_pipeline_text_summary_offline(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(RUNNER),
         "--title", "Greybox Test", "--genre", "platformer",
         "--out", str(tmp_path / "out2"), "--offline"],
        cwd=str(REPO), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"runner failed:\n{proc.stdout}\n{proc.stderr}"
    assert "GAME: Greybox Test" in proc.stdout
    # Godot note points the user at the runnable slice.
    assert "reference slice" in proc.stdout.lower() or "export_godot_slice" in proc.stdout
