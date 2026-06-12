from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.proposal_executor import (
    ProposalNotApproved,
    build_execution_plan,
    validate_execution_plan,
)
from muse_cli.jarvis_prime.self_update import (
    Proposal,
    ProposalKind,
    ProposalStatus,
)


def _approved_proposal(**kw) -> Proposal:
    p = Proposal(
        kind=kw.get("kind", ProposalKind.SELF_RUNTIME_UPDATE),
        target_path=kw.get("target_path", "muse_cli/jarvis_prime/router.py"),
        rationale="router missed a lane",
        diff_intent="add a fallback lane to the router",
        risk_class=kw.get("risk_class", "RC2"),
    )
    p.status = ProposalStatus.APPROVED
    return p


def test_unapproved_proposal_is_refused() -> None:
    p = Proposal(
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/x/SKILL.md",
        rationale="x",
        diff_intent="y",
    )
    with pytest.raises(ProposalNotApproved):
        build_execution_plan(p)


def test_plan_is_bounded_and_never_merges() -> None:
    plan = build_execution_plan(_approved_proposal())
    assert plan.draft_only is True
    assert plan.branch.startswith("jarvis/")
    assert plan.test_commands
    assert any("revert" in r or "drop the branch" in r for r in plan.rollback_plan)
    d = plan.to_dict()
    assert "does not merge" in str(d["warning"])


def test_plan_targets_correct_tests_for_area() -> None:
    plan = build_execution_plan(
        _approved_proposal(target_path="gateway/jarvis_local_http.py")
    )
    assert any("gateway" in c for c in plan.test_commands)


def test_plan_packet_validates() -> None:
    plan = build_execution_plan(_approved_proposal())
    result = validate_execution_plan(plan)
    assert result.ok is True


def test_high_risk_proposal_flags_owner_approval() -> None:
    plan = build_execution_plan(
        _approved_proposal(
            target_path="muse_cli/jarvis_prime/gates.py", risk_class="RC3"
        )
    )
    assert "owner_approval_required" in plan.owner_gates


def test_plan_artifact_writes_json(tmp_path) -> None:
    plan = build_execution_plan(_approved_proposal())
    path = plan.write_artifact(tmp_path)
    assert path.exists()
    assert path.suffix == ".json"
