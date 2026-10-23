"""Verification tests for the foundry/ package (M.U.S.E. Autonomous Specialist Foundry)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "axiom"))

from foundry.eligibility import classify_niche, run_census
from foundry.registry import FoundryRegistry, SpecialistRecord
from foundry.beliefs import BeliefLedger, Belief
from foundry.runtime_gate import Proposal, route_proposal
from foundry.dataset import build_dataset, validate_row
from foundry.evaluation import evaluate, gate_report
from foundry.teacher import discover_teachers, rank_teachers, teacher_plan
from foundry.executors.qa import validators


# ---------------- eligibility ----------------

def test_classify_extraction_niche():
    spec = {"id": "qa.ci.gating", "domain": "qa", "description": "CI quality gates",
            "keywords": ["ci", "gate", "audit", "check"]}
    r = classify_niche(spec)
    assert r.candidate_mode == "NEEDLE_ROUTER_ONLY"
    assert r.schema_expressible


def test_classify_generative_niche_goes_up():
    spec = {"id": "business.gtm.narrative", "domain": "business",
            "description": "GTM narrative positioning story writing",
            "keywords": ["gtm", "positioning", "story", "narrative", "writing"]}
    r = classify_niche(spec)
    assert r.candidate_mode == "PROVIDER_GENERAL_MODEL"
    assert r.requires_free_text_generation


def test_classify_safety_niche_human_gated():
    spec = {"id": "hazmat_command.incident.report", "domain": "hazmat-command",
            "description": "hazmat incident reporting", "keywords": ["incident", "report"]}
    r = classify_niche(spec)
    assert r.candidate_mode == "HUMAN_GATED"
    assert r.safety_or_irreversibility_level == "high"


def test_census_runs_on_real_specs(tmp_path):
    out = run_census(
        specs_dir=Path(r"C:\Users\Echer\M.U.S.E\hermes_cli\jarvis_prime\niches\specs"),
        out_json=tmp_path / "c.json", out_md=tmp_path / "c.md")
    assert out["total"] == 137
    assert sum(out["distribution"].values()) == 137


# ---------------- registry ----------------

def test_registry_lifecycle_and_rollback(tmp_path):
    reg = FoundryRegistry(tmp_path / "reg.json")
    rec = SpecialistRecord(specialist_id="s1", niche_id="n1", specialist_version="0.1",
                           base_hash="a", schema_hash="b", dataset_hash="c")
    cid = reg.register(rec)
    rec.transition("TRAINING", "t")
    rec.transition("ACTIVE", "promoted")
    reg.save()
    reg2 = FoundryRegistry(tmp_path / "reg.json")
    assert reg2.get(cid).status == "ACTIVE"
    assert reg2.known_good("s1").specialist_version == "0.1"
    with pytest.raises(ValueError):
        rec.transition("NOT_A_STATE", "bad")


# ---------------- beliefs ----------------

def test_belief_refutation_reopens_dependents(tmp_path):
    bl = BeliefLedger(tmp_path / "b.json")
    bl.assert_claim(Belief(claim_id="a", statement="x", status="MEASURED"))
    bl.assert_claim(Belief(claim_id="b", statement="y", status="MEASURED", depends_on=["a"]))
    reopened = bl.refute("a", "new evidence")
    assert "b" in reopened
    assert bl._beliefs["b"].status == "UNVERIFIED"
    assert not bl.promotable("a")


# ---------------- runtime gate ----------------

def _gate(**kw):
    defaults = dict(accept_threshold=0.8, review_threshold=0.5,
                    schema_valid=lambda c: True, capability_authorized=lambda c: True,
                    executor_preflight=lambda c: (True, ""))
    defaults.update(kw)
    return defaults


def test_gate_empty_escalates():
    r = route_proposal(Proposal(function_calls=[], confidence=0.9), **_gate())
    assert (r.action, r.reason) == ("escalate", "empty_call")


def test_gate_low_confidence_escalates():
    r = route_proposal(Proposal(function_calls=[{"name": "x"}], confidence=0.3), **_gate())
    assert r.action == "escalate"


def test_gate_schema_invalid_escalates():
    r = route_proposal(Proposal(function_calls=[{"name": "x"}], confidence=0.95),
                       **_gate(schema_valid=lambda c: False))
    assert r.action == "escalate"


def test_gate_capability_denied_rejects():
    r = route_proposal(Proposal(function_calls=[{"name": "x"}], confidence=0.95),
                       **_gate(capability_authorized=lambda c: False))
    assert r.action == "reject"


def test_gate_preflight_fail_escalates():
    r = route_proposal(Proposal(function_calls=[{"name": "x"}], confidence=0.95),
                       **_gate(executor_preflight=lambda c: (False, "bad_path")))
    assert r.action == "escalate" and "preflight" in r.reason


def test_gate_all_pass_executes():
    r = route_proposal(Proposal(function_calls=[{"name": "x"}], confidence=0.95), **_gate())
    assert r.action == "execute"


# ---------------- dataset ----------------

GOOD_TOOLS = {"a", "b"}


def test_dataset_quarantines_dupes_and_unknown_tools():
    rows = [
        {"query": "q1", "answers": [{"name": "a", "arguments": {"x": 1}}]},
        {"query": "q1", "answers": [{"name": "a", "arguments": {"x": 1}}]},  # dup
        {"query": "q2", "answers": [{"name": "nope", "arguments": {}}]},      # unknown tool
        {"query": "q3", "answers": []},
    ]
    ds = build_dataset(rows, specialist_id="s", schema_version="1",
                       tool_names=GOOD_TOOLS, teacher_provider="t", teacher_model="m")
    assert ds["manifest"]["counts"]["quarantined"] == 2
    assert ds["manifest"]["counts"]["valid"] == 2


def test_dataset_no_cluster_leakage():
    rows = []
    for i in range(20):  # paraphrase siblings share output cluster
        rows.append({"query": f"variant {i}", "answers": [{"name": "a", "arguments": {"x": 1}}]})
    for i in range(20):
        rows.append({"query": f"other {i}", "answers": [{"name": "b", "arguments": {"y": i}}]})
    ds = build_dataset(rows, specialist_id="s", schema_version="1",
                       tool_names=GOOD_TOOLS, teacher_provider="t", teacher_model="m")
    tc = {r["_provenance"]["dedupe_cluster"] for r in ds["train"]}
    ec = {r["_provenance"]["dedupe_cluster"] for r in ds["eval"]}
    assert not (tc & ec)


def test_validate_row_catches_bad_shape():
    assert validate_row({"answers": []}, GOOD_TOOLS) == ["missing_query"]
    assert "unknown_tool:z" in validate_row({"query": "q", "answers": [{"name": "z", "arguments": {}}]}, GOOD_TOOLS)


# ---------------- evaluation ----------------

def test_metrics_and_gates_detect_planted_failures():
    golds = [
        {"function_calls": [{"name": "a", "arguments": {"x": 1}}]},
        {"function_calls": []},
    ]
    preds = [
        {"function_calls": [{"name": "a", "arguments": {"x": 2}}]},  # wrong arg
        {"function_calls": [{"name": "b", "arguments": {}}]},          # wrong-domain exec
    ]
    m = evaluate(golds, preds, tool_names={"a", "b"})
    rep = gate_report(m)
    assert not rep["ALL_PASS"]
    assert not rep["exact_call_accuracy"]["passed"]
    assert not rep["wrong_domain_execution_rate"]["passed"]


def test_metrics_perfect_run_passes():
    golds = [
        {"function_calls": [{"name": "a", "arguments": {"x": 1}}]},
        {"function_calls": []},
    ]
    m = evaluate(golds, golds, tool_names={"a"})
    rep = gate_report(m)
    assert rep["ALL_PASS"]


# ---------------- teacher ----------------

def test_teacher_discovery_from_real_catalog():
    cands = discover_teachers(Path(r"C:\Users\Echer\M.U.S.E\config\model-catalog.yaml"))
    assert len(cands) == 40
    ranked = rank_teachers(cands)
    assert all(c.available for c in ranked if c.estimated_cost_rank == 0) or ranked
    plan = teacher_plan(cands, {"primary": 0.6, "secondary": 0.4})
    assert plan["primary"]["status"] in ("READY", "UNAVAILABLE")


def test_teacher_never_emits_credentials():
    cands = discover_teachers(Path(r"C:\Users\Echer\M.U.S.E\config\model-catalog.yaml"))
    plan = teacher_plan(cands, {"primary": 1.0})
    assert "key" not in json.dumps(plan).lower() or "requires" in json.dumps(plan).lower()


# ---------------- QA validators ----------------

def test_qa_gate_pass_and_fail():
    clean = {"triangle_count": 9000, "ngon_count": 0, "non_manifold_edges": 0,
             "degenerate_faces": 0, "materials": ["a"], "uv_overlap_fraction": 0.0,
             "objects": [{"name": "hero_mesh", "scale": [1, 1, 1]}]}
    assert validators.run_asset_gate(clean, "game-ready")["passed"]
    dirty = dict(clean, triangle_count=999999, ngon_count=12)
    gate = validators.run_asset_gate(dirty, "mobile")
    assert not gate["passed"]
    failed = {c["check"] for c in gate["checks"] if not c["passed"]}
    assert "polycount" in failed and "ngons" in failed


# ---------------- AXIOM adapter ----------------

def _axiom_available():
    try:
        import nacl, blake3  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _axiom_available(), reason="pynacl/blake3 not installed")
def test_axiom_promotion_attestation():
    from nacl.signing import SigningKey
    from axiom.core.registry import Registry
    from axiom.core.ledger import Ledger
    from foundry.axiom_adapter import attest_promotion

    key = SigningKey.generate()
    reg, led = Registry(), Ledger(signing_key=key)
    att = attest_promotion(
        specialist_id="needle-qa", niche_id="qa.ci.gating", version="0.0.2",
        lineage={"base_hash": "4b0a972d", "dataset_hash": "bea82807"},
        registry=reg, ledger=led, signing_key=key)
    assert att.unit_hash and att.lineage_event_hash
    assert led.verify_chain()
    assert reg.verify_signature(att.unit_hash)


@pytest.mark.skipif(not _axiom_available(), reason="pynacl/blake3 not installed")
def test_axiom_rejects_bad_units():
    from nacl.signing import SigningKey
    from axiom.core.registry import Registry
    from axiom.core.ledger import Ledger
    from axiom.core.canonical import Unit
    from axiom.core.verifier import Verifier, Attestation

    reg, led = Registry(), Ledger(signing_key=SigningKey.generate())
    bad_intent = Unit(name="b", doc="", intent="free text", effects=("fs.write",))
    assert not isinstance(Verifier(reg, led).verify(bad_intent), Attestation)
    bad_effect = Unit(name="c", doc="", intent="THE system SHALL x.",
                      effects=("fs.delete_all",))
    assert not isinstance(Verifier(reg, led).verify(bad_effect), Attestation)


@pytest.mark.skipif(not _axiom_available(), reason="pynacl/blake3 not installed")
def test_axiom_ledger_tamper_evidence():
    from nacl.signing import SigningKey
    from axiom.core.ledger import Ledger

    led = Ledger(signing_key=SigningKey.generate())
    led.append("t", {"v": 1})
    led.append("t2", {"v": 2})
    assert led.verify_chain()
    led._db.execute("UPDATE events SET payload=? WHERE seq=1", ('{"v": 999}',))
    led._db.commit()
    assert not led.verify_chain()


# ---------------- shadow / runtime learning ----------------

def test_shadow_monitor_estimate_and_scrub(tmp_path):
    from foundry.shadow import ShadowMonitor, ShadowEvent, scrub
    assert "[REDACTED]" in scrub("key sk-abcdef1234567890 tail")
    sm = ShadowMonitor(tmp_path / "s.jsonl")
    sm.record(ShadowEvent("sp", "n", "h1", [{"name": "a"}], "tier0", "rh", True, 0.9, 0.2))
    sm.record(ShadowEvent("sp", "n", "h2", [], "provider", "rh", None, 0.1, 0.3,
                          "retrieval_miss"))
    est = sm.compare("sp")
    assert est["shadow_events"] == 2
    assert 0.0 <= est["verified_call_rate"] <= 1.0


def test_failure_clustering_and_retrain_proposal():
    from foundry.shadow import cluster_failures, propose_retrain
    events = [{"failure_class": "wrong_argument"}] * 6 + \
             [{"failure_class": "retrieval_miss"}] * 2 + [{"failure_class": ""}]
    clusters = cluster_failures(events)
    assert clusters[0] == {"failure_class": "wrong_argument", "count": 6}
    prop = propose_retrain(events, min_cluster=5)
    assert prop and prop["dominant_failure"] == "wrong_argument"
    assert "full_regression_suite" in prop["requires"]
    # below threshold -> no proposal
    assert propose_retrain([{"failure_class": "wrong_argument"}] * 2, min_cluster=5) is None
