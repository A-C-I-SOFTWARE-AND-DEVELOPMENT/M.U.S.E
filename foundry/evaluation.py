"""Evaluation harness — specialist metrics from directive §21.

Compares model outputs (JSON tool-call envelopes) against gold answers and
computes the acceptance-gate metrics (§22). Pure functions over parsed JSON
so it can score stock, tuned, and baseline models identically (§25).
"""
from __future__ import annotations

from typing import Any


def _calls(output: dict) -> list[dict]:
    return output.get("function_calls", []) or []


def exact_call_accuracy(golds: list[dict], preds: list[dict]) -> float:
    """Right function(s), right argument values — strict set equality."""
    ok = 0
    for g, p in zip(golds, preds):
        gc = sorted(((c["name"], tuple(sorted(c.get("arguments", {}).items()))) for c in _calls(g)))
        pc = sorted(((c["name"], tuple(sorted(c.get("arguments", {}).items()))) for c in _calls(p)))
        ok += int(gc == pc)
    return ok / max(1, len(golds))


def function_selection_accuracy(golds: list[dict], preds: list[dict]) -> float:
    ok = 0
    for g, p in zip(golds, preds):
        gnames = sorted(c["name"] for c in _calls(g))
        pnames = sorted(c["name"] for c in _calls(p))
        ok += int(gnames == pnames)
    return ok / max(1, len(golds))


def argument_value_accuracy(golds: list[dict], preds: list[dict]) -> float:
    """Per-argument accuracy over calls whose function was selected correctly."""
    total = correct = 0
    for g, p in zip(golds, preds):
        pmap = {c["name"]: c.get("arguments", {}) for c in _calls(p)}
        for c in _calls(g):
            if c["name"] not in pmap:
                continue
            gargs, pargs = c.get("arguments", {}), pmap[c["name"]]
            for k, v in gargs.items():
                total += 1
                correct += int(pargs.get(k) == v)
    return correct / max(1, total)


def optional_field_hallucination_rate(golds: list[dict], preds: list[dict],
                                      optional_fields: dict[str, set[str]]) -> float:
    """Rate at which optional fields appear in predictions without gold support."""
    total = halluc = 0
    for g, p in zip(golds, preds):
        gmap = {c["name"]: c.get("arguments", {}) for c in _calls(g)}
        for c in _calls(p):
            name = c["name"]
            gargs = gmap.get(name, {})
            for k in c.get("arguments", {}):
                if k in optional_fields.get(name, set()):
                    total += 1
                    halluc += int(k not in gargs)
    return halluc / max(1, total)


def refusal_metrics(golds: list[dict], preds: list[dict]) -> dict[str, float]:
    """Empty-call precision/recall over the refusal classes."""
    gold_neg = [i for i, g in enumerate(golds) if not _calls(g)]
    pred_neg = [i for i, p in enumerate(preds) if not _calls(p)]
    tp = len(set(gold_neg) & set(pred_neg))
    precision = tp / max(1, len(pred_neg))
    recall = tp / max(1, len(gold_neg))
    return {"empty_call_precision": precision, "empty_call_recall": recall}


def wrong_domain_execution_rate(golds: list[dict], preds: list[dict]) -> float:
    """Non-empty calls on inputs whose gold is refusal (must be ~0)."""
    bad = total = 0
    for g, p in zip(golds, preds):
        if not _calls(g):
            total += 1
            bad += int(bool(_calls(p)))
    return bad / max(1, total)


def schema_validity_rate(preds: list[dict], tool_names: set[str]) -> float:
    ok = 0
    for p in preds:
        valid = all(c.get("name") in tool_names and isinstance(c.get("arguments", {}), dict)
                    for c in _calls(p))
        ok += int(valid)
    return ok / max(1, len(preds))


def evaluate(golds: list[dict], preds: list[dict], *,
             tool_names: set[str],
             optional_fields: dict[str, set[str]] | None = None) -> dict[str, float]:
    optional_fields = optional_fields or {}
    out = {
        "exact_call_accuracy": exact_call_accuracy(golds, preds),
        "function_selection_accuracy": function_selection_accuracy(golds, preds),
        "argument_value_accuracy": argument_value_accuracy(golds, preds),
        "optional_field_hallucination": optional_field_hallucination_rate(golds, preds, optional_fields),
        "wrong_domain_execution_rate": wrong_domain_execution_rate(golds, preds),
        "schema_validity_rate": schema_validity_rate(preds, tool_names),
        "n": len(golds),
    }
    out.update(refusal_metrics(golds, preds))
    return out


GATES = {
    "exact_call_accuracy": 0.90,
    "argument_value_accuracy": 0.95,
    "empty_call_recall": 0.95,
    "optional_field_hallucination": 0.02,   # upper bound
    "schema_validity_rate": 1.00,
    "wrong_domain_execution_rate": 0.00,    # upper bound
}


def gate_report(metrics: dict[str, float], gates: dict[str, float] | None = None) -> dict[str, Any]:
    gates = gates or GATES
    upper_bounded = {"optional_field_hallucination", "wrong_domain_execution_rate"}
    results = {}
    for k, threshold in gates.items():
        v = metrics.get(k)
        if v is None:
            results[k] = {"value": None, "gate": threshold, "passed": False}
            continue
        passed = v <= threshold if k in upper_bounded else v >= threshold
        results[k] = {"value": round(v, 4), "gate": threshold, "passed": passed}
    results["ALL_PASS"] = all(r["passed"] for r in results.values())
    return results
