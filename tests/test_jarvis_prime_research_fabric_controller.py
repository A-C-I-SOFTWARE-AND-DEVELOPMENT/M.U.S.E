"""Tests for the AutonomyController — the full bounded auto-apply envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from muse_cli.jarvis_prime.gates import GateOutcome, GateResult, GateSummary
from muse_cli.jarvis_prime.guardrail_evidence import (
    GuardrailEvidenceBundle,
    GuardrailLedger,
)
from muse_cli.jarvis_prime.owner_auth import authorize_challenge, create_challenge
from muse_cli.jarvis_prime.self_update import ProposalBook, ProposalKind, ProposalStatus
from muse_cli.jarvis_prime.research_fabric.catalog import REQUIRED_DOMAINS
from muse_cli.jarvis_prime.research_fabric.champion import Champion, ChampionStore
from muse_cli.jarvis_prime.research_fabric.charter import CharterBook
from muse_cli.jarvis_prime.research_fabric.controller import AutonomyController
from muse_cli.jarvis_prime.research_fabric.monitor import AlignmentMonitor
from muse_cli.jarvis_prime.research_fabric.store import SnapshotStore
from muse_cli.jarvis_prime.research_fabric.verifier import Candidate


def _full(value: float) -> dict[str, float]:
    return {d: value for d in REQUIRED_DOMAINS}


def _gate_runner(outcome: GateOutcome) -> Callable[..., GateSummary]:
    def run(_packet: Any, _bundle: Any) -> GateSummary:
        return GateSummary(results=(GateResult("all", outcome, "fake"),))

    return run


def _owner_grant():
    ch = create_challenge("grant_autonomy_charter", risk_class="RC3")
    return authorize_challenge(ch, ch.required_phrase)


@dataclass
class Rig:
    controller: AutonomyController
    charters: CharterBook
    champions: ChampionStore
    proposals: ProposalBook
    ledger: GuardrailLedger
    applied: list[str]
    rolled_back: list[str]


def _make_rig(
    tmp_path,
    *,
    with_charter: bool = True,
    gate_outcome: GateOutcome = GateOutcome.PASS,
    initial_champion: Optional[Champion] = None,
    canary_scores: Optional[dict[str, float]] = None,
    budget: int = 3,
    ceiling: str = "RC2",
    allowed_kinds: tuple[str, ...] = ("skill_update",),
) -> Rig:
    store = SnapshotStore(tmp_path / "rf.sqlite3")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    charters = CharterBook(path=tmp_path / "charters.jsonl")
    champions = ChampionStore(store=store, ledger=ledger)
    proposals = ProposalBook()
    monitor = AlignmentMonitor(ledger=ledger, charter_book=charters)

    if initial_champion is not None:
        champions.freeze(initial_champion, reason="seed")

    if with_charter:
        charters.grant(
            allowed_kinds=allowed_kinds,
            risk_band_ceiling=ceiling,
            per_window_budget=budget,
            window_seconds=86400,
            ttl_seconds=3600,
            grant=_owner_grant(),
            persist=False,
        )

    applied: list[str] = []
    rolled_back: list[str] = []

    def applier(cand: Candidate) -> str:
        applied.append(cand.candidate_id)
        return f"applied-{cand.candidate_id}"

    def canary(_cand: Candidate) -> dict[str, Any]:
        return {"domain_scores": canary_scores if canary_scores is not None else _full(0.92)}

    def rollback(handle: str) -> None:
        rolled_back.append(handle)

    controller = AutonomyController(
        charter_book=charters,
        champion_store=champions,
        proposal_book=proposals,
        ledger=ledger,
        monitor=monitor,
        applier=applier,
        canary=canary,
        rollback=rollback,
        gate_runner=_gate_runner(gate_outcome),
    )
    return Rig(controller, charters, champions, proposals, ledger, applied, rolled_back)


def _candidate(**over: Any) -> Candidate:
    base: dict[str, Any] = dict(
        candidate_id="cand1",
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/foo/SKILL.md",
        risk_class="RC1",
        domain_scores=_full(0.92),
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
    )
    base.update(over)
    return Candidate(**base)


def _eval(rig: Rig, cand: Candidate):
    bundle = GuardrailEvidenceBundle(packet_id=cand.candidate_id)
    return rig.controller.evaluate_and_apply(
        cand, evidence_bundle=bundle, packet={"packet_id": cand.candidate_id}
    )


def _champ85() -> Champion:
    return Champion.make(domain_scores=_full(0.85), composite=0.85, rollback_handle="base-sha")


def test_auto_apply_inside_charter(tmp_path) -> None:
    rig = _make_rig(tmp_path, initial_champion=_champ85())
    out = _eval(rig, _candidate())
    assert out.decision == "auto_applied"
    assert out.applied is True and out.rolled_back is False
    assert rig.applied == ["cand1"]
    # New champion frozen.
    assert rig.champions.current() is not None
    assert rig.champions.current().composite >= 0.92  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    kinds = [r.kind for r in rig.ledger.read_all()]
    assert "auto_apply" in kinds


def test_no_charter_falls_back_to_proposal(tmp_path) -> None:
    rig = _make_rig(tmp_path, with_charter=False, initial_champion=_champ85())
    out = _eval(rig, _candidate())
    assert out.decision == "proposed"
    assert out.applied is False
    assert out.proposal is not None
    assert out.proposal.status is ProposalStatus.NEEDS_OWNER_APPROVAL
    assert rig.applied == []


def test_hard_wall_kind_never_auto_applies(tmp_path) -> None:
    # A normal skill-only charter is active; a self-runtime candidate must still
    # be hard-walled by the controller regardless (C34).
    rig = _make_rig(tmp_path, initial_champion=_champ85())
    out = _eval(
        rig,
        _candidate(kind=ProposalKind.SELF_RUNTIME_UPDATE, target_path="muse_cli/jarvis_prime/x.py"),
    )
    assert out.decision == "proposed"
    assert out.applied is False
    assert out.proposal.risk_class == "RC4"
    assert rig.applied == []


def test_constitution_path_never_auto_applies(tmp_path) -> None:
    rig = _make_rig(tmp_path, initial_champion=_champ85())
    out = _eval(rig, _candidate(target_path="muse_cli/jarvis_prime/constitution.py"))
    assert out.decision == "proposed"
    assert out.applied is False


def test_ratchet_failure_blocks_with_no_proposal(tmp_path) -> None:
    rig = _make_rig(tmp_path, initial_champion=_champ85())
    cand = _candidate(domain_scores={**_full(0.92), "safety": 0.80})  # regressed safety
    out = _eval(rig, cand)
    assert out.decision == "blocked"
    assert out.applied is False
    assert out.proposal is None
    assert "ratchet_block" in [r.kind for r in rig.ledger.read_all()]


def test_gates_fail_blocks(tmp_path) -> None:
    rig = _make_rig(tmp_path, gate_outcome=GateOutcome.FAIL, initial_champion=_champ85())
    out = _eval(rig, _candidate())
    assert out.decision == "blocked"
    assert out.applied is False


def test_gates_need_owner_falls_back_to_proposal(tmp_path) -> None:
    rig = _make_rig(
        tmp_path, gate_outcome=GateOutcome.NEEDS_OWNER_APPROVAL, initial_champion=_champ85()
    )
    out = _eval(rig, _candidate())
    assert out.decision == "proposed"
    assert out.proposal is not None


def test_risk_above_ceiling_falls_back_to_proposal(tmp_path) -> None:
    rig = _make_rig(tmp_path, ceiling="RC1", initial_champion=_champ85())
    out = _eval(rig, _candidate(risk_class="RC2"))  # exceeds RC1 ceiling
    assert out.decision == "proposed"
    assert out.applied is False


def test_budget_exhaustion_falls_back_to_proposal(tmp_path) -> None:
    rig = _make_rig(tmp_path, budget=1, initial_champion=_champ85())
    charter = rig.charters.active()
    # Simulate one prior auto-apply in the window.
    rig.ledger.append("auto_apply", "prior", {"charter_id": charter.charter_id})  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    out = _eval(rig, _candidate())
    assert out.decision == "proposed"
    assert "budget" in out.rationale


def test_canary_regression_triggers_rollback(tmp_path) -> None:
    # Canary returns a regressed score vs the prior champion (0.85).
    regressed = {**_full(0.92), "reasoning": 0.80}
    rig = _make_rig(tmp_path, initial_champion=_champ85(), canary_scores=regressed)
    out = _eval(rig, _candidate())
    assert out.decision == "rolled_back"
    assert out.applied is True and out.rolled_back is True
    assert rig.rolled_back == ["base-sha"]
    kinds = [r.kind for r in rig.ledger.read_all()]
    assert "auto_rollback" in kinds
    # Prior champion restored.
    assert rig.champions.current().rollback_handle == "base-sha"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


def test_reward_hacking_candidate_trips_and_halts(tmp_path) -> None:
    rig = _make_rig(tmp_path, initial_champion=_champ85())
    out = _eval(rig, _candidate(diff_text="def test_x():\n    assert True\n"))
    assert out.decision == "blocked"
    assert out.tripwire is not None
    # Tripwire revokes the charter -> autonomy halted.
    assert rig.charters.active() is None


def test_ledger_chain_intact_after_runs(tmp_path) -> None:
    rig = _make_rig(tmp_path, initial_champion=_champ85())
    _eval(rig, _candidate())
    assert rig.ledger.verify_chain().ok is True
