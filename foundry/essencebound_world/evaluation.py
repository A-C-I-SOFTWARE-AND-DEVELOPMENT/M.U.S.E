"""Essencebound behavior metrics and production gates for real Needle outputs."""

from __future__ import annotations

import json
from typing import Any

from .ontology import (
    ACTION_CODES,
    BLOCKER_CODES,
    CATEGORY_CODES,
    CONSTRAINT_CODES,
    EVIDENCE_STATE_CODES,
    GATE_CODES,
    PRIORITY_CODES,
)
from .schemas import tool_schemas

DOMAIN_GATES = {
    "exact_accuracy": 0.90,
    "verdict_accuracy": 0.95,
    "category_accuracy": 0.95,
    "corrective_action_accuracy": 0.90,
    "evidence_discipline": 0.95,
    "priority_accuracy": 0.95,
    "false_completion_safety": 1.00,
    "constraint_accuracy": 0.95,
    "schema_validity": 1.00,
    "wrong_domain_execution_rate": 0.00,
    "critical_failure_count": 0.00,
}


def _reverse(codes: dict[str, str]) -> dict[str, str]:
    return {compact: name for name, compact in codes.items()}


_CATEGORY_NAMES = _reverse(CATEGORY_CODES)
_ACTION_NAMES = _reverse(ACTION_CODES)
_PRIORITY_NAMES = _reverse(PRIORITY_CODES)
_BLOCKER_NAMES = _reverse(BLOCKER_CODES)
_CONSTRAINT_NAMES = _reverse(CONSTRAINT_CODES)
_GATE_NAMES = _reverse(GATE_CODES)
_EVIDENCE_STATE_NAMES = _reverse(EVIDENCE_STATE_CODES)


def _calls(item: dict) -> list[dict]:
    calls = item.get("answers") if "answers" in item else item.get("function_calls")
    return calls if isinstance(calls, list) else []


def _decode(value: str | None, names: dict[str, str]) -> str:
    if value is None:
        return ""
    return names.get(value, value)


def _constraint_category(constraint: str) -> str:
    if constraint in {
        "PLAYER_HEIGHT_CM", "WALKWAY_WIDTH_CM", "PRIMARY_PATH_WIDTH_CM",
        "COMBAT_ROUTE_WIDTH_CM", "DOOR_WIDTH_CM", "RAILING_HEIGHT_CM", "STAIR_RISE_CM",
    }:
        return "PLAYER_SCALE"
    if constraint in {"BRIDGE_WIDTH_CM", "BRIDGE_GRADE_DEG"}:
        return "BRIDGES"
    if constraint == "ISLAND_RADIUS_UU":
        return "LANDMASS"
    if constraint == "ISLAND_INSTANCES":
        return "PERFORMANCE"
    if constraint in {"VRAM_GB", "FRAME_TIME_REGRESSION_PERCENT"}:
        return "PERFORMANCE"
    return "FAILURE_DETECTION"


def _facts(item: dict, *, gold_category: str | None = None) -> dict[str, str]:
    calls = _calls(item)
    if not calls:
        return {
            "verdict": "REFUSE",
            "category": "OUT_OF_SCOPE",
            "action": "NONE",
            "evidence_state": "INSUFFICIENT_EVIDENCE",
            "tool": "",
        }
    call = calls[0]
    name = call.get("name", "")
    args = call.get("arguments") or {}
    if name == "assess_world_state":
        return {
            "verdict": str(args.get("verdict", "")),
            "category": _decode(args.get("category"), _CATEGORY_NAMES),
            "action": _decode(args.get("action_code"), _ACTION_NAMES),
            "evidence_state": _decode(args.get("evidence_state"), _EVIDENCE_STATE_NAMES),
            "tool": name,
        }
    if name == "prioritize_world_action":
        blocker = _decode(args.get("blocker_code"), _BLOCKER_NAMES)
        return {
            "verdict": "PASS" if blocker == "NONE" else "BLOCKED",
            "category": "TASK_PRIORITIZATION",
            "action": _decode(args.get("priority_code"), _PRIORITY_NAMES),
            "evidence_state": _decode(args.get("evidence_state"), _EVIDENCE_STATE_NAMES),
            "tool": name,
        }
    if name == "evaluate_world_constraint":
        constraint = _decode(args.get("constraint_code"), _CONSTRAINT_NAMES)
        return {
            "verdict": str(args.get("verdict", "")),
            "category": _constraint_category(constraint),
            "action": _decode(args.get("action_code"), _ACTION_NAMES),
            "evidence_state": _decode(args.get("evidence_state"), _EVIDENCE_STATE_NAMES),
            "tool": name,
        }
    if name == "request_world_verification":
        return {
            "verdict": "UNVERIFIED",
            "category": _decode(args.get("category"), _CATEGORY_NAMES),
            "action": _decode(args.get("next_gate"), _GATE_NAMES),
            "evidence_state": "INSUFFICIENT_EVIDENCE",
            "tool": name,
        }
    return {
        "verdict": "INVALID",
        "category": "INVALID",
        "action": "INVALID",
        "evidence_state": "INVALID",
        "tool": name,
    }


def _schema_valid(item: dict) -> bool:
    schemas = {schema["name"]: schema for schema in tool_schemas()}
    for call in _calls(item):
        name = call.get("name")
        if name not in schemas or not isinstance(call.get("arguments"), dict):
            return False
        args = call["arguments"]
        params = schemas[name]["parameters"]
        properties = params.get("properties", {})
        if not set(params.get("required", [])) <= set(args):
            return False
        if not set(args) <= set(properties):
            return False
        for key, value in args.items():
            if "enum" in properties[key] and value not in properties[key]["enum"]:
                return False
    return True


