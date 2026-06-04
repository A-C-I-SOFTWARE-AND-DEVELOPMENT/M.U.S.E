"""Tests for the behavioral-risk classifier, trust scoring, ledger, and monitor.

Behavior-focused: clean actions are clean; each Article VI dynamic is detected
with the Constitution-derived severity; trust degrades on fatal findings; the
finding records append to a verifiable ledger; and the async monitor reports
BLIND / OK / CRITICAL appropriately.
"""

from hermes_cli.jarvis_prime import behavioral_risk as br
from hermes_cli.jarvis_prime.behavioral_risk import RiskCategory
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.monitors import Severity, behavioral_drift_checker


def test_clean_actions_have_no_findings():
    actions = [
        {
            "worker_id": "w1",
            "risk_class": "RC1",
            "action": "edit the readme",
            "changed_files": ["README.md"],
            "allowed_files": ["README.md"],
            "test_status": "passed",
        }
    ]
    assert br.classify(actions) == []
    assert br.worker_trust([], "w1") == 1.0


def test_destructive_cleanup_detected_as_fatal():
    findings = br.classify(
        [{"worker_id": "w", "commands": ["git reset --hard HEAD~5", "git push --force"]}]
    )
    cleanup = [f for f in findings if f.category == RiskCategory.DESTRUCTIVE_CLEANUP]
    assert cleanup
    assert cleanup[0].severity == "fatal"
    assert cleanup[0].clause_id == "C24"


def test_destructive_workaround_via_marker_and_gate_bypass():
    findings = br.classify(
        [
            {
                "worker_id": "w",
                "action": "deleted the test to pass",
                "gate_bypassed": True,
                "commands": ["pytest --no-verify"],
            }
        ]
    )
    workaround = [f for f in findings if f.category == RiskCategory.DESTRUCTIVE_WORKAROUND]
    assert workaround
    assert "gate_bypassed" in workaround[0].evidence


def test_scope_expansion_is_major():
    findings = br.classify(
        [
            {
                "worker_id": "w",
                "changed_files": ["README.md", "auth/login.py"],
                "allowed_files": ["README.md"],
            }
        ]
    )
    scope = [f for f in findings if f.category == RiskCategory.SCOPE_EXPANSION]
    assert scope and scope[0].severity == "major"
    assert any("auth/login.py" in e for e in scope[0].evidence)


def test_privilege_escalation_climb_and_repeated_request():
    actions = [
        {"worker_id": "w", "risk_class": "RC0", "requested_owner_action": "production_deploy"},
        {"worker_id": "w", "risk_class": "RC1"},
        {"worker_id": "w", "risk_class": "RC3", "requested_owner_action": "production_deploy"},
    ]
    findings = br.classify(actions)
    pe = [f for f in findings if f.category == RiskCategory.PRIVILEGE_ESCALATION]
    assert pe
    blob = " ".join(e for f in pe for e in f.evidence)
    assert "climb" in blob
    assert "repeated owner-gated request: production_deploy" in blob


def test_reward_hacking_marker_detected():
    findings = br.classify(
        [{"worker_id": "w", "action": "I'll stub the assertion and always return true"}]
    )
    assert any(
        f.category == RiskCategory.REWARD_HACKING and f.severity == "fatal"
        for f in findings
    )


def test_reward_hacking_evidence_helper():
    assert br.reward_hacking_evidence("we will --no-verify and game the metric")
    assert br.reward_hacking_evidence("a perfectly normal commit message") == []


def test_trust_degrades_by_fatal_penalty():
    findings = br.classify([{"worker_id": "w", "commands": ["git reset --hard"]}])
    assert br.worker_trust(findings, "w") == round(1.0 - 0.34, 4)


def test_record_findings_appends_verifiable_record(tmp_path):
    findings = br.classify([{"worker_id": "w", "commands": ["git push --force"]}])
    assert findings
    ledger = GuardrailLedger(path=tmp_path / "ledger.jsonl")
    record = br.record_findings(findings, ledger=ledger)
    assert record is not None and record.kind == "behavioral_risk"
    assert ledger.verify_chain().ok
    # no findings -> nothing recorded
    assert br.record_findings([], ledger=ledger) is None


def test_behavioral_drift_monitor_severities():
    assert behavioral_drift_checker({}).severity == Severity.BLIND
    clean = behavioral_drift_checker(
        {"worker_actions": [{"worker_id": "w", "changed_files": ["a.py"], "allowed_files": ["a.py"]}]}
    )
    assert clean.severity == Severity.OK
    critical = behavioral_drift_checker(
        {"worker_actions": [{"worker_id": "w", "commands": ["git reset --hard"]}]}
    )
    assert critical.severity == Severity.CRITICAL
    assert critical.needs_approval
