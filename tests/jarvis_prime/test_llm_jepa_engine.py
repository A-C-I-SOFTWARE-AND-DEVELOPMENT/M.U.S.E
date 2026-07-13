"""Tests for the torch-free LLM-JEPA engine (plan / run / gate / proposal)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.research_fabric.llm_jepa import engine, views
from hermes_cli.jarvis_prime.gates import GateOutcome
from hermes_cli.jarvis_prime.self_update import ProposalBook, ProposalStatus


def _pairs(tmp_path: Path) -> Path:
    vs = [
        views.TwoView(text=f"intent number {i} here", code=f"def f{i}(): return {i}")
        for i in range(5)
    ]
    return views.views_to_jsonl(vs, tmp_path / "pairs.jsonl")


def test_compute_multiplier_reflects_loss_dropout():
    cfg = engine.JepaFinetuneConfig(jepa_loss_dropout=0.75)
    assert cfg.compute_multiplier() == pytest.approx(1.25)
    cfg2 = engine.JepaFinetuneConfig(jepa_loss_dropout=0.0)
    assert cfg2.compute_multiplier() == pytest.approx(2.0)


def test_plan_is_torch_free_and_describes_objective(tmp_path):
    cfg = engine.JepaFinetuneConfig(tag="t")
    plan = engine.plan_finetune(cfg, 10)
    assert plan["mode"] == "plan"
    assert "L_LLM" in plan["objective"]
    assert plan["n_pairs"] == 10
    assert plan["gate"]["min_margin"] == cfg.min_margin


def test_run_finetune_is_noop_without_spawn(tmp_path):
    cfg = engine.JepaFinetuneConfig(tag="t", workspace_root=tmp_path)
    pairs = _pairs(tmp_path)
    res = engine.run_finetune(cfg, pairs, allow_spawn=False)
    assert res.status == "plan"
    assert res.jepa_accuracy is None


def test_run_finetune_live_parses_summary(tmp_path):
    cfg = engine.JepaFinetuneConfig(tag="live", workspace_root=tmp_path)
    pairs = _pairs(tmp_path)

    def fake_runner(argv, cwd=None, capture_output=True, text=True, timeout=None):
        # Assert the workspace was seeded with the vendored harness + pairs.
        assert (Path(cwd) / "train.py").exists()
        assert (Path(cwd) / "pairs.jsonl").exists()
        out = "training...\nbaseline_accuracy: 0.40\njepa_accuracy: 0.62\n"
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    res = engine.run_finetune(cfg, pairs, allow_spawn=True, runner=fake_runner)
    assert res.status == "keep"
    assert res.baseline_accuracy == pytest.approx(0.40)
    assert res.jepa_accuracy == pytest.approx(0.62)


def test_run_finetune_live_crash_is_contained(tmp_path):
    cfg = engine.JepaFinetuneConfig(tag="crash", workspace_root=tmp_path)
    pairs = _pairs(tmp_path)

    def boom(argv, cwd=None, capture_output=True, text=True, timeout=None):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="boom")

    res = engine.run_finetune(cfg, pairs, allow_spawn=True, runner=boom)
    assert res.status == "crash"


def test_gate_passes_only_on_real_lift(tmp_path):
    cfg = engine.JepaFinetuneConfig(min_margin=0.05)
    win = engine.JepaFinetuneResult(baseline_accuracy=0.5, jepa_accuracy=0.7)
    tie = engine.JepaFinetuneResult(baseline_accuracy=0.6, jepa_accuracy=0.6)
    missing = engine.JepaFinetuneResult(baseline_accuracy=None, jepa_accuracy=None)
    assert engine.evaluate_finetune(win, cfg).outcome is GateOutcome.PASS
    assert engine.evaluate_finetune(tie, cfg).outcome is GateOutcome.FAIL
    assert engine.evaluate_finetune(missing, cfg).outcome is GateOutcome.SKIPPED


def test_propose_promotion_is_rc4_owner_gated(tmp_path):
    cfg = engine.JepaFinetuneConfig()
    win = engine.JepaFinetuneResult(baseline_accuracy=0.5, jepa_accuracy=0.8, log_path="x")
    gate = engine.evaluate_finetune(win, cfg)
    book = ProposalBook()
    p = engine.propose_promotion(book, cfg, win, gate)
    assert p is not None
    assert p.risk_class == "RC4"
    assert p.status is ProposalStatus.NEEDS_OWNER_APPROVAL
    assert p.target_path.endswith("train.py")


def test_no_proposal_when_gate_fails(tmp_path):
    cfg = engine.JepaFinetuneConfig(min_margin=0.05)
    tie = engine.JepaFinetuneResult(baseline_accuracy=0.6, jepa_accuracy=0.6)
    gate = engine.evaluate_finetune(tie, cfg)
    book = ProposalBook()
    assert engine.propose_promotion(book, cfg, tie, gate) is None
    assert book.proposals == []


def test_jepa_gate_score_clamps():
    assert engine.jepa_gate_score(None) == 0.0
    assert engine.jepa_gate_score(1.5) == 1.0
    assert engine.jepa_gate_score(-0.2) == 0.0
    assert engine.jepa_gate_score(0.7) == pytest.approx(0.7)
