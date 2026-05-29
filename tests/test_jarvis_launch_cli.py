"""Tests for the JARVIS launch path: the launch() orchestrator and the
stdlib-only ``python -m hermes_cli.jarvis_prime`` launch subcommands.

The subprocess tests mirror tests/test_jarvis_prime_cli.py — they run the
real argparse + handler path end-to-end with a tmp HERMES_HOME, exercising
only the stdlib import path (no rich / dotenv / full install needed).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import launch as launch_mod


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = [sys.executable, "-m", "hermes_cli.jarvis_prime"]


def _run(args: list[str], home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    return subprocess.run(
        CLI + args, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60
    )


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# launch() orchestrator (in-process)
# ---------------------------------------------------------------------------


def test_launch_dry_run_is_ok_and_writes_nothing(hermes_home: Path) -> None:
    summary = launch_mod.launch(dry_run=True, which=lambda b: None)
    assert summary.ok is True
    # dry-run plans the policy but writes nothing.
    assert not (hermes_home / "jarvis_prime" / "model_policy.json").exists()


def test_launch_apply_writes_policy(hermes_home: Path) -> None:
    summary = launch_mod.launch(no_pull=True, which=lambda b: None)
    assert summary.ok is True
    assert (hermes_home / "jarvis_prime" / "model_policy.json").is_file()


def test_launch_steps_cover_required_stages(hermes_home: Path) -> None:
    summary = launch_mod.launch(dry_run=True, which=lambda b: None)
    names = {s.name for s in summary.steps}
    assert {
        "runtime",
        "model_bootstrap",
        "memory",
        "owner_gate",
        "emergency_stop",
        "slash_commands",
        "workers",
    } <= names


def test_launch_next_commands_present(hermes_home: Path) -> None:
    summary = launch_mod.launch(dry_run=True, which=lambda b: None)
    nc = summary.next_commands
    assert "hermes" in nc["start"]
    assert "/jarvis" in nc["invoke"]
    assert "doctor --jarvis-launch" in nc["doctor"]
    assert "stop" in nc["stop"]


def test_launch_owner_gate_and_emergency_stop_pass(hermes_home: Path) -> None:
    summary = launch_mod.launch(dry_run=True, which=lambda b: None)
    by = {s.name: s for s in summary.steps}
    assert by["owner_gate"].ok is True
    assert by["emergency_stop"].ok is True


def test_slash_invocations_constant() -> None:
    assert launch_mod.SLASH_INVOCATIONS == ("/jarvis", "/jp", "/jarvis-prime")


# ---------------------------------------------------------------------------
# CLI surface (subprocess, stdlib-only path)
# ---------------------------------------------------------------------------


def test_cli_help_lists_new_commands(hermes_home: Path) -> None:
    proc = _run(["--help"], hermes_home)
    assert proc.returncode == 0
    for cmd in ("bootstrap", "launch", "launch-doctor"):
        assert cmd in proc.stdout


def test_cli_bootstrap_dry_run_json(hermes_home: Path) -> None:
    proc = _run(["bootstrap", "--dry-run", "--json"], hermes_home)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["config_written"] is False
    assert not (hermes_home / "jarvis_prime" / "model_policy.json").exists()


def test_cli_launch_doctor_runs(hermes_home: Path) -> None:
    proc = _run(["launch-doctor"], hermes_home)
    assert proc.returncode == 0, proc.stderr
    assert "LAUNCH READY" in proc.stdout


def test_cli_launch_apply_writes_and_succeeds(hermes_home: Path) -> None:
    proc = _run(["launch", "--no-pull"], hermes_home)
    assert proc.returncode == 0, proc.stderr
    assert (hermes_home / "jarvis_prime" / "model_policy.json").is_file()


def test_cli_stop_still_works(hermes_home: Path) -> None:
    # Emergency stop must remain functional after the new commands land.
    proc = _run(["stop", "--reason", "test"], hermes_home)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["tick_disabled"] is True
    assert data["reason"] == "test"
