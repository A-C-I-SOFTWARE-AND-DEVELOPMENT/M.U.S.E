"""Integration tests for Essencebound dataset artifact construction."""

import json

from foundry.essencebound_world.pipeline import build_data, validate_root


def _master_prompt() -> str:
    lines = ["# MUSE / NEEDLE 2 — ESSENCEBOUND TEST", ""]
    for number in range(83):
        lines.extend(
            [
                f"# {number}. SECTION {number}",
                f"- Verify the Essencebound bridge, evidence, scale, and performance rule {number}.",
                "",
            ]
        )
    return "\n".join(lines)


def test_build_data_writes_complete_valid_tree(tmp_path):
    source = tmp_path / "master.md"
    source.write_text(_master_prompt(), encoding="utf-8")
    output = tmp_path / "EB_World_Architect"

    result = build_data(source, output)

    assert result["validation"]["passed"]
    assert result["requirements"] >= 83
    assert (output / "source" / "requirements.json").exists()
    assert (output / "source" / "ontology.json").exists()
    assert (output / "source" / "tool_schemas.json").exists()
    assert (output / "reports" / "dataset_validation.json").exists()
    assert (output / "reports" / "coverage.md").exists()
    assert (output / "manifest.json").exists()
    assert sum(1 for _ in open(output / "rung_0250" / "train.jsonl", encoding="utf-8")) == 200
    assert sum(1 for _ in open(output / "rung_0250" / "validation.jsonl", encoding="utf-8")) == 25
    assert sum(1 for _ in open(output / "rung_0250" / "test.jsonl", encoding="utf-8")) == 25
    assert sum(1 for _ in open(output / "qa" / "qa_0250.jsonl", encoding="utf-8")) == 250
    assert sum(
        1
        for _ in open(
            output / "holdout" / "needle_eb_world_holdout.jsonl", encoding="utf-8"
        )
    ) == 400

    persisted = json.loads(
        (output / "reports" / "dataset_validation.json").read_text(encoding="utf-8")
    )
    assert persisted["passed"]
    assert validate_root(output)["passed"]


def test_build_data_is_deterministic(tmp_path):
    source = tmp_path / "master.md"
    source.write_text(_master_prompt(), encoding="utf-8")
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_result = build_data(source, first)
    second_result = build_data(source, second)

    assert first_result["dataset_hash"] == second_result["dataset_hash"]
    assert json.loads((first / "manifest.json").read_text(encoding="utf-8"))["files"] == json.loads(
        (second / "manifest.json").read_text(encoding="utf-8")
    )["files"]
