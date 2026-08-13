"""Deterministic concise rendering for validated specialist decisions."""

from __future__ import annotations

from .ontology import (
    ACTION_CODES,
    ACTION_TEXT,
    BLOCKER_CODES,
    BLOCKER_TEXT,
    CATEGORY_CODES,
    CATEGORIES,
    CLAIM_CODES,
    CLAIM_TEXT,
    CONSTRAINT_CODES,
    CONSTRAINTS,
    EVIDENCE_KIND_CODES,
    EVIDENCE_STATE_CODES,
    EVIDENCE_STATES,
    EVIDENCE_TEXT,
    GATE_CODES,
    GATE_TEXT,
    ISSUE_CODES,
    ISSUE_TEXT,
    PRIORITY_CODES,
    PRIORITY_TEXT,
    STAGE_CODES,
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


def _decode(code: str, codes: dict[str, str], kind: str) -> str:
    if code in codes:
        return code
    decoded = {compact: name for name, compact in codes.items()}.get(code)
    if decoded is None:
        raise ValueError(f"unknown {kind} code: {code}")
    return decoded


def render_decision(answer: dict) -> str:
    """Render one validated Needle answer without asking a model to write prose."""
    name = answer.get("name")
    args = answer.get("arguments") or {}

    if name == "assess_world_state":
        verdict = _member(VERDICTS, args.get("verdict"), "verdict")
        category = _decode(args.get("category"), CATEGORY_CODES, "category")
        issue_name = _decode(args.get("issue_code"), ISSUE_CODES, "issue")
        action_name = _decode(args.get("action_code"), ACTION_CODES, "action")
        issue = _need(ISSUE_TEXT, issue_name, "issue")
        action = _need(ACTION_TEXT, action_name, "action")
        _decode(args.get("evidence_state"), EVIDENCE_STATE_CODES, "evidence state")
        return f"{verdict} | {category}\n\n{issue}. {action}."

    if name == "prioritize_world_action":
        stage = _decode(args.get("stage"), STAGE_CODES, "stage")
        priority_name = _decode(args.get("priority_code"), PRIORITY_CODES, "priority")
        blocker_name = _decode(args.get("blocker_code"), BLOCKER_CODES, "blocker")
        priority = _need(PRIORITY_TEXT, priority_name, "priority")
        blocker = _need(BLOCKER_TEXT, blocker_name, "blocker")
        _decode(args.get("evidence_state"), EVIDENCE_STATE_CODES, "evidence state")
        return f"NEXT | {stage}\n\n{priority}; current blocker: {blocker}."

    if name == "evaluate_world_constraint":
        constraint = _decode(args.get("constraint_code"), CONSTRAINT_CODES, "constraint")
        verdict = _member(VERDICTS, args.get("verdict"), "verdict")
        action_name = _decode(args.get("action_code"), ACTION_CODES, "action")
        action = _need(ACTION_TEXT, action_name, "action")
        _decode(args.get("evidence_state"), EVIDENCE_STATE_CODES, "evidence state")
        observed = args.get("observed_value")
        limit = args.get("limit_value")
        unit = args.get("unit")
        return (
            f"{verdict} | {constraint}\n\n"
            f"Observed {observed} {unit}; reference limit {limit} {unit}. {action}."
        )

    if name == "request_world_verification":
        category = _decode(args.get("category"), CATEGORY_CODES, "category")
        claim_name = _decode(args.get("claim_kind"), CLAIM_CODES, "claim")
        evidence_name = _decode(args.get("evidence_kind"), EVIDENCE_KIND_CODES, "evidence")
        gate_name = _decode(args.get("next_gate"), GATE_CODES, "gate")
        claim = _need(CLAIM_TEXT, claim_name, "claim")
        evidence = _need(EVIDENCE_TEXT, evidence_name, "evidence")
        gate = _need(GATE_TEXT, gate_name, "gate")
        return f"UNVERIFIED | {category}\n\n{claim} requires {evidence}. {gate}."

    raise ValueError(f"unknown specialist tool: {name}")
