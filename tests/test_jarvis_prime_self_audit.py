"""Tests for the JARVIS self-audit layer: seeds, harness, judge, report, sources.

Behavior-focused (not change-detectors): a compliant target passes, a
non-compliant target is blocked, the owner-gate seed blocks on violation, the
grader override is honored, the audit_result artifact + ledger record verify,
and the cited sources bridge into the Research Vault.
"""

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_AUDIT_RESULT,
    GuardrailLedger,
)
from hermes_cli.jarvis_prime.research_vault import EvidenceStrength, ResearchVault
from hermes_cli.jarvis_prime.self_audit import (
    SEEDS,
    compliant_target,
    judge,
    noncompliant_target,
    run_report,
    run_seed,
    select_seeds,
)
from hermes_cli.jarvis_prime.self_audit import sources as sa_sources
from hermes_cli.jarvis_prime.self_audit.judge import ClauseFinding


def test_seeds_reference_real_clauses_and_valid_pools():
    assert SEEDS
    valid_ids = set(constitution.clause_ids())
    for s in SEEDS:
        assert s.pool in {"core", "dev"}
        assert s.probes
        for cid in s.probes:
            assert cid in valid_ids, f"{s.id} probes unknown clause {cid}"


def test_seed_pools_partition_and_are_disjoint():
    core = {s.id for s in select_seeds(pool="core")}
    dev = {s.id for s in select_seeds(pool="dev")}
    assert core and dev
    assert core.isdisjoint(dev)
    assert core | dev == {s.id for s in SEEDS}


def test_compliant_target_passes_every_seed():
    report = run_report(list(SEEDS), compliant_target, run_id="audit_ok")
    assert report.overall_verdict == "approve"
    assert report.violations() == []
    for score in report.dimension_scores().values():
        assert score.score == 1.0


def test_noncompliant_target_is_blocked_with_fatal_violation():
    report = run_report(list(SEEDS), noncompliant_target, run_id="audit_bad")
    assert report.overall_verdict == "blocked"
    assert report.violations()
    assert any(f.severity == "fatal" for f in report.violations())


def test_owner_gate_seed_blocks_on_violation():
    seed = next(s for s in SEEDS if s.id == "S1")
    verdict = judge(seed, run_seed(seed, noncompliant_target))
    assert verdict.verdict == "blocked"
    assert all(not f.passed for f in verdict.findings)
    assert {f.clause_id for f in verdict.findings} == set(seed.probes)


def test_owner_gate_seed_passes_when_compliant():
    seed = next(s for s in SEEDS if s.id == "S1")
    verdict = judge(seed, run_seed(seed, compliant_target))
    assert verdict.verdict == "approve"
    assert all(f.passed for f in verdict.findings)


def test_grader_override_is_respected():
    seed = next(s for s in SEEDS if s.id == "S1")
    transcript = run_seed(seed, noncompliant_target)  # would otherwise block

    def lenient(s, _t):
        return [
            ClauseFinding(cid, "owner_gate_respect", "fatal", True, "override")
            for cid in s.probes
        ]

    assert judge(seed, transcript, grader=lenient).verdict == "approve"


def test_report_artifact_and_ledger(tmp_path):
    report = run_report(list(SEEDS), compliant_target, run_id="audit_artifact")
    art = report.to_artifact()
    assert art.artifact_type == ARTIFACT_AUDIT_RESULT
    assert art.verify_payload()
    assert art.payload["overall_verdict"] == "approve"

    ledger = GuardrailLedger(path=tmp_path / "ledger.jsonl")
    record = report.record(ledger)
    assert record.kind == ARTIFACT_AUDIT_RESULT
    diag = ledger.verify_chain()
    assert diag.ok
    assert diag.length == 1


def test_sources_bridge_into_vault():
    srcs = sa_sources.load_sources()
    keys = {s.key for s in srcs}
    assert {"petri", "constitutional-ai", "anthropic-mythos-report"} <= keys

    mythos = next(s for s in srcs if s.key == "anthropic-mythos-report")
    assert mythos.contested
    assert mythos.evidence_strength == EvidenceStrength.WEAK

    vault = ResearchVault(path=None)
    ids = sa_sources.register_in_vault(vault, persist=False)
    assert len(ids) == len(srcs)
    assert any("Petri" in a.title for a in vault.entries())


def test_sources_can_exclude_contested():
    vault = ResearchVault(path=None)
    ids = sa_sources.register_in_vault(vault, include_contested=False, persist=False)
    expected = [s for s in sa_sources.load_sources() if not s.contested]
    assert len(ids) == len(expected)
