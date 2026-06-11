"""Tests for the scaling decision tree, kill criteria, and evaluation matrix."""

from hermes_cli.jarvis_prime.federation import KIND_SCALE_RECOMMENDATION
from hermes_cli.jarvis_prime.federation.scaling import (
    EVALUATION_MATRIX,
    KILL_CRITERIA,
    MECHANISM_UNLOCKS,
    Scale,
    ScaleSignals,
    evaluate_kill_criteria,
    recommend_scale,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger


def test_default_signals_recommend_stay_solo():
    rec = recommend_scale(ScaleSignals())
    assert rec.recommended == Scale.A_SOLO
    assert any("stay solo" in step.lower() for step in rec.decision_path)
    assert rec.amendment_process == "ceremonial_phrase"
    assert not [f for f in rec.kill_findings if f.triggered]


def test_each_kill_criterion_triggers_individually_and_forces_solo():
    cases = {
        "K1": ScaleSignals(collaborator_count=3, has_proving_ground_user=False),
        "K2": ScaleSignals(
            collaborator_count=3,
            has_proving_ground_user=True,
            gates_need_constant_manual_intervention=True,
        ),
        "K3": ScaleSignals(
            seeking_funding=True,
            has_proving_ground_user=True,
            funding_term_touches_anti_goals=True,
        ),
        "K4": ScaleSignals(
            collaborator_count=2,
            has_proving_ground_user=True,
            coordination_hours_weekly=30.0,
            worker_throughput_hours_weekly=10.0,
        ),
    }
    for criterion_id, signals in cases.items():
        findings = {f.criterion_id: f.triggered for f in evaluate_kill_criteria(signals)}
        assert findings[criterion_id], criterion_id
        rec = recommend_scale(signals)
        assert rec.recommended == Scale.A_SOLO, criterion_id
        assert criterion_id in rec.decision_path[0]


def test_collaborators_recommend_team_with_parallelize():
    rec = recommend_scale(ScaleSignals(collaborator_count=3, has_proving_ground_user=True))
    assert rec.recommended == Scale.B_TEAM
    assert any("parallelize" in step.lower() for step in rec.decision_path)
    assert rec.amendment_process == "quorum"
    assert "quorum_auth" in rec.unlocked_mechanisms


def test_funding_path_demands_mission_lock_first():
    rec = recommend_scale(
        ScaleSignals(
            collaborator_count=4, has_proving_ground_user=True, seeking_funding=True
        )
    )
    assert rec.recommended == Scale.B_TEAM
    assert any("mission-lock" in step.lower() for step in rec.decision_path)


def test_community_startup_and_enterprise_branches():
    community = recommend_scale(
        ScaleSignals(community_contributors=60, has_proving_ground_user=True)
    )
    assert community.recommended == Scale.C_COMMUNITY
    startup = recommend_scale(
        ScaleSignals(collaborator_count=25, has_proving_ground_user=True)
    )
    assert startup.recommended == Scale.D_STARTUP
    enterprise = recommend_scale(
        ScaleSignals(
            collaborator_count=25,
            has_proving_ground_user=True,
            external_customers=3,
            regulated_deployment=True,
        )
    )
    assert enterprise.recommended == Scale.E_ENTERPRISE
    assert "conformity_assessment" in enterprise.unlocked_mechanisms


def test_evaluation_matrix_complete_and_in_range():
    axes = {
        "capability_ceiling",
        "governance_integrity",
        "anti_goal_resilience",
        "time_to_vision",
        "sovereignty",
    }
    assert set(EVALUATION_MATRIX) == set(Scale)
    for scale, row in EVALUATION_MATRIX.items():
        assert set(row) == axes, scale
        assert all(1 <= v <= 5 for v in row.values()), scale
    # The Vol VI reading: A and B tie at the top of the composite.
    composite = {s: sum(r.values()) for s, r in EVALUATION_MATRIX.items()}
    assert composite[Scale.A_SOLO] == composite[Scale.B_TEAM] == max(composite.values())


def test_mechanism_unlocks_are_cumulative():
    order = [Scale.A_SOLO, Scale.B_TEAM, Scale.C_COMMUNITY, Scale.D_STARTUP, Scale.E_ENTERPRISE]
    for earlier, later in zip(order, order[1:]):
        assert MECHANISM_UNLOCKS[earlier] <= MECHANISM_UNLOCKS[later]


def test_recommendation_ledgered_and_signals_round_trip(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    signals = ScaleSignals(collaborator_count=2, has_proving_ground_user=True)
    rec = recommend_scale(signals, ledger=ledger)
    records = ledger.read_all()
    assert records[-1].kind == KIND_SCALE_RECOMMENDATION
    assert records[-1].subject == rec.recommended.value
    assert ledger.verify_chain().ok
    restored = ScaleSignals.from_dict(signals.to_dict())
    assert restored == signals
    assert len(KILL_CRITERIA) == 4
