"""Fail-closed validation and coverage reporting for Essencebound datasets."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from needle.model.finetune import render_example
from needle.model.tokenizer import get_tokenizer

from .generator import RUNG_SIZES
from .ontology import CATEGORIES, SPECIALIST_ID
from .renderer import render_decision
from .schemas import tool_schemas

_SPACE = re.compile(r"\s+")
_BANNED_REASONING = (
    "chain of thought",
    "hidden reasoning",
    "internal monologue",
    "step by step private",
)
_LEGAL_STATUS_LABELS = {
    "PASS", "FAIL", "WARN", "UNVERIFIED", "BLOCKED", "REFUSE", "OUT_OF_SCOPE",
}
_SOURCE_LEAKAGE_MARKERS = (
    "muse / needle 2 — essencebound world architect foundry prompt",
    "begin dataset foundry execution now",
)


def _normalize(text: str) -> str:
    return _SPACE.sub(" ", text.strip().casefold())


def _error(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, **details}


def _schema_errors(answer: dict, schemas: dict[str, dict], row_id: str) -> list[dict]:
    errors: list[dict] = []
    name = answer.get("name")
    if name not in schemas:
        return [_error("unknown_tool", row_id=row_id, tool=name)]
    arguments = answer.get("arguments")
    if not isinstance(arguments, dict):
        return [_error("arguments_not_object", row_id=row_id, tool=name)]
    parameters = schemas[name]["parameters"]
    properties = parameters.get("properties", {})
    required = set(parameters.get("required", []))
    missing = sorted(required - set(arguments))
    if missing:
        errors.append(_error("missing_argument", row_id=row_id, tool=name, fields=missing))
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        errors.append(_error("unknown_argument", row_id=row_id, tool=name, fields=unknown))
    for key, value in arguments.items():
        prop = properties.get(key, {})
        if "enum" in prop and value not in prop["enum"]:
            errors.append(
                _error("invalid_enum", row_id=row_id, tool=name, field=key, value=value)
            )
        expected = prop.get("type")
        if expected == "number" and not isinstance(value, (int, float)):
            errors.append(
                _error("invalid_argument_type", row_id=row_id, tool=name, field=key)
            )
        if expected == "string" and not isinstance(value, str):
            errors.append(
                _error("invalid_argument_type", row_id=row_id, tool=name, field=key)
            )
    return errors


def validate_rows(
    rows: list[dict],
    ontology: dict | None = None,
    schemas: list[dict] | None = None,
) -> dict[str, Any]:
    """Validate enriched rows and Needle-native targets without mutating input."""
    ontology = ontology or {}
    schemas = schemas or tool_schemas()
    schema_map = {schema["name"]: schema for schema in schemas}
    errors: list[dict] = []
    ids: Counter[str] = Counter()
    queries: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    types: Counter[str] = Counter()
    tokenizer = get_tokenizer()
    max_tokens = 0

    for position, row in enumerate(rows):
        row_id = row.get("id", f"row:{position}")
        if not isinstance(row_id, str) or not row_id.strip():
            errors.append(_error("blank_id", row=position))
            continue
        ids[row_id] += 1
        required = (
            "specialist", "category", "difficulty", "source_tags", "requirement_ids",
            "example_type", "expected_labels", "semantic_family", "query", "reasoning",
            "answers", "tools",
        )
        for key in required:
            if key not in row:
                errors.append(_error("missing_field", row_id=row_id, field=key))
        if row.get("specialist") != SPECIALIST_ID:
            errors.append(_error("specialist_tag", row_id=row_id))
        category = row.get("category")
        if category not in CATEGORIES:
            errors.append(_error("unknown_category", row_id=row_id, category=category))
        else:
            categories[category] += 1
        query = row.get("query")
        if not isinstance(query, str) or not query.strip():
            errors.append(_error("blank_query", row_id=row_id))
        else:
            queries[_normalize(query)] += 1
            lowered = query.casefold()
            if any(marker in lowered for marker in _SOURCE_LEAKAGE_MARKERS):
                errors.append(_error("source_prompt_leakage", row_id=row_id))
            try:
                query.encode("utf-8", "strict")
            except UnicodeError:
                errors.append(_error("malformed_unicode", row_id=row_id))
        reasoning = row.get("reasoning", "")
        if not isinstance(reasoning, str) or not reasoning.strip():
            errors.append(_error("blank_reasoning", row_id=row_id))
        else:
            normalized_reasoning = reasoning.casefold()
            if any(marker in normalized_reasoning for marker in _BANNED_REASONING):
                errors.append(_error("chain_of_thought", row_id=row_id))
            if len(reasoning.split()) > 24:
                errors.append(_error("reasoning_too_long", row_id=row_id))
        expected_labels = row.get("expected_labels")
        if not isinstance(expected_labels, list) or not expected_labels:
            errors.append(_error("invalid_labels", row_id=row_id))
        else:
            legal = _LEGAL_STATUS_LABELS | set(CATEGORIES)
            for label in expected_labels:
                labels[str(label)] += 1
                if label not in legal:
                    errors.append(_error("invalid_label", row_id=row_id, label=label))
        example_type = row.get("example_type")
        if isinstance(example_type, str):
            types[example_type] += 1
        answers = row.get("answers")
        if not isinstance(answers, list):
            errors.append(_error("answers_not_list", row_id=row_id))
        else:
            for answer in answers:
                if not isinstance(answer, dict):
                    errors.append(_error("answer_not_object", row_id=row_id))
                    continue
                errors.extend(_schema_errors(answer, schema_map, row_id))
                if answer.get("name") in schema_map:
                    try:
                        rendered = render_decision(answer)
                        if len(rendered.split()) > 150:
                            errors.append(_error("rendered_output_too_long", row_id=row_id))
                    except ValueError as exc:
                        errors.append(_error("render_failure", row_id=row_id, detail=str(exc)))
        if row.get("tools") != schemas:
            errors.append(_error("schema_mismatch", row_id=row_id))
        if all(key in row for key in ("query", "answers", "tools")):
            prompt, target = render_example(row)
            token_count = 1 + len(tokenizer.encode(prompt)) + len(tokenizer.encode(target)) + 1
            max_tokens = max(max_tokens, token_count)
            if token_count > 2048:
                errors.append(
                    _error("needle_context_overflow", row_id=row_id, tokens=token_count)
                )

    duplicate_ids = sorted(value for value, count in ids.items() if count > 1)
    duplicate_queries = sorted(value for value, count in queries.items() if count > 1)
    for row_id in duplicate_ids:
        errors.append(_error("duplicate_id", row_id=row_id, count=ids[row_id]))
    if duplicate_queries:
        errors.append(_error("duplicate_query", count=len(duplicate_queries)))

    row_count = len(rows)
    failure_count = sum(
        bool({"FAIL", "BLOCKED", "UNVERIFIED"} & set(row.get("expected_labels", [])))
        for row in rows
    )
    adversarial_count = sum(
        row.get("example_type") in {"adversarial", "repo_evidence"} for row in rows
    )
    if row_count:
        if failure_count / row_count < 0.30:
            errors.append(_error("negative_balance", value=failure_count / row_count))
        if adversarial_count / row_count < 0.15:
            errors.append(_error("adversarial_balance", value=adversarial_count / row_count))
    if row_count >= 250:
        missing_categories = sorted(set(CATEGORIES) - set(categories))
        if missing_categories:
            errors.append(_error("category_coverage", missing=missing_categories))

    return {
        "passed": not errors,
        "errors": errors,
        "counts": {
            "rows": row_count,
            "unique_ids": len(ids),
            "unique_queries": len(queries),
            "exact_duplicate_queries": sum(count - 1 for count in queries.values() if count > 1),
            "failure_rows": failure_count,
            "adversarial_rows": adversarial_count,
            "categories": dict(sorted(categories.items())),
            "labels": dict(sorted(labels.items())),
            "example_types": dict(sorted(types.items())),
            "max_training_tokens": max_tokens,
        },
    }


def coverage_matrix(ladders: dict[int, dict[str, list[dict]]]) -> dict[str, Any]:
    categories = {category: {} for category in CATEGORIES}
    example_types: dict[str, dict[str, int]] = {}
    labels: dict[str, dict[str, int]] = {}
    for size, splits in sorted(ladders.items()):
        rows = [row for values in splits.values() for row in values]
        category_counts = Counter(row.get("category") for row in rows)
        type_counts = Counter(row.get("example_type") for row in rows)
        label_counts = Counter(label for row in rows for label in row.get("expected_labels", []))
        for category in CATEGORIES:
            categories[category][str(size)] = category_counts[category]
        for name, count in type_counts.items():
            example_types.setdefault(str(name), {})[str(size)] = count
        for name, count in label_counts.items():
            labels.setdefault(str(name), {})[str(size)] = count
    return {"categories": categories, "example_types": example_types, "labels": labels}


def validate_dataset(
    canonical: list[dict],
    ladders: dict[int, dict[str, list[dict]]],
    qa: list[dict],
    holdout: list[dict],
) -> dict[str, Any]:
    """Validate every pool, split, rung relationship, and isolation boundary."""
    errors: list[dict] = []
    row_reports = {
        "canonical": validate_rows(canonical),
        "qa": validate_rows(qa),
        "holdout": validate_rows(holdout),
    }
    for pool, report in row_reports.items():
        errors.extend({**error, "pool": pool} for error in report["errors"])

    canonical_ids = [row["id"] for row in canonical]
    previous_ids: set[str] = set()
    for size in RUNG_SIZES:
        splits = ladders.get(size)
        if splits is None:
            errors.append(_error("missing_rung", rung=size))
            continue
        expected_counts = {"train": size * 8 // 10, "validation": size // 10, "test": size // 10}
        actual_counts = {name: len(splits.get(name, [])) for name in expected_counts}
        if actual_counts != expected_counts:
            errors.append(
                _error("rung_size", rung=size, expected=expected_counts, actual=actual_counts)
            )
        current_ids = {
            row["id"] for name in ("train", "validation", "test") for row in splits.get(name, [])
        }
        expected_ids = set(canonical_ids[:size])
        if current_ids != expected_ids:
            errors.append(_error("rung_membership", rung=size))
        if not previous_ids <= current_ids:
            errors.append(_error("rung_not_superset", rung=size))
        previous_ids = current_ids
        family_sets = {
            name: {row["semantic_family"] for row in splits.get(name, [])}
            for name in ("train", "validation", "test")
        }
        if (
            family_sets["train"] & family_sets["validation"]
            or family_sets["train"] & family_sets["test"]
            or family_sets["validation"] & family_sets["test"]
        ):
            errors.append(_error("split_family_leakage", rung=size))

    pools = {
        "canonical": canonical,
        "qa": qa,
        "holdout": holdout,
    }
    names = tuple(pools)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            left_families = {row["semantic_family"] for row in pools[left]}
            right_families = {row["semantic_family"] for row in pools[right]}
            left_queries = {_normalize(row["query"]) for row in pools[left]}
            right_queries = {_normalize(row["query"]) for row in pools[right]}
            family_overlap = left_families & right_families
            query_overlap = left_queries & right_queries
            if family_overlap or query_overlap:
                errors.append(
                    _error(
                        "pool_leakage",
                        pools=[left, right],
                        family_overlap=len(family_overlap),
                        query_overlap=len(query_overlap),
                    )
                )

    duplicate_rate = (
        row_reports["canonical"]["counts"]["exact_duplicate_queries"] / max(1, len(canonical))
    )
    return {
        "passed": not errors,
        "errors": errors,
        "pools": row_reports,
        "coverage": coverage_matrix(ladders),
        "duplicate_rate": duplicate_rate,
        "rungs": {
            str(size): {name: len(rows) for name, rows in ladders.get(size, {}).items()}
            for size in RUNG_SIZES
        },
    }
