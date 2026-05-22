"""Risk classification + human-in-the-loop gating for the enterprise council.

The orchestrator and the validator both call into this module to
decide whether a task can be executed autonomously or must escalate
to the user. Keep the rules here small, declarative, and unit-tested —
adding a new high-risk action should be a one-line table edit, not a
control-flow change.

The risk levels are deliberately coarse (LOW / MEDIUM / HIGH). Anything
that could move money, change employment status, send a mass message,
or release regulated data is HIGH. Anything that mutates a customer
record or a contract is MEDIUM. Read-only lookups and internal
summaries are LOW.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# (domain, action) → Risk. Action strings match the structured task verbs the
# orchestrator emits; if a task action isn't listed here it defaults to LOW
# for read actions and MEDIUM for write actions (see `classify`).
_BASE_RULES: dict[tuple[str, str], Risk] = {
    # Finance — money movement + reporting
    ("finance", "invoice.read"): Risk.LOW,
    ("finance", "invoice.create"): Risk.MEDIUM,
    ("finance", "invoice.send"): Risk.MEDIUM,
    ("finance", "payment.refund"): Risk.HIGH,
    ("finance", "payment.wire"): Risk.HIGH,
    ("finance", "budget.read"): Risk.LOW,
    ("finance", "budget.update"): Risk.MEDIUM,
    ("finance", "report.generate"): Risk.LOW,
    # HR — employment + personal data
    ("hr", "policy.lookup"): Risk.LOW,
    ("hr", "candidate.screen"): Risk.LOW,
    ("hr", "offer.create"): Risk.HIGH,
    ("hr", "offer.send"): Risk.HIGH,
    ("hr", "employee.terminate"): Risk.HIGH,
    ("hr", "pii.export"): Risk.HIGH,
    # Customer Service — public-facing communication
    ("customer-service", "ticket.classify"): Risk.LOW,
    ("customer-service", "kb.retrieve"): Risk.LOW,
    ("customer-service", "ticket.reply"): Risk.MEDIUM,
    ("customer-service", "ticket.escalate"): Risk.MEDIUM,
    ("customer-service", "mass.email"): Risk.HIGH,
    # Operations — logistics + compliance
    ("operations", "logistics.plan"): Risk.LOW,
    ("operations", "logistics.execute"): Risk.MEDIUM,
    ("operations", "compliance.check"): Risk.LOW,
    ("operations", "compliance.file"): Risk.MEDIUM,
    ("operations", "incident.declare"): Risk.HIGH,
    # Sales — pipeline + contracts
    ("sales", "lead.read"): Risk.LOW,
    ("sales", "lead.update"): Risk.MEDIUM,
    ("sales", "proposal.draft"): Risk.LOW,
    ("sales", "proposal.send"): Risk.MEDIUM,
    ("sales", "contract.execute"): Risk.HIGH,
    ("sales", "discount.apply"): Risk.MEDIUM,
}

# Threshold-based bumps: if the task carries a numeric amount that
# exceeds a domain-specific limit, escalate one risk level. Keeps the
# common case (small invoices, small refunds) autonomous while ensuring
# the big-dollar long-tail goes through a human.
_AMOUNT_THRESHOLDS: dict[tuple[str, str], float] = {
    ("finance", "invoice.create"): 50_000.0,
    ("finance", "invoice.send"): 50_000.0,
    ("finance", "payment.refund"): 5_000.0,
    ("sales", "discount.apply"): 0.25,  # 25% off — bumps to HIGH
    ("sales", "proposal.send"): 100_000.0,
}


@dataclass(frozen=True)
class Task:
    """A unit of work the orchestrator dispatches to a leaf agent."""

    domain: str
    action: str
    args: Mapping[str, object] = field(default_factory=dict)
    rationale: str = ""
    # Free-form tags the orchestrator can use to bump risk (e.g. "gdpr",
    # "external-comms", "irreversible"). Anything starting with "@" is
    # treated as a forced-HIGH override.
    tags: tuple[str, ...] = ()


def _amount_for(task: Task) -> Optional[float]:
    for k in ("amount", "total", "value", "discount"):
        v = task.args.get(k) if isinstance(task.args, Mapping) else None
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _bump(level: Risk) -> Risk:
    return {Risk.LOW: Risk.MEDIUM, Risk.MEDIUM: Risk.HIGH, Risk.HIGH: Risk.HIGH}[level]


def classify(task: Task) -> Risk:
    """Map a task to a risk level using the table + threshold bumps."""
    key = (task.domain, task.action)
    base = _BASE_RULES.get(key)
    if base is None:
        # Unknown action — read-shaped verbs are LOW, write-shaped MEDIUM,
        # destructive ones HIGH. Errs on the safer side.
        verb = task.action.split(".")[-1].lower()
        if verb in {
            "read",
            "lookup",
            "list",
            "search",
            "describe",
            "summarize",
            "generate",
        }:
            base = Risk.LOW
        elif verb in {"delete", "terminate", "wire", "execute", "publish", "release"}:
            base = Risk.HIGH
        else:
            base = Risk.MEDIUM

    # Threshold bump.
    threshold = _AMOUNT_THRESHOLDS.get(key)
    amount = _amount_for(task)
    if threshold is not None and amount is not None and amount > threshold:
        base = _bump(base)

    # Tag overrides.
    for tag in task.tags:
        if tag.startswith("@"):
            return Risk.HIGH
        if tag.lower() in {"gdpr", "regulated", "irreversible", "external-mass"}:
            base = _bump(base)

    return base


def requires_human(task: Task, *, autonomy: str = "default") -> bool:
    """Return True if the user must confirm before this task executes.

    ``autonomy`` is a soft knob the operator can set on the council
    profile:
      * ``"strict"``     — MEDIUM and HIGH both require a human.
      * ``"default"``    — only HIGH requires a human.
      * ``"yolo"``       — never requires a human (acknowledged risk).
        Mirrors Hermes' existing YOLO mode; the SKILL.md spells this
        out so an operator opt-in is obvious.
    """
    risk = classify(task)
    if autonomy == "yolo":
        return False
    if autonomy == "strict":
        return risk in (Risk.MEDIUM, Risk.HIGH)
    return risk == Risk.HIGH


# Convenience for tests and the monitor: surface every (domain, action) we
# know about. Helps the monitor detect novel actions in the audit log that
# should probably be added to the rule table.
def known_actions() -> set[tuple[str, str]]:
    return set(_BASE_RULES.keys())
