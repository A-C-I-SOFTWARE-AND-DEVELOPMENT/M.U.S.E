"""Tests for the owner-gated autoresearch bridge (reuses run_self_improvement)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import pytest

from hermes_cli.jarvis_prime.autoresearch_improve import (
    TARGET_PATH,
    TASK_NAME,
    evaluate_constraints,
    record_promotion,
    run_autoresearch_improvement,
)
from hermes_cli.jarvis_prime.gates import GateOutcome
from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import bpb_gate_score
from hermes_cli.jarvis_prime.self_update import ProposalBook, ProposalKind, ProposalStatus
from hermes_cli.workers.base import (
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)


class FakeAutoresearchWorker:
    """Duck-typed worker in the FakeSiaWorker pattern."""

    def __init__(
        self,
        *,
        champion_bpb: Optional[float] = 0.95,
        baseline_bpb: float = 1.0,
        infeasible_bpb: Optional[float] = None,
        total_cost_usd: float = 0.0,
        available: bool = True,
    ) -> None:
        self.champion_bpb = champion_bpb
        self.baseline_bpb = baseline_bpb
        self.infeasible_bpb = infeasible_bpb
        self.total_cost_usd = total_cost_usd
        self.available = available

    def detect(self) -> WorkerDetection:
        return WorkerDetection(available=self.available, reason="fake")

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text="fake")

    def run(self, job: Any) -> WorkerRunResult:
        return WorkerRunResult(ok=True)

    def collect(self, job: Any) -> WorkerArtifacts:
        experiments = [
            {
                "index": 0, "commit": "c000001", "description": "baseline",
                "val_bpb": self.baseline_bpb, "peak_vram_mb": 9000.0,
                "mfu_percent_raw": 10.0, "mfu_percent_honest": None,
                "training_seconds": 300.0, "total_seconds": 320.0,
                "total_tokens_m": 100.0, "num_steps": 100, "num_params_m": 50.0,
                "depth": 8, "status": "keep", "reason": "", "log_tail": "",
                "cost_usd": 0.0,
            }
        ]
        champion = None
        if self.champion_bpb is not None:
            champion = dict(
                experiments[0],
                index=1, commit="c000002", description="raise lr",
                val_bpb=self.champion_bpb,
            )
            experiments.append(champion)
        best_infeasible = None
        if self.infeasible_bpb is not None:
            best_infeasible = dict(
                experiments[0],
                index=2, commit="c000003", description="huge model",
                val_bpb=self.infeasible_bpb, peak_vram_mb=13000.0,
                status="infeasible",
                reason="peak VRAM 13000.0MB > budget 12000.0MB",
            )
            experiments.append(best_infeasible)
        gens = [
            {
                "gen": e["index"],
                "score": bpb_gate_score(e["val_bpb"]),
                "target_agent": "/ws/train.py",
                "improvement": "/ws/results.tsv",
            }
            for e in experiments
        ]
        return WorkerArtifacts(
            workspace_path="/ws",
            details={
                "best_gen": champion["index"] if champion else None,
                "generations": gens,
                "experiments": experiments,
                "champion": champion,
                "best_infeasible": best_infeasible,
                "baseline_bpb": self.baseline_bpb,
                "results_tsv": "/ws/results.tsv",
                "total_cost_usd": self.total_cost_usd,
                "stopped_reason": "edit_provider_exhausted",
                "branch": "autoresearch/test",
                "device": "cuda:0",
                "tag": "test",
            },
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        champion = artifacts.details.get("champion")
        if not champion:
            return WorkerScore(value=0.0, confidence=0.0, rationale="no champion")
        return WorkerScore(
            value=bpb_gate_score(champion["val_bpb"]),
            confidence=0.5,
            rationale=f"champion bpb {champion['val_bpb']}",
        )


def _run(worker: FakeAutoresearchWorker, **kwargs):
    book = ProposalBook()
    outcome = run_autoresearch_improvement(
        "lower val_bpb",
        book=book,
        worker=worker,
        baseline_bpb=worker.baseline_bpb,
        vram_budget_mb=kwargs.pop("vram_budget_mb", 12000.0),
        **kwargs,
    )
    return outcome, book


def test_improvement_yields_owner_gated_rc4_proposal() -> None:
    outcome, book = _run(FakeAutoresearchWorker(champion_bpb=0.95))
    assert outcome.sia.improved
    proposal = outcome.proposal
    assert proposal is not None
    assert proposal.kind is ProposalKind.SELF_RUNTIME_UPDATE  # hermes_cli/ target
    assert proposal.risk_class == "RC4"
    assert proposal.status is ProposalStatus.NEEDS_OWNER_APPROVAL
    assert proposal.target_path == TARGET_PATH
    assert proposal in book.proposals
    assert outcome.constraints_gate.outcome is GateOutcome.PASS
    assert outcome.sia.task == TASK_NAME


def test_regression_yields_no_proposal() -> None:
    outcome, book = _run(FakeAutoresearchWorker(champion_bpb=1.05))
    assert not outcome.sia.improved
    assert outcome.proposal is None
    assert book.proposals == []


def test_vram_blown_winner_is_named_constraint_fail_with_no_proposal() -> None:
    worker = FakeAutoresearchWorker(champion_bpb=None, infeasible_bpb=0.90)
    outcome, book = _run(worker)
    assert outcome.proposal is None and book.proposals == []
    assert outcome.constraints_gate.outcome is GateOutcome.FAIL
    assert "infeasible" in outcome.constraints_gate.reason
    assert "VRAM" in outcome.constraints_gate.reason


def test_cost_exceeded_is_named_constraint_fail() -> None:
    gate = evaluate_constraints(
        {"champion": {"val_bpb": 0.9, "peak_vram_mb": 9000.0}, "total_cost_usd": 5.0},
        vram_budget_mb=12000.0,
        max_cost_usd=2.0,
    )
    assert gate.outcome is GateOutcome.FAIL
    assert "ceiling" in gate.reason


def test_champion_records_exactly_one_scorecard() -> None:
    book = ScorecardBook()  # in-memory, no path
    outcome, _ = _run(FakeAutoresearchWorker(champion_bpb=0.95), scorecard_book=book)
    assert len(outcome.scorecards) == 1
    card = outcome.scorecards[0]
    assert card.model == "autoresearch/test@c000002"
    assert card.task_type == TASK_NAME
    assert card.accepted_diff_rate == pytest.approx(bpb_gate_score(0.95))
    assert book.scorecards == [card]


def test_axiom_chain_record_when_gates_on(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MUSE_AXIOM_GATES", "1")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    outcome, _ = _run(FakeAutoresearchWorker(champion_bpb=0.95))
    chain = tmp_path / "axiom" / "chain.jsonl"
    if outcome.chain_hash is not None:
        records = [json.loads(line) for line in chain.read_text(encoding="utf-8").splitlines()]
        assert any(r["kind"] == "autoresearch.champion" for r in records)
    else:
        # Bridge soft-failed (e.g. axiom extra not installed) — must not raise.
        assert outcome.proposal is not None


def test_axiom_inert_when_gates_off(monkeypatch) -> None:
    monkeypatch.setenv("MUSE_AXIOM_GATES", "0")
    outcome, _ = _run(FakeAutoresearchWorker(champion_bpb=0.95))
    assert outcome.chain_hash is None


def test_memory_tree_consolidation_writes_durable_note(tmp_path: Path) -> None:
    from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore

    store = MemoryTreeStore(path=tmp_path / "memory_tree.jsonl")
    outcome, _ = _run(FakeAutoresearchWorker(champion_bpb=0.95), memory_store=store)
    assert outcome.memory_written
    nodes = [n for n in store.nodes.values() if "autoresearch" in n.title]
    assert nodes, "expected a consolidated what-worked node"
    assert "raise lr" in nodes[0].text  # kept idea class named
    assert any("results.tsv" in s.uri for s in nodes[0].sources)


def test_swarm_lane_mode_never_writes_the_real_book() -> None:
    book = ProposalBook()
    outcome = run_autoresearch_improvement(
        "lane run",
        book=book,
        worker=FakeAutoresearchWorker(champion_bpb=0.95),
        baseline_bpb=1.0,
        vram_budget_mb=12000.0,
        emit_proposal=False,
    )
    assert outcome.sia.improved  # the gate still PASSed in the throwaway book
    assert book.proposals == []  # but the real book is untouched


def test_unavailable_worker_skips_cleanly() -> None:
    outcome, book = _run(FakeAutoresearchWorker(available=False))
    assert not outcome.sia.available
    assert outcome.proposal is None and book.proposals == []


def test_record_promotion_is_high_risk_with_owner_gate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MUSE_AXIOM_GATES", "1")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    result = record_promotion(TARGET_PATH, commit="c000002", val_bpb=0.95, diff_loc=40)
    classification = result["classification"]
    assert classification["risk"] == "HIGH"
    assert "owner_approval" in classification["gates"]
    if result["chain_hash"] is not None:
        chain = tmp_path / "axiom" / "chain.jsonl"
        records = [json.loads(line) for line in chain.read_text(encoding="utf-8").splitlines()]
        assert any(r["kind"] == "autoresearch.promotion" for r in records)


def test_dataset_candidate_offer_is_soft_fail(monkeypatch) -> None:
    # Even if the learning-dataset layer explodes, the run must not raise.
    import hermes_cli.jarvis_prime.autoresearch_improve as mod

    def boom(details):
        raise RuntimeError("dataset layer down")

    monkeypatch.setattr(mod, "_offer_dataset_candidate", boom)
    outcome, _ = _run(FakeAutoresearchWorker(champion_bpb=0.95))
    assert outcome.proposal is not None
    assert os.environ.get("HERMES_HOME")  # hermetic guard intact
