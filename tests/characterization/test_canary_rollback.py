"""Governance regression: the canary auto-rollback path must stay exercised.

WHY THIS FILE EXISTS
====================

The recorded self-improvement run this descends from went:

    candidate auto-applied -> champion frozen to the candidate
        -> ``code_editing`` canary scored 0.0
        -> automatic rollback -> previous handle restored

A self-improvement architecture that can only *promote* is unsafe. The
rollback leg is the half of the loop that nobody exercises by accident: a
healthy system almost never takes it, so it can rot silently and nothing
notices until the one run that needed it. A diagram that says "and then it
rolls back" is worth much less than a test that drives a candidate all the
way through the revert and checks the previous handle came back.

So this file drives the real
:class:`~hermes_cli.jarvis_prime.research_fabric.controller.AutonomyController`
through the recorded sequence and asserts the whole contract, and then —
because a governance test that cannot fail is decoration — it *breaks
rollback in memory three different ways* and proves the same assertions
catch each one:

* ``rollback`` unwired          -> the tree is never reverted;
* the canary can only pass      -> a controller that can only promote;
* the absolute-floor check gone -> a 0.0 canary promoted on cold start.

Every mutation test asserts the shared
:func:`assert_rollback_governance_held` helper *raises*, which is the same
helper the positive test calls. That is the proof that the positive test is
load-bearing rather than incidental.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from hermes_cli.jarvis_prime.gates import GateOutcome, GateResult, GateSummary
from hermes_cli.jarvis_prime.guardrail_evidence import (
    GuardrailEvidenceBundle,
    GuardrailLedger,
)
from hermes_cli.jarvis_prime.owner_auth import authorize_challenge, create_challenge
from hermes_cli.jarvis_prime.self_update import ProposalBook, ProposalKind
from hermes_cli.jarvis_prime.research_fabric import apply as apply_module
from hermes_cli.jarvis_prime.research_fabric import auto_apply
from hermes_cli.jarvis_prime.research_fabric.apply import GitApplier, GitRollback
from hermes_cli.jarvis_prime.research_fabric.catalog import (
    ABSOLUTE_FLOOR,
    REQUIRED_DOMAINS,
)
from hermes_cli.jarvis_prime.research_fabric.champion import Champion, ChampionStore
from hermes_cli.jarvis_prime.research_fabric.charter import CharterBook
from hermes_cli.jarvis_prime.research_fabric.controller import (
    AutoApplyOutcome,
    AutonomyController,
)
from hermes_cli.jarvis_prime.research_fabric.monitor import AlignmentMonitor
from hermes_cli.jarvis_prime.research_fabric.store import SnapshotStore
from hermes_cli.jarvis_prime.research_fabric.verifier import Candidate

# The recorded run's regressed domain and score.
CANARY_ZERO_DOMAIN = "code_editing"
CANARY_ZERO_SCORE = 0.0

# The handle the previous champion owned, i.e. what "previous handle
# restored" has to mean at the end of the run.
PREVIOUS_HANDLE = "champion-sha-before"


def _all_domains(value: float) -> dict[str, float]:
    return {d: value for d in REQUIRED_DOMAINS}


def _owner_grant():
    challenge = create_challenge("grant_autonomy_charter", risk_class="RC3")
    return authorize_challenge(challenge, challenge.required_phrase)


@dataclass
class Rig:
    """One fully wired controller plus the side-effect recorders."""

    controller: AutonomyController
    champions: ChampionStore
    ledger: GuardrailLedger
    charters: CharterBook
    applied: list[str] = field(default_factory=list)
    rolled_back: list[str] = field(default_factory=list)
    champion_seen_by_canary: list[Optional[Champion]] = field(default_factory=list)


def _build_rig(
    tmp_path,
    *,
    initial_champion: Optional[Champion],
    canary_scores: dict[str, float],
    wire_rollback: bool = True,
) -> Rig:
    store = SnapshotStore(tmp_path / "rf.sqlite3")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    charters = CharterBook(path=tmp_path / "charters.jsonl")
    champions = ChampionStore(store=store, ledger=ledger)
    proposals = ProposalBook()
    monitor = AlignmentMonitor(ledger=ledger, charter_book=charters)

    if initial_champion is not None:
        champions.freeze(initial_champion, reason="seed")

    charters.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=_owner_grant(),
        persist=False,
    )

    rig = Rig(
        controller=None,  # type: ignore[arg-type]  # filled in below
        champions=champions,
        ledger=ledger,
        charters=charters,
    )

    def applier(cand: Candidate) -> str:
        rig.applied.append(cand.candidate_id)
        return f"applied-{cand.candidate_id}"

    def canary(_cand: Candidate) -> dict[str, Any]:
        # Snapshot the champion the moment the canary runs: the recorded run
        # had the champion already frozen to the candidate at this point.
        rig.champion_seen_by_canary.append(champions.current())
        return {"domain_scores": dict(canary_scores)}

    def rollback(handle: str) -> None:
        rig.rolled_back.append(handle)

    def gate_runner(_packet: Any, _bundle: Any) -> GateSummary:
        return GateSummary(results=(GateResult("all", GateOutcome.PASS, "test rig"),))

    rig.controller = AutonomyController(
        charter_book=charters,
        champion_store=champions,
        proposal_book=proposals,
        ledger=ledger,
        monitor=monitor,
        applier=applier,
        canary=canary,
        rollback=rollback if wire_rollback else None,
        gate_runner=gate_runner,
    )
    return rig


def _promotable_candidate(**over: Any) -> Candidate:
    """A candidate that clears the ratchet and every gate.

    It has to genuinely pass, otherwise the run never reaches the canary and
    the test would be proving something else entirely.
    """
    base: dict[str, Any] = dict(
        candidate_id="cand-canary-zero",
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/foo/SKILL.md",
        risk_class="RC1",
        domain_scores=_all_domains(0.92),
        holdout_scores=_all_domains(0.92),
        eval_win_rate=0.60,
        rollback_handle="candidate-parent-sha",
    )
    base.update(over)
    return Candidate(**base)


def _evaluate(rig: Rig, candidate: Candidate):
    bundle = GuardrailEvidenceBundle(packet_id=candidate.candidate_id)
    return rig.controller.evaluate_and_apply(
        candidate,
        evidence_bundle=bundle,
        packet={"packet_id": candidate.candidate_id},
    )


def _canary_zero_on_code_editing() -> dict[str, float]:
    return {**_all_domains(0.92), CANARY_ZERO_DOMAIN: CANARY_ZERO_SCORE}


def _champion_before() -> Champion:
    return Champion.make(
        domain_scores=_all_domains(0.85),
        composite=0.85,
        rollback_handle=PREVIOUS_HANDLE,
        note="the champion the run must come back to",
    )


# ---------------------------------------------------------------------------
# The governance contract, in one place
# ---------------------------------------------------------------------------


def assert_rollback_governance_held(
    outcome,
    rig: Rig,
    *,
    expected_handle: str,
    regressed_domain: str = CANARY_ZERO_DOMAIN,
) -> None:
    """Assert the full §10/§11 rollback contract.

    Called by the positive test *and* by every mutation test (which assert it
    raises). Every clause below is load-bearing:

    1. the candidate really was applied, then really was reverted;
    2. the revert callable was invoked with the previous handle — a decision
       string saying "rolled_back" while the tree is untouched is worthless;
    3. the ledger records the apply *before* the rollback, so replay
       reconstructs the order of events;
    4. the rollback record names the regressed domain, the restored handle
       and the canary scores, so the reason survives; and
    5. the ledger's hash chain still verifies afterwards.
    """
    assert outcome.decision == "rolled_back", (
        f"expected an automatic rollback, got decision={outcome.decision!r}"
    )
    assert outcome.applied is True, "the candidate was never applied"
    assert outcome.rolled_back is True
    assert outcome.rollback_handle == expected_handle

    # (2) the revert actually ran against the previous handle.
    assert rig.rolled_back == [expected_handle], (
        f"rollback callable received {rig.rolled_back!r}, expected [{expected_handle!r}]"
    )

    records = rig.ledger.read_all()
    kinds = [r.kind for r in records]
    assert "auto_apply" in kinds, "no auto_apply recorded"
    assert "auto_rollback" in kinds, "no auto_rollback recorded"
    assert kinds.index("auto_apply") < kinds.index("auto_rollback"), (
        "the ledger does not record apply-then-rollback in order"
    )

    rollback_record = [r for r in records if r.kind == "auto_rollback"][-1]
    payload = rollback_record.payload
    assert payload["restored_handle"] == expected_handle
    assert payload["canary_scores"][regressed_domain] == pytest.approx(CANARY_ZERO_SCORE)
    assert regressed_domain in payload["reason"], (
        f"the rollback reason does not name {regressed_domain!r}: {payload['reason']!r}"
    )

    assert rig.ledger.verify_chain().ok is True, "ledger chain broken by the rollback"


# ---------------------------------------------------------------------------
# The recorded run
# ---------------------------------------------------------------------------


def test_recorded_canary_zero_rolls_back_and_restores_the_previous_handle(tmp_path) -> None:
    """The recorded sequence, end to end, against the real controller."""
    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_canary_zero_on_code_editing(),
    )

    outcome = _evaluate(rig, _promotable_candidate())

    # The candidate really was auto-applied first — this is not a pre-emptive
    # refusal dressed up as a rollback.
    assert rig.applied == ["cand-canary-zero"]

    assert_rollback_governance_held(outcome, rig, expected_handle=PREVIOUS_HANDLE)

    # And the previous champion is the current champion again.
    restored = rig.champions.current()
    assert restored is not None
    assert restored.rollback_handle == PREVIOUS_HANDLE
    assert restored.domain_scores == _all_domains(0.85)


def test_champion_is_frozen_to_the_candidate_before_the_canary_runs(tmp_path) -> None:
    """'candidate auto-applied, champion frozen' is a real intermediate state.

    The canary must run against the *promoted* champion, otherwise it is not
    canarying the change at all.
    """
    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_canary_zero_on_code_editing(),
    )

    _evaluate(rig, _promotable_candidate())

    assert len(rig.champion_seen_by_canary) == 1
    mid_flight = rig.champion_seen_by_canary[0]
    assert mid_flight is not None
    assert mid_flight.rollback_handle == "applied-cand-canary-zero", (
        "the champion was not frozen to the candidate before the canary ran"
    )
    assert mid_flight.domain_scores == _all_domains(0.92)

    # The freeze is on the ledger between the apply and the rollback.
    kinds = [r.kind for r in rig.ledger.read_all()]
    freeze_positions = [i for i, k in enumerate(kinds) if k == "champion_freeze"]
    assert kinds.index("auto_apply") < max(freeze_positions)
    assert any(
        kinds.index("auto_apply") < i < kinds.index("auto_rollback")
        for i in freeze_positions
    ), "no champion_freeze recorded between auto_apply and auto_rollback"


def test_a_canary_at_zero_is_below_the_absolute_floor(tmp_path) -> None:
    """Pin why 0.0 triggers the revert, so the threshold cannot silently move."""
    assert CANARY_ZERO_SCORE < ABSOLUTE_FLOOR
    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_canary_zero_on_code_editing(),
    )
    outcome = _evaluate(rig, _promotable_candidate())
    assert "below floor" in outcome.rationale, outcome.rationale


def test_a_clean_canary_promotes_so_the_rollback_test_is_not_vacuous(tmp_path) -> None:
    """The same rig with a healthy canary must auto-apply and stay applied.

    Without this, a controller that rolled back *everything* would satisfy the
    rollback test while being just as broken as one that never rolls back.
    """
    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_all_domains(0.92),
    )

    outcome = _evaluate(rig, _promotable_candidate())

    assert outcome.decision == "auto_applied"
    assert outcome.rolled_back is False
    assert rig.rolled_back == []
    champ = rig.champions.current()
    assert champ is not None
    assert champ.rollback_handle == "applied-cand-canary-zero"


def test_cold_start_rollback_reverts_the_tree_to_the_candidate_parent(tmp_path) -> None:
    """With no prior champion the revert target is the candidate's parent.

    Characterized limitation, recorded rather than asserted as correct: the
    controller only restores a *previous* champion record when one existed
    (``controller.py``: ``if prev_champion is not None``). On cold start the
    working tree is reverted but the champion store still names the
    rolled-back candidate. The tree and the champion record therefore
    disagree until the next freeze. This test documents that gap; it does not
    endorse it.
    """
    rig = _build_rig(
        tmp_path,
        initial_champion=None,
        canary_scores=_canary_zero_on_code_editing(),
    )

    outcome = _evaluate(rig, _promotable_candidate())

    assert_rollback_governance_held(
        outcome, rig, expected_handle="candidate-parent-sha"
    )

    still_the_candidate = rig.champions.current()
    assert still_the_candidate is not None
    assert still_the_candidate.rollback_handle == "applied-cand-canary-zero", (
        "cold-start behaviour changed — the champion record now tracks the revert"
    )


# ---------------------------------------------------------------------------
# Mutation proofs: break rollback in memory, show the contract catches it
# ---------------------------------------------------------------------------


def test_mutation_unwired_rollback_is_caught(tmp_path) -> None:
    """Remove the revert wiring: the decision still says 'rolled_back'.

    This is the nastiest failure mode, because every log line and the outcome
    object keep claiming a rollback happened while the applied change is
    still in the tree. Only the assertion that the revert *callable ran*
    catches it.
    """
    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_canary_zero_on_code_editing(),
        wire_rollback=False,
    )

    outcome = _evaluate(rig, _promotable_candidate())

    assert outcome.decision == "rolled_back"      # still claims it
    assert rig.rolled_back == []                  # but nothing was reverted

    with pytest.raises(AssertionError, match="rollback callable received"):
        assert_rollback_governance_held(outcome, rig, expected_handle=PREVIOUS_HANDLE)


def test_mutation_controller_that_can_only_promote_is_caught(
    tmp_path, monkeypatch
) -> None:
    """Neuter the canary verdict so nothing ever regresses.

    This is the §10/§11 failure the item is named for: a self-improvement
    architecture that can only promote.
    """
    monkeypatch.setattr(
        AutonomyController,
        "_canary_regressed",
        lambda self, prev, scores: (False, "canary stable"),
    )

    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_canary_zero_on_code_editing(),
    )

    outcome = _evaluate(rig, _promotable_candidate())

    # A 0.0 canary was promoted.
    assert outcome.decision == "auto_applied"
    assert rig.champions.current().rollback_handle == "applied-cand-canary-zero"

    with pytest.raises(AssertionError, match="expected an automatic rollback"):
        assert_rollback_governance_held(outcome, rig, expected_handle=PREVIOUS_HANDLE)


def test_mutation_dropping_the_absolute_floor_check_is_caught(
    tmp_path, monkeypatch
) -> None:
    """Keep only the 'worse than the prior champion' comparison.

    On cold start there is no prior champion to compare against, so a canary
    score of 0.0 sails through. The floor is the only thing standing between
    a first-ever candidate and an unconditional promotion.
    """

    def floorless(self, prev, canary_scores):
        for domain in REQUIRED_DOMAINS:
            score = canary_scores.get(domain)
            if score is None:
                return True, f"canary missing domain '{domain}'"
            if prev is not None:
                base = prev.domain_scores.get(domain)
                if base is not None and score < base:
                    return True, f"canary '{domain}' regressed vs prior champion"
        return False, "canary stable"

    monkeypatch.setattr(AutonomyController, "_canary_regressed", floorless)

    rig = _build_rig(
        tmp_path,
        initial_champion=None,
        canary_scores=_canary_zero_on_code_editing(),
    )

    outcome = _evaluate(rig, _promotable_candidate())

    assert outcome.decision == "auto_applied", "the floorless mutation did not promote"
    assert rig.rolled_back == []

    with pytest.raises(AssertionError, match="expected an automatic rollback"):
        assert_rollback_governance_held(
            outcome, rig, expected_handle="candidate-parent-sha"
        )


def test_mutation_rollback_reason_stripped_from_the_ledger_is_caught(
    tmp_path, monkeypatch
) -> None:
    """A rollback that reverts but records no reason is still a regression.

    Replay has to be able to reconstruct *why* the revert happened; §10/§11
    treat the ledger record as part of the rollback, not as commentary.
    """
    rig = _build_rig(
        tmp_path,
        initial_champion=_champion_before(),
        canary_scores=_canary_zero_on_code_editing(),
    )

    real_append: Callable[..., Any] = rig.ledger.append

    def forgetful(kind: str, subject: str, payload):
        if kind == "auto_rollback":
            payload = {**dict(payload), "reason": "rolled back"}
        return real_append(kind, subject, payload)

    monkeypatch.setattr(rig.ledger, "append", forgetful)

    outcome = _evaluate(rig, _promotable_candidate())

    assert outcome.decision == "rolled_back"
    assert rig.rolled_back == [PREVIOUS_HANDLE]   # the revert itself is fine

    with pytest.raises(AssertionError, match="does not name"):
        assert_rollback_governance_held(outcome, rig, expected_handle=PREVIOUS_HANDLE)


# ---------------------------------------------------------------------------
# The shipping path: does production actually wire a rollback in?
# ---------------------------------------------------------------------------
#
# Everything above drives a controller this file builds itself, so it proves
# the controller *can* roll back. It says nothing about whether the code that
# actually runs in production hands it a revert callable. Delete
# ``rollback=GitRollback(repo)`` from
# ``research_fabric/auto_apply.py::drive_candidate`` and every test above
# still passes while the shipping path silently becomes promote-only — the
# exact §10/§11 failure, one line away and undetected.
#
# These tests close that hole. No git command runs: the branch checkout, the
# HEAD read and the controller are all replaced. What is left executing is
# the real ``drive_candidate`` body, which is precisely the code that decides
# what governance the shipping path installs.


def _drive_candidate_capturing(tmp_path, monkeypatch) -> tuple[Path, dict[str, Any]]:
    """Run the real ``drive_candidate`` and capture the controller's kwargs."""
    repo = tmp_path / "fake_repo"
    # drive_candidate refuses a non-worktree; a bare directory satisfies the
    # check without `git init` ever running.
    (repo / ".git").mkdir(parents=True)

    captured: dict[str, Any] = {}

    class ControllerSpy:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def evaluate_and_apply(self, candidate, **_kw: Any) -> AutoApplyOutcome:
            return AutoApplyOutcome(
                decision="rolled_back",
                applied=True,
                rolled_back=True,
                ratchet=None,
                gate_overall="PASS",
                capability_ok=True,
                charter_id="charter-spy",
                proposal=None,
                rollback_handle=PREVIOUS_HANDLE,
                tripwire=None,
                ledger_record_hash="0" * 64,
                rationale=(
                    f"canary '{CANARY_ZERO_DOMAIN}' below floor: "
                    f"{CANARY_ZERO_SCORE:.4f}"
                ),
            )

    monkeypatch.setattr(auto_apply, "AutonomyController", ControllerSpy)
    monkeypatch.setattr(
        auto_apply, "_ensure_autonomy_branch", lambda _repo, _cid: "autonomy/spy"
    )
    monkeypatch.setattr(auto_apply, "current_head", lambda _repo: "0" * 40)

    auto_apply.drive_candidate(
        repo,
        _promotable_candidate(),
        packet={"packet_id": "spy"},
        evidence_bundle=GuardrailEvidenceBundle(packet_id="spy"),
    )
    return repo, captured


