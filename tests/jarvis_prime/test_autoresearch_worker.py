"""Tests for the autoresearch worker adapter (gating, scoring, contract)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from hermes_cli.jarvis_prime.benchmark_gate import evaluate_improvement
from hermes_cli.jarvis_prime.gates import GateOutcome
from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
    EditContext,
    ExperimentConfig,
    ExperimentEdit,
    bpb_gate_score,
)
from hermes_cli.workers.autoresearch import (
    SPAWN_ENV,
    AutoresearchWorker,
    AutoresearchWorkerConfig,
)
from hermes_cli.workers.base import WorkerScore


def _data_cache(tmp_path: Path) -> Path:
    cache = tmp_path / "cache"
    (cache / "tokenizer").mkdir(parents=True)
    (cache / "tokenizer" / "tokenizer.pkl").write_bytes(b"fake")
    (cache / "data").mkdir()
    (cache / "data" / "shard_00000.parquet").write_bytes(b"fake")
    return cache


SUMMARY = """\
---
val_bpb:          {bpb:.6f}
training_seconds: 300.0
total_seconds:    320.0
peak_vram_mb:     {vram:.1f}
mfu_percent:      10.0
total_tokens_M:   100.0
num_steps:        100
num_params_M:     50.0
depth:            8
"""


class _Completed:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = 0


def _fake_git(args, cwd):
    if list(args)[:2] == ["rev-parse", "--short=7"]:
        return _Completed("abc1234")
    return _Completed("")


def _worker(
    tmp_path: Path,
    outputs: list[str],
    *,
    edits: Optional[list[str]] = None,
    vram_budget: float = 12000.0,
) -> AutoresearchWorker:
    items = list(edits or [])

    def provider(ctx: EditContext) -> Optional[ExperimentEdit]:
        if not items:
            return None
        return ExperimentEdit(description=items.pop(0), train_py="# edit\n")

    def runner(argv, *, cwd, timeout, env=None):
        return _Completed(outputs.pop(0))

    return AutoresearchWorker(
        config=AutoresearchWorkerConfig(
            experiment=ExperimentConfig(
                tag="wk",
                workspace_dir=str(tmp_path / "ws"),
                device="modal:test",  # skip CUDA detection in CI
                vram_budget_mb=vram_budget,
            ),
            propose_edit=provider,
            subprocess_runner=runner,
            git_runner=_fake_git,
            data_cache=_data_cache(tmp_path),
        )
    )


def test_detect_blocks_without_spawn_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(SPAWN_ENV, raising=False)
    detection = _worker(tmp_path, []).detect()
    assert not detection.available
    assert SPAWN_ENV in detection.reason


def test_detect_blocks_without_uv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    monkeypatch.setattr("hermes_cli.workers.autoresearch.detect_command", lambda c: False)
    detection = _worker(tmp_path, []).detect()
    assert not detection.available
    assert "uv" in detection.reason


def test_detect_blocks_without_training_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    monkeypatch.setattr("hermes_cli.workers.autoresearch.detect_command", lambda c: True)
    worker = AutoresearchWorker(
        config=AutoresearchWorkerConfig(
            experiment=ExperimentConfig(tag="x", device="modal:test"),
            data_cache=tmp_path / "empty-cache",
        )
    )
    detection = worker.detect()
    assert not detection.available
    assert "prepare.py" in detection.reason


def test_modal_lane_detects_without_cuda(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    monkeypatch.setattr("hermes_cli.workers.autoresearch.detect_command", lambda c: True)
    detection = _worker(tmp_path, []).detect()
    assert detection.available
    assert "modal" in detection.reason


def test_run_collect_score_end_to_end(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    monkeypatch.setattr("hermes_cli.workers.autoresearch.detect_command", lambda c: True)
    outputs = [
        SUMMARY.format(bpb=1.0, vram=9000.0),
        SUMMARY.format(bpb=0.95, vram=9100.0),
    ]
    worker = _worker(tmp_path, outputs, edits=["raise lr"])
    job = object()
    prompt = worker.prepare_prompt(type("J", (), {"objective": "go", "prompt": "go"})())
    assert "MUSE governance addendum" in prompt.text
    assert "NEVER STOP" in prompt.text  # vendored program.md is included

    run = worker.run(job)
    assert run.ok, run.error
    artifacts = worker.collect(job)
    details = dict(artifacts.details)
    assert details["best_gen"] == 1
    assert details["champion"]["val_bpb"] == pytest.approx(0.95)
    assert [g["gen"] for g in details["generations"]] == [0, 1]

    score = worker.score(artifacts)
    assert isinstance(score, WorkerScore)  # [0,1] contract validated on init
    assert score.value == pytest.approx(bpb_gate_score(0.95))
    assert "0.95" in score.rationale  # raw bpb preserved for honesty


def test_sign_flip_through_benchmark_gate(monkeypatch, tmp_path: Path) -> None:
    # lower bpb must PASS the higher-is-better gate after the transform
    baseline, better, worse = 1.0, 0.95, 1.05
    gate = evaluate_improvement(
        bpb_gate_score(baseline), bpb_gate_score(better), task="autoresearch_pretrain"
    )
    assert gate.outcome is GateOutcome.PASS
    gate = evaluate_improvement(
        bpb_gate_score(baseline), bpb_gate_score(worse), task="autoresearch_pretrain"
    )
    assert gate.outcome is GateOutcome.FAIL


def test_raw_negated_bpb_violates_worker_score_contract() -> None:
    # Regression pin: literal negation of a lower-is-better metric is illegal.
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        WorkerScore(value=-0.95)


def test_score_zero_when_no_feasible_champion(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    monkeypatch.setattr("hermes_cli.workers.autoresearch.detect_command", lambda c: True)
    outputs = [
        SUMMARY.format(bpb=1.0, vram=9000.0),
        SUMMARY.format(bpb=0.90, vram=13000.0),  # wins bpb, blows 12GB budget
    ]
    worker = _worker(tmp_path, outputs, edits=["huge model"])
    job = object()
    assert worker.run(job).ok
    score = worker.score(worker.collect(job))
    assert score.value == 0.0 and score.confidence == 0.0
    assert "infeasible" in score.rationale


def test_run_fails_closed_without_edit_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    monkeypatch.setattr("hermes_cli.workers.autoresearch.detect_command", lambda c: True)
    worker = AutoresearchWorker(
        config=AutoresearchWorkerConfig(
            experiment=ExperimentConfig(tag="x", device="modal:test"),
            data_cache=_data_cache(tmp_path),
        )
    )
    result = worker.run(object())
    assert not result.ok
    assert "edit provider" in result.error
