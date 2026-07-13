"""Approval language for risky and owner-gated actions.

Approval flows in Jarvis Prime use a formal, precise voice — no jokes,
no metaphors, no warmth padding. The owner gate phrase is fixed and
appears verbatim in the rendered response so it can be matched
programmatically later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from hermes_cli.jarvis_prime.conversation.response_shapes import (
    DOUBLE_CONFIRM_PHRASE,
    OWNER_GATE_PHRASE,
)


class RiskLevel(str, Enum):
    """Conversation-level risk class.

    The capability graph has its own ``RiskLevel`` used for routing.
    This one is tuned for *response shaping* — it decides between a
    single approval request and a serious double confirmation.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_HIGH_RISK_MARKERS: tuple[str, ...] = (
    "deploy",
    "release",
    "publish",
    "push to main",
    "push to master",
    "force push",
    "merge to main",
    "drop table",
    "delete production",
    "wipe",
    "rm -rf",
    "revoke",
    "rotate credentials",
    "rotate secrets",
    "shut down production",
    "shutdown production",
    "kill production",
    "send to all",
    "broadcast to",
    "mass email",
    "charge customers",
    "refund all",
    "irreversible",
    "destroy",
)


_MEDIUM_RISK_MARKERS: tuple[str, ...] = (
    "push",
    "merge",
    "deploy preview",
    "delete branch",
    "delete file",
    "rewrite history",
    "rebase",
    "force",
    "open pr",
    "open pull request",
    "create release",
    "post to",
    "send a message",
    "send email",
    "send slack",
    "notify",
)


_LOW_RISK_MARKERS: tuple[str, ...] = (
    "commit",
    "stage",
    "save file",
    "create branch",
    "open issue",
    "create issue",
    "draft",
)


def classify_risk(text: str) -> RiskLevel:
    """Estimate risk from the request text using coarse keyword markers."""
    if not text:
        return RiskLevel.NONE
    lowered = text.lower()

    if any(marker in lowered for marker in _HIGH_RISK_MARKERS):
        return RiskLevel.CRITICAL if "production" in lowered or "irreversible" in lowered else RiskLevel.HIGH
    if any(marker in lowered for marker in _MEDIUM_RISK_MARKERS):
        return RiskLevel.MEDIUM
    if any(marker in lowered for marker in _LOW_RISK_MARKERS):
        return RiskLevel.LOW
    return RiskLevel.NONE


@dataclass(frozen=True)
class ApprovalAsk:
    """A rendered approval ask."""

    risk: RiskLevel
    summary: str
    body: str
    requires_double_confirm: bool


def render_approval(
    action: str,
    risk: RiskLevel,
    blast_radius: str | None = None,
    rollback: str | None = None,
) -> ApprovalAsk:
    """Render a formal approval request."""
    summary = f"Proposed action: {action.strip().rstrip('.')}."
    lines: list[str] = [summary, f"Risk level: {risk.value}."]

    if blast_radius:
        lines.append(f"Blast radius: {blast_radius.strip()}.")
    if rollback:
        lines.append(f"Rollback: {rollback.strip()}.")

    lines.append("Authorization required.")
    lines.append(f"Reply '{OWNER_GATE_PHRASE}' to proceed.")

    return ApprovalAsk(
        risk=risk,
        summary=summary,
        body="\n".join(lines),
        requires_double_confirm=False,
    )


def render_double_confirmation(
    action: str,
    risk: RiskLevel,
    blast_radius: str | None = None,
    rollback: str | None = None,
) -> ApprovalAsk:
    """Render a serious two-step confirmation for high-risk actions."""
    summary = f"High-risk action proposed: {action.strip().rstrip('.')}."
    lines: list[str] = [
        summary,
        f"Risk level: {risk.value}.",
    ]
    if blast_radius:
        lines.append(f"Blast radius: {blast_radius.strip()}.")
    if rollback:
        lines.append(f"Rollback: {rollback.strip()}.")

    lines.extend(
        [
            "This action is irreversible or destructive.",
            "Two confirmations required.",
            f"Step 1: reply '{OWNER_GATE_PHRASE}' to acknowledge.",
            f"Step 2: reply '{DOUBLE_CONFIRM_PHRASE}' to execute.",
        ]
    )

    return ApprovalAsk(
        risk=risk,
        summary=summary,
        body="\n".join(lines),
        requires_double_confirm=True,
    )


def needs_double_confirmation(risk: RiskLevel) -> bool:
    """Return True for risks that require a two-step confirmation."""
    return risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}


__all__ = [
    "RiskLevel",
    "ApprovalAsk",
    "OWNER_GATE_PHRASE",
    "DOUBLE_CONFIRM_PHRASE",
    "classify_risk",
    "render_approval",
    "render_double_confirmation",
    "needs_double_confirmation",
]