def assert_production_wires_a_rollback(repo: Path, captured: dict[str, Any]) -> None:
    """The shipping controller must be constructed with a working revert."""
    rollback = captured.get("rollback")
    assert rollback is not None, (
        "auto_apply.drive_candidate built the AutonomyController with no "
        "rollback — the shipping self-improvement path can only promote"
    )
    assert isinstance(rollback, GitRollback), (
        f"rollback is {type(rollback).__name__}, not a real GitRollback"
    )
    assert callable(rollback)
    assert Path(rollback.repo_root).resolve() == Path(repo).resolve(), (
        "the rollback is bound to a different worktree than the applier"
    )


def test_production_auto_apply_wires_a_real_rollback(tmp_path, monkeypatch) -> None:
    repo, captured = _drive_candidate_capturing(tmp_path, monkeypatch)

    assert_production_wires_a_rollback(repo, captured)

    # "a rollback is wired" is only meaningful if something can be applied and
    # something can regress, so pin the other two legs of the loop as well.
    applier = captured.get("applier")
    assert isinstance(applier, GitApplier), "no real GitApplier was wired"
    assert Path(applier.repo_root).resolve() == Path(repo).resolve()
    assert callable(captured.get("canary")), "no canary was wired"


def test_mutation_production_rollback_removed_is_caught(tmp_path, monkeypatch) -> None:
    """Delete the revert from the shipping wiring; the assertion must catch it.

    ``GitRollback`` is replaced by a factory returning ``None``, which is what
    ``rollback=None`` (or a deleted keyword) produces at the call site.
    """
    monkeypatch.setattr(auto_apply, "GitRollback", lambda _repo_root: None)

    repo, captured = _drive_candidate_capturing(tmp_path, monkeypatch)

    assert captured["rollback"] is None            # the mutation took effect
    assert isinstance(captured["applier"], GitApplier)   # apply still works

    with pytest.raises(AssertionError, match="no rollback"):
        assert_production_wires_a_rollback(repo, captured)


def test_git_rollback_refuses_an_empty_handle_without_touching_git(monkeypatch) -> None:
    """The real ``GitRollback`` guard clause, exercised without running git.

    ``reset --hard ''`` would be a destructive no-target reset, so the empty
    handle has to short-circuit. This is the one part of the production
    revert that can be tested directly here — the ``git reset --hard`` branch
    itself needs a real worktree and is deliberately not driven from a test.
    """

    def refuse(*_a: Any, **_k: Any):
        raise AssertionError("GitRollback ran a git command for an empty handle")

    monkeypatch.setattr(apply_module, "_git", refuse)

    revert = GitRollback(Path("."))
    assert revert("") is None
    assert revert(None) is None  # type: ignore[arg-type]
