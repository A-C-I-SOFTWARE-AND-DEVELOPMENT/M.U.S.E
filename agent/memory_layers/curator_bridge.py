"""Curator bridge (MEM-1).

Decides whether a raw `MemoryEvent` may become durable memory. The safety
invariant: **untrusted / injected content is never auto-promoted.** Only
owner-trusted, owner-approved content auto-promotes; everything else is routed
to the EXISTING owner-approval gate as a `ProposalKind.MEMORY_PROMOTION`
proposal (`hermes_cli/jarvis_prime/self_update.py::ProposalBook`).

This keeps prompt-injection in tool output from writing itself into long-term
memory, while preserving an auditable path for legitimate promotions.
"""

from __future__ import annotations

import logging
from typing import Optional

from .provenance import MemoryEvent

logger = logging.getLogger(__name__)


def should_auto_promote(event: MemoryEvent) -> bool:
    """Auto-promote only owner-trusted AND owner-approved content."""
    return event.trust_level == "owner" and event.user_approval_state == "approved"


def propose_promotion(event: MemoryEvent, book) -> object:
    """Route a non-auto event to the owner-approval ProposalBook.

    Returns the created Proposal. Risk class scales with trust: untrusted/tool
    content is RC3 (always needs owner approval); trusted content is RC2.
    """
    # Lazy import keeps this module importable without the jarvis_prime runtime.
    from hermes_cli.jarvis_prime.self_update import (
        ProposalEvidence,
        ProposalKind,
    )

    risk = "RC3" if event.trust_rank <= 1 else "RC2"
    evidence = (
        ProposalEvidence(
            kind="research_finding",
            text=f"candidate memory from {event.source} (trust={event.trust_level})",
            confidence=0.5 if event.trust_rank <= 1 else 0.8,
        ),
    )
    return book.propose(
        kind=ProposalKind.MEMORY_PROMOTION,
        target_path=f"memory://{event.sha256[:12]}",
        rationale=f"promote content from {event.source}",
        diff_intent=event.content[:200],
        evidence=evidence,
        risk_class=risk,
    )


def consider(event: MemoryEvent, book) -> tuple[str, Optional[object]]:
    """Decide an event's fate. Returns ``(decision, proposal_or_none)``.

    ``decision`` is ``"auto_promote"`` (caller may write to durable memory) or
    ``"proposed"`` (a pending owner-approval proposal was created). Untrusted
    content always takes the ``"proposed"`` path.
    """
    if should_auto_promote(event):
        return "auto_promote", None
    proposal = propose_promotion(event, book)
    return "proposed", proposal
