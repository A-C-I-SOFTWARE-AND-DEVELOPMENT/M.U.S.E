"""Tests for the Essencebound Needle 2 world-architecture specialist."""

from collections import Counter

from foundry.essencebound_world.generator import (
    RUNG_SIZES,
    build_ladder,
    generate_canonical,
    generate_holdout,
    generate_qa,
)
from foundry.essencebound_world.ontology import ontology_payload
from foundry.essencebound_world.renderer import render_decision
from foundry.essencebound_world.requirements import compile_requirements, parse_sections
from foundry.essencebound_world.schemas import tool_names, tool_schemas
from third_party.needle.needle.model.finetune import render_example
from third_party.needle.needle.model.tokenizer import get_tokenizer


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


def _compiled_test_requirements() -> list[dict]:
    return compile_requirements(_numbered_source())


def test_canonical_generation_is_deterministic_dense_and_native():
    requirements = _compiled_test_requirements()

    first = generate_canonical(requirements, 4000)
    second = generate_canonical(requirements, 4000)

    assert first == second
    assert len(first) == 4000
    assert [row["id"] for row in first] == [
        f"eb_world_{index:06d}" for index in range(1, 4001)
    ]
    assert {row["category"] for row in first} == set(ontology_payload()["categories"])
    assert len({row["query"] for row in first}) == 4000
    assert all(row["specialist"] == "NEEDLE-EB-WORLD-ARCHITECT" for row in first)
    assert all(row["tools"] == first[0]["tools"] for row in first)
    assert all(len(row["reasoning"].split()) <= 24 for row in first)
    assert all("query" in row and "answers" in row for row in first)

    label_counts = Counter(label for row in first for label in row["expected_labels"])
    failure_fraction = sum(
        bool({"FAIL", "BLOCKED", "UNVERIFIED"} & set(row["expected_labels"]))
        for row in first
    ) / len(first)
    adversarial_fraction = sum(
        row["example_type"] in {"adversarial", "repo_evidence"} for row in first
    ) / len(first)
    assert failure_fraction >= 0.30
    assert adversarial_fraction >= 0.15
    assert label_counts["PASS"] > 0


def test_ladder_has_exact_splits_and_is_an_exact_superset():
    rows = generate_canonical(_compiled_test_requirements(), 4000)
    ladder = build_ladder(rows)

    previous_ids: set[str] = set()
    for size in RUNG_SIZES:
        splits = ladder[size]
        assert {name: len(values) for name, values in splits.items()} == {
            "train": size * 8 // 10,
            "validation": size // 10,
            "test": size // 10,
        }
        current_ids = {row["id"] for values in splits.values() for row in values}
        assert current_ids == {f"eb_world_{index:06d}" for index in range(1, size + 1)}
        assert previous_ids <= current_ids
        previous_ids = current_ids


def test_qa_and_holdout_are_isolated_from_training_families():
    requirements = _compiled_test_requirements()
    canonical = generate_canonical(requirements, 4000)
    qa = generate_qa(requirements, 4000)
    holdout = generate_holdout(requirements, 400)

    assert len(qa) == 4000
    assert len(holdout) == 400
    assert qa[0]["id"] == "eb_world_qa_000001"
    assert holdout[0]["id"] == "eb_world_holdout_000001"
    canonical_families = {row["semantic_family"] for row in canonical}
    assert canonical_families.isdisjoint(row["semantic_family"] for row in qa)
    assert canonical_families.isdisjoint(row["semantic_family"] for row in holdout)
    assert {row["query"] for row in canonical}.isdisjoint(row["query"] for row in qa)
    assert {row["query"] for row in canonical}.isdisjoint(row["query"] for row in holdout)


def test_native_training_rows_fit_needle_context_with_targets_intact():
    rows = generate_canonical(_compiled_test_requirements(), 80)
    tokenizer = get_tokenizer()
    lengths = []
    for row in rows:
        prompt, target = render_example(row)
        lengths.append(1 + len(tokenizer.encode(prompt)) + len(tokenizer.encode(target)) + 1)

    assert max(lengths) <= 2048
