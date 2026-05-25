"""Monitor reads the audit trail and writes drafts to the drafts dir."""

from __future__ import annotations

import json
from pathlib import Path

from enterprise.audit import audit
from enterprise.monitor import review_session
from enterprise.policy import Risk


def _drafts_dir(tmp_path: Path) -> Path:
    return tmp_path / "enterprise" / "drafts"


def test_no_failures_no_proposals(audit_dir):
    audit("sess-mon-clean", "plan", "orchestrator")
    audit("sess-mon-clean", "judge", "judge", validation="ok", tool="invoice.read")
    audit("sess-mon-clean", "done", "orchestrator")
    proposals = review_session("sess-mon-clean")
    assert proposals == []


def test_schema_fail_produces_prompt_regression_proposal(audit_dir, tmp_path):
    sid = "sess-mon-schema"
    audit(sid, "plan", "orchestrator")
    audit(
        sid, "judge", "judge", validation="schema_fail", tool="finance.invoice.create"
    )
    audit(
        sid, "judge", "judge", validation="schema_fail", tool="finance.invoice.create"
    )
    audit(sid, "done", "orchestrator")

    proposals = review_session(sid, min_repeat=2)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.kind == "prompt_regression"
    assert p.target_agent == "finance"
    assert p.suggested_action == "update_skill_prompt"
    assert p.evidence_event_count == 2

    drafts = list(_drafts_dir(tmp_path).glob("*.json"))
    assert len(drafts) == 1
    on_disk = json.loads(drafts[0].read_text())
    assert on_disk["kind"] == "prompt_regression"


def test_policy_fail_produces_planning_regression_proposal(audit_dir):
    sid = "sess-mon-policy"
    audit(
        sid,
        "judge",
        "judge",
        validation="policy_fail",
        tool="hr.offer.send",
        risk=Risk.HIGH,
    )
    audit(sid, "done", "orchestrator")
    proposals = review_session(sid)
    kinds = [p.kind for p in proposals]
    assert kinds == ["planning_regression"]
    assert proposals[0].target_agent == "orchestrator"


def test_judge_disagree_produces_model_proposal(audit_dir):
    sid = "sess-mon-disagree"
    audit(
        sid, "judge", "judge", validation="judge_disagree", tool="sales.proposal.draft"
    )
    audit(
        sid, "judge", "judge", validation="judge_disagree", tool="sales.proposal.draft"
    )
    audit(sid, "done", "orchestrator")
    proposals = review_session(sid, min_repeat=2)
    assert len(proposals) == 1
    assert proposals[0].kind == "model_disagreement"
    assert proposals[0].target_agent == "judge"


def test_min_repeat_filters_one_off_blips(audit_dir):
    sid = "sess-mon-noisy"
    # Only one schema_fail — with min_repeat=2 the monitor should stay quiet.
    audit(
        sid, "judge", "judge", validation="schema_fail", tool="finance.invoice.create"
    )
    proposals = review_session(sid, min_repeat=2)
    assert proposals == []
