"""Tests for the SIA worker adapter (``muse_cli/workers/sia.py``).

SIA itself is never invoked — we inject a fake runner that simulates the
``runs/run_*/gen_*/`` artifacts SIA writes, so the tests are hermetic
(no network, no ``sia`` binary). The key behaviors: detection, sandbox
confinement, generation parsing, and scoring.
"""

from __future__ import annotations

import json
import subprocess
import types
from pathlib import Path
from unittest import mock

from muse_cli.workers import registry
from muse_cli.workers.sia import SiaConfig, SiaWorker


def _job(**overrides):
    defaults = {
        "prompt": "Improve the planner so it localizes edit sites better.",
        "objective": "Improve the planner so it localizes edit sites better.",
        "target_path": "",
        "task": "planner-bench",
        "job_id": "t1",
    }
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _fake_runner_two_gens(scores=(0.4, 0.8)):
    def runner(argv, *, cwd, timeout):
        root = Path(cwd)
        for i, sc in enumerate(scores, start=1):
            gen = root / "runs" / "run_1" / f"gen_{i}"
            gen.mkdir(parents=True, exist_ok=True)
            (gen / "target_agent.py").write_text(
                f"def solve(t):\n    return 'v{i}'\n", encoding="utf-8"
            )
            (gen / "agent_execution.json").write_text(
                json.dumps({"score": sc}), encoding="utf-8"
            )
            (gen / "improvement.md").write_text(f"gen {i}", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="sia: ok\n", stderr=""
        )

    return runner


# ── detection ──────────────────────────────────────────────────────────


def test_detect_unavailable_when_not_installed():
    worker = SiaWorker()
    with (
        mock.patch("muse_cli.workers.sia.detect_command", return_value=False),
        mock.patch(
            "muse_cli.workers.sia.importlib.util.find_spec", return_value=None
        ),
    ):
        det = worker.detect()
    assert det.available is False
    assert "install" in det.details
    assert "sia-agent" in det.details["install"]


def test_detect_available_when_on_path():
    worker = SiaWorker()
    with mock.patch("muse_cli.workers.sia.detect_command", return_value=True):
        det = worker.detect()
    assert det.available is True


# ── prepare_prompt ───────────────────────────────────────────────────────


def test_prepare_prompt_carries_objective_and_metadata():
    worker = SiaWorker()
    prompt = worker.prepare_prompt(_job())
    assert "planner" in prompt.text
    assert prompt.metadata["task"] == "planner-bench"
    assert prompt.metadata["max_gen"] <= 10


# ── run / collect / score (hermetic, fake runner) ────────────────────────


def test_run_executes_in_sandbox_and_parses_generations(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    worker = SiaWorker(repo_root=str(repo), runner=_fake_runner_two_gens())

    job = _job()
    result = worker.run(job)

    assert result.ok is True
    assert result.details["generations"] == 2
    assert result.details["best_gen"] == 2

    # Confinement: everything SIA produced lives under the sandbox, and
    # nothing leaked into the repo root.
    ws = Path(result.details["workspace"])
    assert ".hermes-orchestrator" in ws.parts
    assert str(repo) in str(ws)
    assert not (repo / "runs").exists()  # SIA wrote runs/ under the sandbox

    artifacts = worker.collect(job)
    assert len(artifacts.files) == 2
    assert ".hermes-orchestrator" in artifacts.workspace_path

    score = worker.score(artifacts)
    assert score.value == 0.8  # best of (0.4, 0.8)
    assert score.components["gen_1"] == 0.4
    assert score.components["gen_2"] == 0.8


def test_run_empty_objective_fails():
    worker = SiaWorker()
    result = worker.run(_job(prompt="", objective=""))
    assert result.ok is False
    assert "objective" in result.error


def test_score_zero_when_no_parsable_scores(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def runner_no_scores(argv, *, cwd, timeout):
        gen = Path(cwd) / "runs" / "run_1" / "gen_1"
        gen.mkdir(parents=True, exist_ok=True)
        (gen / "target_agent.py").write_text("x = 1\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr=""
        )

    worker = SiaWorker(repo_root=str(repo), runner=runner_no_scores)
    job = _job()
    worker.run(job)
    score = worker.score(worker.collect(job))
    assert score.value == 0.0
    assert score.confidence == 0.0


def test_percentage_scores_are_normalized(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    worker = SiaWorker(
        repo_root=str(repo), runner=_fake_runner_two_gens(scores=(55.0, 90.0))
    )
    job = _job()
    worker.run(job)
    score = worker.score(worker.collect(job))
    assert score.value == 0.9  # 90.0 → 0.9


def test_timeout_is_handled(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def boom(argv, *, cwd, timeout):
        raise subprocess.TimeoutExpired(cmd="sia", timeout=timeout)

    worker = SiaWorker(repo_root=str(repo), runner=boom)
    result = worker.run(_job())
    assert result.ok is False
    assert "timed out" in result.error


# ── registration ─────────────────────────────────────────────────────────


def test_worker_is_registered():
    from muse_cli.workers import load_builtins

    load_builtins()
    assert "sia" in registry.default_registry
    assert registry.get("sia").id == "sia"
