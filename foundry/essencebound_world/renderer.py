"""Deterministic concise rendering for validated specialist decisions."""

from __future__ import annotations

from .ontology import (
    ACTION_TEXT,
    BLOCKER_TEXT,
    CATEGORIES,
    CLAIM_TEXT,
    CONSTRAINTS,
    EVIDENCE_STATES,
    EVIDENCE_TEXT,
    GATE_TEXT,
    ISSUE_TEXT,
    PRIORITY_TEXT,
    STAGES,
    VERDICTS,
)


def _need(mapping, code: str, kind: str) -> str:
    try:
        return mapping[code]
    except KeyError as exc:
        raise ValueError(f"unknown {kind} code: {code}") from exc


def _member(values, code: str, kind: str) -> str:
    if code not in values:
        raise ValueError(f"unknown {kind} code: {code}")
    return code


def render_decision(answer: dict) -> str:
    """Render one validated Needle answer without asking a model to write prose."""
    name = answer.get("name")
    args = answer.get("arguments") or {}

    if name == "assess_world_state":
        verdict = _member(VERDICTS, args.get("verdict"), "verdict")
        category = _member(CATEGORIES, args.get("category"), "category")
        issue = _need(ISSUE_TEXT, args.get("issue_code"), "issue")
        action = _need(ACTION_TEXT, args.get("action_code"), "action")
        _member(EVIDENCE_STATES, args.get("evidence_state"), "evidence state")
        return f"{verdict} | {category}\n\n{issue}. {action}."

    if name == "prioritize_world_action":
        stage = _member(STAGES, args.get("stage"), "stage")
        priority = _need(PRIORITY_TEXT, args.get("priority_code"), "priority")
        blocker = _need(BLOCKER_TEXT, args.get("blocker_code"), "blocker")
        _member(EVIDENCE_STATES, args.get("evidence_state"), "evidence state")
        return f"NEXT | {stage}\n\n{priority}; current blocker: {blocker}."

    if name == "evaluate_world_constraint":
        constraint = _member(CONSTRAINTS, args.get("constraint_code"), "constraint")
        verdict = _member(VERDICTS, args.get("verdict"), "verdict")
        action = _need(ACTION_TEXT, args.get("action_code"), "action")
        _member(EVIDENCE_STATES, args.get("evidence_state"), "evidence state")
        observed = args.get("observed_value")
        limit = args.get("limit_value")
        unit = args.get("unit")
        return (
            f"{verdict} | {constraint}\n\n"
            f"Observed {observed} {unit}; reference limit {limit} {unit}. {action}."
        )

    if name == "request_world_verification":
        category = _member(CATEGORIES, args.get("category"), "category")
        claim = _need(CLAIM_TEXT, args.get("claim_kind"), "claim")
        evidence = _need(EVIDENCE_TEXT, args.get("evidence_kind"), "evidence")
        gate = _need(GATE_TEXT, args.get("next_gate"), "gate")
        return f"UNVERIFIED | {category}\n\n{claim} requires {evidence}. {gate}."

    raise ValueError(f"unknown specialist tool: {name}")
