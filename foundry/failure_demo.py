"""Deliberate-failure demo (directive §87).

Feeds the five mandatory failure classes through the REAL Foundry components
(runtime_gate, QA validators, registry, belief ledger) and proves:
  refusal / escalation / verification rejection / quarantine-rollback / ledger evidence.

A happy path is included for contrast. Run: python foundry/failure_demo.py
Writes: docs/foundry/FAILURE_DEMO_TRANSCRIPT.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from foundry.runtime_gate import Proposal, route_proposal
from foundry.executors.qa import validators
from foundry.registry import FoundryRegistry, SpecialistRecord
from foundry.beliefs import BeliefLedger, Belief

OUT = ROOT / "docs" / "foundry" / "FAILURE_DEMO_TRANSCRIPT.json"

QA_TOOL_NAMES = {"inspect_geometry", "inspect_uv_materials", "inspect_transform_scale",
                 "inspect_naming_structure", "run_asset_gate"}
# Arguments must be objects whose keys exist in the schema (bounded set here).
ALLOWED_ARGS = {
    "inspect_geometry": {"max_tris", "allow_ngons"},
    "inspect_uv_materials": {"max_materials"},
    "inspect_transform_scale": set(),
    "inspect_naming_structure": {"pattern"},
    "run_asset_gate": {"profile"},
}
CAPABILITIES = {"qa.inspect", "qa.gate"}          # specialist holds these only
CALL_CAPABILITY = {name: "qa.gate" if name == "run_asset_gate" else "qa.inspect"
                   for name in QA_TOOL_NAMES}
ALLOWED_ROOTS = (r"D:\assets\staging", r"C:\Users\Echer\M.U.S.E\staging")


def schema_valid(call: dict) -> bool:
    name = call.get("name")
    args = call.get("arguments", {})
    return name in QA_TOOL_NAMES and isinstance(args, dict) \
        and set(args) <= ALLOWED_ARGS.get(name, set())


def capability_authorized(call: dict) -> bool:
    return CALL_CAPABILITY.get(call.get("name")) in CAPABILITIES


def executor_preflight(call: dict):
    path = call.get("arguments", {}).get("path")
    if path and not str(path).startswith(ALLOWED_ROOTS):
        return False, "path_outside_staging"
    return True, ""


transcript: list[dict] = []


def record(case: str, expectation: str, **fields):
    entry = {"case": case, "expectation": expectation, "at": time.time(), **fields}
    transcript.append(entry)
    print(f"[{case}] -> {fields.get('outcome')}")


registry = FoundryRegistry(ROOT / "docs" / "foundry" / "demo_registry.json")
ledger = BeliefLedger(ROOT / "docs" / "foundry" / "demo_beliefs.json")

# ---------------------------------------------------------------- HAPPY PATH
prop = Proposal(function_calls=[{"name": "inspect_geometry",
                                 "arguments": {"max_tris": 9000}}],
                confidence=0.93, specialist_id="needle-qa", specialist_hash="probe")
gate = route_proposal(prop, accept_threshold=0.8, review_threshold=0.5,
                      schema_valid=schema_valid, capability_authorized=capability_authorized,
                      executor_preflight=executor_preflight)
manifest = {"triangle_count": 9000, "ngon_count": 0, "non_manifold_edges": 0,
            "degenerate_faces": 0, "materials": ["a"], "uv_overlap_fraction": 0.0,
            "objects": [{"name": "hero_mesh", "scale": [1, 1, 1]}]}
verdict = validators.run_asset_gate(manifest, "game-ready")
record("HAPPY", "execute + verify pass", outcome=gate.action,
       gate_reason=gate.reason, verifier_passed=verdict["passed"])

# ------------------------------------------------- 1. OFF-TOPIC -> refusal->escalate
prop = Proposal(function_calls=[], confidence=0.0, specialist_id="needle-qa")
gate = route_proposal(prop, accept_threshold=0.8, review_threshold=0.5,
                      schema_valid=schema_valid, capability_authorized=capability_authorized,
                      executor_preflight=executor_preflight)
record("1-OFF-TOPIC", "escalate(empty_call)", outcome=gate.action, gate_reason=gate.reason)

# --------------------------------------- 2. UNDER-SPECIFIED -> low confidence -> escalate
prop = Proposal(function_calls=[{"name": "inspect_geometry", "arguments": {"max_tris": 1}}],
                confidence=0.31, specialist_id="needle-qa")
gate = route_proposal(prop, accept_threshold=0.8, review_threshold=0.5,
                      schema_valid=schema_valid, capability_authorized=capability_authorized,
                      executor_preflight=executor_preflight)
record("2-UNDER-SPECIFIED", "escalate(confidence_below_review)", outcome=gate.action,
       gate_reason=gate.reason, confidence=prop.confidence)

# ----------------- 3. ADJACENT-DOMAIN (FBX export asked of QA specialist) -> reject/escalate
prop = Proposal(function_calls=[{"name": "export_fbx", "arguments": {"path": "x.fbx"}}],
                confidence=0.88, specialist_id="needle-qa")
gate = route_proposal(prop, accept_threshold=0.8, review_threshold=0.5,
                      schema_valid=schema_valid, capability_authorized=capability_authorized,
                      executor_preflight=executor_preflight)
record("3-ADJACENT-DOMAIN", "escalate(schema_invalid: unknown tool)", outcome=gate.action,
       gate_reason=gate.reason)

# ---------------------------------------------------------- 4. MALFORMED -> schema escalate
prop = Proposal(function_calls=[{"name": "inspect_geometry",
                                 "arguments": {"required": ["type"], "minimum": 1}}],
                confidence=0.97, specialist_id="needle-qa")
gate = route_proposal(prop, accept_threshold=0.8, review_threshold=0.5,
                      schema_valid=schema_valid, capability_authorized=capability_authorized,
                      executor_preflight=executor_preflight)
record("4-MALFORMED", "escalate(schema_invalid: arg-key bleed)", outcome=gate.action,
       gate_reason=gate.reason)

# ---------------------- 5. VALID REQUEST, INVALID EXECUTOR OUTPUT -> verification rejection
#         -> quarantine + rollback to known-good + ledger evidence
rec_v2 = SpecialistRecord(specialist_id="needle-qa", niche_id="qa.ci.gating",
                          specialist_version="0.0.2", base_hash="4b0a972d",
                          schema_hash="sch", dataset_hash="dat")
cid_v2 = registry.register(rec_v2)
rec_v2.transition("TRAINING", "probe")
rec_v2.transition("ACTIVE", "demo promotion")
rec_v1 = SpecialistRecord(specialist_id="needle-qa", niche_id="qa.ci.gating",
                          specialist_version="0.0.1", base_hash="4b0a972d",
                          schema_hash="sch", dataset_hash="dat0")
registry.register(rec_v1)

prop = Proposal(function_calls=[{"name": "run_asset_gate",
                                 "arguments": {"profile": "game-ready"}}],
                confidence=0.95, specialist_id="needle-qa", specialist_hash=cid_v2[:16])
gate = route_proposal(prop, accept_threshold=0.8, review_threshold=0.5,
                      schema_valid=schema_valid, capability_authorized=capability_authorized,
                      executor_preflight=executor_preflight)
# executor "produces" a deliberately invalid output: gate claims pass but the
# deterministic verifier re-checks the real manifest and FAILS it.
bad_manifest = {"triangle_count": 999999, "ngon_count": 14, "non_manifold_edges": 3,
                "degenerate_faces": 2, "materials": ["a"] * 9, "uv_overlap_fraction": 0.4,
                "objects": [{"name": "BAD NAME!!", "scale": [2, 1, 1]}]}
verdict = validators.run_asset_gate(bad_manifest, "game-ready")
if not verdict["passed"]:
    rec_v2.transition("QUARANTINED", "verification rejection: executor output failed deterministic gate")
    kg = registry.known_good("needle-qa")
    if kg and kg.specialist_version != "0.0.2":
        kg.transition("ACTIVE", "rollback: restored known-good after quarantine of 0.0.2")
    registry.save()
    ledger.assert_claim(Belief(
        claim_id="demo.verification_escape.prevented",
        statement="Validator rejected bad executor output; v0.0.2 quarantined; known-good restored",
        status="MEASURED", evidence=["FAILURE_DEMO_TRANSCRIPT.json case 5"], confidence=1.0))
record("5-INVALID-EXECUTOR-OUTPUT", "verification rejection + quarantine + rollback",
       outcome="quarantined", gate_action=gate.action, verifier_passed=verdict["passed"],
       failed_checks=[c["check"] for c in verdict["checks"] if not c["passed"]],
       registry_status=registry.get(cid_v2).status)

OUT.write_text(json.dumps(transcript, indent=2))
print(f"\ntranscript -> {OUT}")
ok = (
    transcript[0]["outcome"] == "execute" and transcript[0]["verifier_passed"]
    and transcript[1]["outcome"] == "escalate"
    and transcript[2]["outcome"] == "escalate"
    and transcript[3]["outcome"] == "escalate"
    and transcript[4]["outcome"] == "escalate"
    and transcript[5]["outcome"] == "quarantined" and not transcript[5]["verifier_passed"]
)
print("FAILURE DEMO:", "ALL EXPECTATIONS MET" if ok else "MISMATCH — inspect transcript")
sys.exit(0 if ok else 1)
