"""Tests for the Essencebound Needle 2 world-architecture specialist."""

from foundry.essencebound_world.ontology import ontology_payload
from foundry.essencebound_world.renderer import render_decision
from foundry.essencebound_world.schemas import tool_names, tool_schemas


def test_native_schema_contract_and_tool_ceiling():
    schemas = tool_schemas()

    assert len(schemas) == 4
    assert tool_names() == {
        "assess_world_state",
        "prioritize_world_action",
        "evaluate_world_constraint",
        "request_world_verification",
    }
    assert all("parameters" in schema for schema in schemas)
    assert all("arguments" not in schema for schema in schemas)
    assert all(schema["parameters"]["type"] == "object" for schema in schemas)


def test_ontology_contains_all_required_domain_categories():
    ontology = ontology_payload()

    assert len(ontology["categories"]) == 40
    assert ontology["categories"][0] == "CONCEPT_FIDELITY"
    assert ontology["categories"][-1] == "TASK_PRIORITIZATION"
    assert {"PASS", "FAIL", "WARN", "UNVERIFIED", "BLOCKED"} <= set(
        ontology["verdicts"]
    )


def test_renderer_is_concise_and_evidence_aware():
    answer = {
        "name": "request_world_verification",
        "arguments": {
            "evidence_kind": "PERFORMANCE_MEASUREMENT",
            "claim_kind": "PERFORMANCE_PASS",
            "category": "PERFORMANCE",
            "next_gate": "RUN_PERFORMANCE_GATE",
        },
    }

    text = render_decision(answer)

    assert text.startswith("UNVERIFIED | PERFORMANCE")
    assert "measurement" in text.lower()
    assert len(text.split()) <= 80


def test_renderer_rejects_unknown_codes():
    answer = {
        "name": "assess_world_state",
        "arguments": {
            "verdict": "FAIL",
            "category": "TRAVERSAL",
            "issue_code": "NOT_A_REAL_ISSUE",
            "action_code": "ADD_VALID_LANDING",
            "evidence_state": "SUPPORTED_BY_INPUT",
        },
    }

    try:
        render_decision(answer)
    except ValueError as exc:
        assert "NOT_A_REAL_ISSUE" in str(exc)
    else:
        raise AssertionError("unknown ontology codes must fail closed")
