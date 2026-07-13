"""Tests for the LLM-JEPA worker adapter (dry-run default + gated live run)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.research_fabric.llm_jepa import engine, views
from hermes_cli.workers import llm_jepa
from hermes_cli.workers.llm_jepa import LlmJepaWorker, LlmJepaWorkerConfig


def _pairs(tmp_path: Path) -> Path:
    vs = [
        views.TwoView(text=f"intent number {i} here", code=f"def f{i}(): return {i}")
        for i in range(4)
    ]
    return views.views_to_jsonl(vs, tmp_path / "pairs.jsonl")


def test_registered_in_default_registry():
    from hermes_cli.workers import builtin_worker_classes, known_workers

    builtin_worker_classes()  # importing self-registers
    assert "llm-jepa" in known_workers()


def test_dry_run_detect_available_without_gate(tmp_path, monkeypatch):
    monkeypatch.delenv("MUSE_LLM_JEPA_ALLOW_SPAWN", raising=False)
    cfg = LlmJepaWorkerConfig(finetune=engine.JepaFinetuneConfig(), dry_run=True)
    worker = LlmJepaWorker(config=cfg)
    det = worker.detect()
    assert det.available is True
    assert det.details.get("mode") == "plan"


def test_dry_run_produces_plan_not_training(tmp_path, monkeypatch):
    monkeypatch.delenv("MUSE_LLM_JEPA_ALLOW_SPAWN", raising=False)
    pairs = _pairs(tmp_path)
    cfg = LlmJepaWorkerConfig(
        finetune=engine.JepaFinetuneConfig(workspace_root=tmp_path),
        pairs_jsonl=pairs,
        dry_run=True,
    )
    worker = LlmJepaWorker(config=cfg)
    run = worker.run(object())
    assert run.ok
    assert run.details["mode"] == "plan"
    assert run.details["n_pairs"] == 4
    score = worker.score(worker.collect(object()))
    assert score.value == 0.0
    assert "plan-only" in score.rationale


def test_live_run_blocked_without_spawn_env(tmp_path, monkeypatch):
    monkeypatch.delenv("MUSE_LLM_JEPA_ALLOW_SPAWN", raising=False)
    cfg = LlmJepaWorkerConfig(finetune=engine.JepaFinetuneConfig(), dry_run=False)
    worker = LlmJepaWorker(config=cfg)
    det = worker.detect()
    assert det.available is False
    assert "owner-gated" in det.reason


def test_live_run_scores_jepa_accuracy(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSE_LLM_JEPA_ALLOW_SPAWN", "1")
    monkeypatch.setattr(llm_jepa, "detect_command", lambda cmd: True)
    pairs = _pairs(tmp_path)

    def fake_runner(argv, cwd=None, capture_output=True, text=True, timeout=None):
        out = "baseline_accuracy: 0.30\njepa_accuracy: 0.55\n"
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    cfg = LlmJepaWorkerConfig(
        finetune=engine.JepaFinetuneConfig(tag="w", workspace_root=tmp_path),
        pairs_jsonl=pairs,
        dry_run=False,
        subprocess_runner=fake_runner,
    )
    worker = LlmJepaWorker(config=cfg)
    assert worker.detect().available is True
    run = worker.run(object())
    assert run.ok
    score = worker.score(worker.collect(object()))
    assert score.value == pytest.approx(0.55)
    assert score.components["baseline"] == pytest.approx(0.30)


def test_score_zero_when_metrics_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSE_LLM_JEPA_ALLOW_SPAWN", "1")
    monkeypatch.setattr(llm_jepa, "detect_command", lambda cmd: True)
    pairs = _pairs(tmp_path)

    def crash_runner(argv, cwd=None, capture_output=True, text=True, timeout=None):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="oom")

    cfg = LlmJepaWorkerConfig(
        finetune=engine.JepaFinetuneConfig(tag="w2", workspace_root=tmp_path),
        pairs_jsonl=pairs,
        dry_run=False,
        subprocess_runner=crash_runner,
    )
    worker = LlmJepaWorker(config=cfg)
    run = worker.run(object())
    assert not run.ok
    score = worker.score(worker.collect(object()))
    assert score.value == 0.0
