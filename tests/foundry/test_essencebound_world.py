"""Tests for the Essencebound Needle 2 world-architecture specialist."""

from foundry.essencebound_world.ontology import ontology_payload
from foundry.essencebound_world.renderer import render_decision
from foundry.essencebound_world.requirements import compile_requirements, parse_sections
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


def _numbered_source() -> str:
    lines = ["# MUSE / NEEDLE 2 — TEST SOURCE", ""]
    for number in range(83):
        lines.extend(
            [
                f"# {number}. SECTION {number}",
                "",
                f"- Verify bridge landing rule {number} before claiming completion.",
                "",
            ]
        )
    return "\n".join(lines)


def test_requirements_cover_every_numbered_source_section():
    sections = parse_sections(_numbered_source())
    rows = compile_requirements(_numbered_source())

    assert [section.number for section in sections] == list(range(83))
    assert {row["source_section_number"] for row in rows} == set(range(83))
    assert len({row["requirement_id"] for row in rows}) == len(rows)
    assert all(
        {
            "requirement_id",
            "source_section",
            "source_section_number",
            "requirement",
            "category",
            "severity",
            "testability",
            "required_evidence",
            "rule_kind",
            "source_excerpt_hash",
        }
        <= row.keys()
        for row in rows
    )


def test_requirements_distinguish_design_rules_from_foundry_process_rules():
    rows = compile_requirements(_numbered_source())

    kinds_by_section = {row["source_section_number"]: row["rule_kind"] for row in rows}
    assert kinds_by_section[0] == "DESIGN_RULE"
    assert kinds_by_section[29] == "DESIGN_RULE"
    assert kinds_by_section[30] == "FOUNDRY_RULE"
    assert kinds_by_section[82] == "FOUNDRY_RULE"


def test_requirements_classify_evidence_and_performance_rules():
    source = """
# 15. PERFORMANCE GATES
- Never claim performance success without measurement.
# 37. EVIDENCE TRAINING
- Repository facts require repository inspection.
"""
    rows = compile_requirements(source)

    performance = next(row for row in rows if row["source_section_number"] == 15)
    evidence = next(row for row in rows if row["source_section_number"] == 37)
    assert performance["category"] == "PERFORMANCE"
    assert performance["testability"] == "measurement"
    assert "performance_measurement" in performance["required_evidence"]
    assert evidence["category"] == "REPO_REASONING"
    assert evidence["testability"] == "repository"


def test_requirements_do_not_misclassify_essence_infrastructure_as_architecture():
    rows = compile_requirements(
        """
# 9. ESSENCE ENERGY AS INFRASTRUCTURE
- Essence conduits must connect the crystal source to the consuming machinery.
"""
    )

    assert rows[0]["category"] == "ESSENCE_INFRASTRUCTURE"
