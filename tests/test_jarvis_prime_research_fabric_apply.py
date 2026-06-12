"""Live git-backed apply / rollback — proves the activation path is real."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from muse_cli.jarvis_prime.gates import GateOutcome, GateResult, GateSummary
from muse_cli.jarvis_prime.guardrail_evidence import (
    GuardrailEvidenceBundle,
    GuardrailLedger,
)
from muse_cli.jarvis_prime.owner_auth import authorize_challenge, create_challenge
from muse_cli.jarvis_prime.self_update import ProposalBook, ProposalKind
from muse_cli.jarvis_prime.research_fabric.apply import (
    ApplyRefused,
    GitApplier,
    GitRollback,
    current_head,
)
from muse_cli.jarvis_prime.research_fabric.catalog import REQUIRED_DOMAINS
from muse_cli.jarvis_prime.research_fabric.champion import Champion, ChampionStore
from muse_cli.jarvis_prime.research_fabric.charter import CharterBook
from muse_cli.jarvis_prime.research_fabric.controller import AutonomyController
from muse_cli.jarvis_prime.research_fabric.monitor import AlignmentMonitor
from muse_cli.jarvis_prime.research_fabric.store import SnapshotStore
from muse_cli.jarvis_prime.research_fabric.verifier import Candidate


def _full(v: float) -> dict[str, float]:
    return {d: v for d in REQUIRED_DOMAINS}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(
        repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed"
    )
    return current_head(repo)


def _pass_gate(_p, _b) -> GateSummary:
    return GateSummary(results=(GateResult("all", GateOutcome.PASS, "ok"),))


def _owner_grant():
    ch = create_challenge("grant_autonomy_charter", risk_class="RC3")
    return authorize_challenge(ch, ch.required_phrase)


def _controller(tmp_path, repo, *, canary=None):
    store = SnapshotStore(tmp_path / "rf.sqlite3")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    charters = CharterBook(path=tmp_path / "charters.jsonl")
    champions = ChampionStore(store=store, ledger=ledger)
    head = current_head(repo)
    champions.freeze(
        Champion.make(domain_scores=_full(0.85), composite=0.85, rollback_handle=head),
        reason="seed",
    )
    charters.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=5,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=_owner_grant(),
        persist=False,
    )
    controller = AutonomyController(
        charter_book=charters,
        champion_store=champions,
        proposal_book=ProposalBook(),
        ledger=ledger,
        monitor=AlignmentMonitor(ledger=ledger, charter_book=charters),
        applier=GitApplier(repo),
        rollback=GitRollback(repo),
        canary=canary,
        gate_runner=_pass_gate,
    )
    return controller, champions, ledger


def _candidate(**over):
    base = dict(
        candidate_id="cand1",
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/foo/SKILL.md",
        risk_class="RC1",
        domain_scores=_full(0.92),
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
        diff_text="# improved skill\nbetter content\n",
    )
    base.update(over)
    return Candidate(**base)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def _eval(controller, cand):
    bundle = GuardrailEvidenceBundle(packet_id=cand.candidate_id)
    return controller.evaluate_and_apply(
        cand, evidence_bundle=bundle, packet={"packet_id": cand.candidate_id}
    )


def test_live_git_apply_commits_the_change(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    controller, champions, _ = _controller(tmp_path, repo)
    before = current_head(repo)
    out = _eval(controller, _candidate())
    assert out.decision == "auto_applied"
    assert out.applied is True
    # The file exists on disk and a new commit was created.
    assert (repo / "skills" / "foo" / "SKILL.md").read_text(encoding="utf-8").startswith("# improved")
    assert current_head(repo) != before
    assert champions.current().rollback_handle == current_head(repo)


def test_live_git_canary_regression_rolls_back(tmp_path) -> None:
    repo = tmp_path / "repo"
    seed = _init_repo(repo)
    # Canary reports a regression vs the prior champion (0.85).
    regressed = {**_full(0.92), "reasoning": 0.70}
    controller, champions, ledger = _controller(
        tmp_path, repo, canary=lambda _c: {"domain_scores": regressed}
    )
    out = _eval(controller, _candidate())
    assert out.decision == "rolled_back"
    assert out.rolled_back is True
    # Real git rollback: tree is back at the seed commit, the file is gone.
    assert current_head(repo) == seed
    assert not (repo / "skills" / "foo" / "SKILL.md").exists()
    assert champions.current().rollback_handle == seed
    assert "auto_rollback" in [r.kind for r in ledger.read_all()]


def test_applier_refuses_protected_path(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    applier = GitApplier(repo)
    cand = _candidate(
        target_path="muse_cli/jarvis_prime/gates.py", diff_text="x = 1\n"
    )
    with pytest.raises(ApplyRefused):
        applier(cand)


def test_applier_refuses_path_escape(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    applier = GitApplier(repo)
    cand = _candidate(target_path="../outside.txt", diff_text="x\n")
    with pytest.raises(ApplyRefused):
        applier(cand)
