"""Needle-native macro-tool schemas for Essencebound world decisions."""

from __future__ import annotations

from typing import Annotated

from needle.agent.tools import Field, build_schema

from .ontology import (
    ACTION_CODES,
    BLOCKER_CODES,
    CATEGORY_CODES,
    CLAIM_CODES,
    CONSTRAINT_CODES,
    EVIDENCE_KIND_CODES,
    EVIDENCE_STATE_CODES,
    GATE_CODES,
    ISSUE_CODES,
    PRIORITY_CODES,
    STAGE_CODES,
    VERDICTS,
)

Verdict = Annotated[str, Field(enum=VERDICTS)]
Category = Annotated[str, Field(enum=tuple(CATEGORY_CODES.values()))]
IssueCode = Annotated[str, Field(enum=tuple(ISSUE_CODES.values()))]
ActionCode = Annotated[str, Field(enum=tuple(ACTION_CODES.values()))]
EvidenceState = Annotated[str, Field(enum=tuple(EVIDENCE_STATE_CODES.values()))]
Stage = Annotated[str, Field(enum=tuple(STAGE_CODES.values()))]
PriorityCode = Annotated[str, Field(enum=tuple(PRIORITY_CODES.values()))]
BlockerCode = Annotated[str, Field(enum=tuple(BLOCKER_CODES.values()))]
ConstraintCode = Annotated[str, Field(enum=tuple(CONSTRAINT_CODES.values()))]
EvidenceKind = Annotated[str, Field(enum=tuple(EVIDENCE_KIND_CODES.values()))]
ClaimKind = Annotated[str, Field(enum=tuple(CLAIM_CODES.values()))]
NextGate = Annotated[str, Field(enum=tuple(GATE_CODES.values()))]


def assess_world_state(
    verdict: Verdict,
    category: Category,
    issue_code: IssueCode,
    action_code: ActionCode,
    evidence_state: EvidenceState,
) -> dict:
    """Classify an Essencebound world state and select its smallest safe correction."""
    return dict(
        verdict=verdict,
        category=category,
        issue_code=issue_code,
        action_code=action_code,
        evidence_state=evidence_state,
    )


def prioritize_world_action(
    stage: Stage,
    priority_code: PriorityCode,
    blocker_code: BlockerCode,
    evidence_state: EvidenceState,
) -> dict:
    """Select the next Essencebound production action at the current stage."""
    return dict(
        stage=stage,
        priority_code=priority_code,
        blocker_code=blocker_code,
        evidence_state=evidence_state,
    )


def evaluate_world_constraint(
    constraint_code: ConstraintCode,
    observed_value: float,
    limit_value: float,
    unit: str,
    verdict: Verdict,
    action_code: ActionCode,
    evidence_state: EvidenceState,
) -> dict:
    """Evaluate a supplied Essencebound scale, geometry, or performance constraint."""
    return dict(
        constraint_code=constraint_code,
        observed_value=observed_value,
        limit_value=limit_value,
        unit=unit,
        verdict=verdict,
        action_code=action_code,
        evidence_state=evidence_state,
    )


def request_world_verification(
    evidence_kind: EvidenceKind,
    claim_kind: ClaimKind,
    category: Category,
    next_gate: NextGate,
) -> dict:
    """Refuse an unsupported project claim and name the evidence gate required next."""
    return dict(
        evidence_kind=evidence_kind,
        claim_kind=claim_kind,
        category=category,
        next_gate=next_gate,
    )


_TOOLS = (
    assess_world_state,
    prioritize_world_action,
    evaluate_world_constraint,
    request_world_verification,
)


def tool_schemas() -> list[dict]:
    """Return Needle's verified native `parameters` schema dialect."""
    return [build_schema(fn) for fn in _TOOLS]


def tool_names() -> set[str]:
    return {fn.__name__ for fn in _TOOLS}
