"""Tier-0 runtime gate — the fail-closed escalation path (directive §47).

A specialist proposal NEVER touches an effect directly. This module is the
deterministic gate between a Needle proposal and any executor:

    proposal -> schema check -> confidence policy -> capability check
             -> executor preflight -> execute -> verify -> attest

Each stage can only escalate or reject; it can never weaken a later stage.
The executor and verifier are injected callables so this module stays
pure policy with zero I/O of its own (testable with mocks, §88 Phase 2 gate).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Proposal:
    function_calls: list[dict[str, Any]]
    confidence: float = 0.0
    raw: str = ""
    specialist_id: str = ""
    specialist_hash: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.function_calls


@dataclass
class GateResult:
    action: str  # "execute" | "escalate" | "reject"
    reason: str
    proposal: Optional[Proposal] = None
    evidence: dict[str, Any] = field(default_factory=dict)


def route_proposal(
    proposal: Proposal,
    *,
    accept_threshold: float,
    review_threshold: float,
    schema_valid: Callable[[dict[str, Any]], bool],
    capability_authorized: Callable[[dict[str, Any]], bool],
    executor_preflight: Callable[[dict[str, Any]], tuple[bool, str]],
) -> GateResult:
    """Deterministic, fail-closed routing of a Tier-0 proposal.

    Order matters: empty/low-confidence/schema-invalid proposals escalate;
    capability denial rejects; preflight failure escalates. Nothing here
    executes effects — it only decides.
    """
    if proposal.is_empty:
        return GateResult("escalate", "empty_call", proposal)

    if proposal.confidence < review_threshold:
        return GateResult("escalate", "confidence_below_review", proposal,
                          {"confidence": proposal.confidence})

    for call in proposal.function_calls:
        if not schema_valid(call):
            return GateResult("escalate", "schema_invalid", proposal,
                              {"call": call.get("name")})
        if not capability_authorized(call):
            return GateResult("reject", "capability_denied", proposal,
                              {"call": call.get("name")})
        ok, why = executor_preflight(call)
        if not ok:
            return GateResult("escalate", f"preflight_failed:{why}", proposal,
                              {"call": call.get("name")})

    if proposal.confidence < accept_threshold:
        return GateResult("escalate", "confidence_below_accept", proposal,
                          {"confidence": proposal.confidence})

    return GateResult("execute", "all_gates_passed", proposal)