def _ratio(correct: int, total: int) -> float:
    return correct / total if total else 1.0


def evaluate_domain(golds: list[dict], predictions: list[dict]) -> dict[str, Any]:
    """Score domain decisions and expose every critical failure instance."""
    n = len(golds)
    padded_predictions = list(predictions[:n]) + [
        {"function_calls": []} for _ in range(max(0, n - len(predictions)))
    ]
    exact = verdict = category = action = 0
    action_total = 0
    evidence = evidence_total = 0
    priority = priority_total = 0
    constraint = constraint_total = 0
    false_completion_safe = false_completion_total = 0
    schema_valid = wrong_domain = wrong_domain_total = 0
    critical: list[dict[str, Any]] = []

    for index, (gold, prediction) in enumerate(zip(golds, padded_predictions)):
        gold_calls = _calls(gold)
        pred_calls = _calls(prediction)
        exact += int(
            json.dumps(gold_calls, sort_keys=True, separators=(",", ":"))
            == json.dumps(pred_calls, sort_keys=True, separators=(",", ":"))
        )
        gold_facts = _facts(gold, gold_category=gold.get("category"))
        pred_facts = _facts(prediction)
        verdict += int(gold_facts["verdict"] == pred_facts["verdict"])
        category += int(gold_facts["category"] == pred_facts["category"])
        if gold_calls:
            action_total += 1
            action += int(gold_facts["action"] == pred_facts["action"])
        evidence_required = (
            not gold_calls
            or gold_facts["tool"] == "request_world_verification"
            or gold_facts["evidence_state"] == "INSUFFICIENT_EVIDENCE"
        )
        if evidence_required:
            evidence_total += 1
            evidence += int(
                not pred_calls
                or pred_facts["tool"] == "request_world_verification"
                or pred_facts["evidence_state"] == "INSUFFICIENT_EVIDENCE"
            )
        if gold_facts["tool"] == "prioritize_world_action":
            priority_total += 1
            priority += int(
                pred_facts["tool"] == "prioritize_world_action"
                and pred_facts["action"] == gold_facts["action"]
            )
        if gold_facts["tool"] == "evaluate_world_constraint":
            constraint_total += 1
            constraint += int(
                pred_facts["tool"] == "evaluate_world_constraint"
                and pred_facts["verdict"] == gold_facts["verdict"]
                and pred_facts["action"] == gold_facts["action"]
            )
        if gold_facts["tool"] == "request_world_verification":
            false_completion_total += 1
            safe = pred_facts["verdict"] != "PASS"
            false_completion_safe += int(safe)
            if not safe:
                critical.append(
                    {
                        "index": index,
                        "id": gold.get("id", str(index)),
                        "class": "false_completion",
                        "gold": gold_facts,
                        "prediction": pred_facts,
                    }
                )
        if gold_facts["verdict"] in {"FAIL", "BLOCKED"} and pred_facts["verdict"] == "PASS":
            critical.append(
                {
                    "index": index,
                    "id": gold.get("id", str(index)),
                    "class": "unsafe_approval",
                    "gold": gold_facts,
                    "prediction": pred_facts,
                }
            )
        schema_valid += int(_schema_valid(prediction))
        if not gold_calls:
            wrong_domain_total += 1
            wrong_domain += int(bool(pred_calls))

    return {
        "n": n,
        "exact_accuracy": _ratio(exact, n),
        "verdict_accuracy": _ratio(verdict, n),
        "category_accuracy": _ratio(category, n),
        "corrective_action_accuracy": _ratio(action, action_total),
        "evidence_discipline": _ratio(evidence, evidence_total),
        "priority_accuracy": _ratio(priority, priority_total),
        "false_completion_safety": _ratio(false_completion_safe, false_completion_total),
        "constraint_accuracy": _ratio(constraint, constraint_total),
        "schema_validity": _ratio(schema_valid, n),
        "wrong_domain_execution_rate": (
            wrong_domain / wrong_domain_total if wrong_domain_total else 0.0
        ),
        "critical_failure_count": len(critical),
        "critical_failures": critical,
        "subsets": {
            "action": action_total,
            "evidence": evidence_total,
            "priority": priority_total,
            "constraint": constraint_total,
            "false_completion": false_completion_total,
            "wrong_domain": wrong_domain_total,
        },
    }


def domain_gate(
    metrics: dict[str, Any],
    *,
    baseline: dict[str, Any] | None = None,
    gates: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Apply hard domain gates and require measured improvement over stock."""
    gates = gates or DOMAIN_GATES
    upper_bounded = {"wrong_domain_execution_rate", "critical_failure_count"}
    report: dict[str, Any] = {}
    for metric, threshold in gates.items():
        value = metrics.get(metric)
        passed = False if value is None else (
            value <= threshold if metric in upper_bounded else value >= threshold
        )
        report[metric] = {"value": value, "gate": threshold, "passed": passed}
    if baseline is None:
        report["baseline_improvement"] = {
            "value": None,
            "gate": "required_for_promotion",
            "passed": True,
            "status": "NOT_APPLIED",
        }
    else:
        tuned = metrics.get("exact_accuracy")
        stock = baseline.get("exact_accuracy")
        improvement = None if tuned is None or stock is None else tuned - stock
        report["baseline_improvement"] = {
            "value": improvement,
            "gate": ">0",
            "passed": improvement is not None and improvement > 0,
            "status": "MEASURED",
        }
    report["ALL_PASS"] = all(
        value["passed"] for key, value in report.items() if key != "ALL_PASS"
    )
    return report
