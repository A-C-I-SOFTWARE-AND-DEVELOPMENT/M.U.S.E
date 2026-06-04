"""Hallucination proxy detection.

A lightweight, reference-free proxy for hallucination: the share of an
answer's claims that are *not* supported by the retrieved context. It is the
complement of grounding coverage and is intended as a guardrail signal, not a
ground-truth factuality judgement (which requires a stronger verifier).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from .grounding_tests import grounding_coverage, split_claims, token_overlap

__all__ = ["HallucinationReport", "hallucination_score"]


@dataclass(slots=True)
class HallucinationReport:
    """Result of a hallucination-proxy evaluation."""

    score: float  # fraction of unsupported claims in [0, 1]
    total_claims: int
    unsupported_claims: List[str] = field(default_factory=list)
    flagged: bool = False
    max_overlaps: List[float] = field(default_factory=list)


def hallucination_score(
    answer: str,
    contexts: Sequence[str],
    *,
    support_threshold: float = 0.5,
    flag_threshold: float = 0.34,
) -> HallucinationReport:
    """Estimate the unsupported-claim ratio for ``answer`` given ``contexts``.

    Parameters
    ----------
    answer:
        Generated answer to scrutinise.
    contexts:
        Retrieved context blocks the answer should rely on.
    support_threshold:
        Per-claim overlap needed to count a claim as grounded.
    flag_threshold:
        If the unsupported ratio meets/exceeds this, ``flagged`` is ``True``.
    """
    claims = split_claims(answer)
    if not claims:
        return HallucinationReport(score=0.0, total_claims=0)
    grounding = grounding_coverage(answer, contexts, threshold=support_threshold)
    score = 1.0 - grounding.coverage
    max_overlaps = [
        max((token_overlap(claim, ctx) for ctx in contexts), default=0.0)
        for claim in claims
    ]
    return HallucinationReport(
        score=score,
        total_claims=grounding.total_claims,
        unsupported_claims=grounding.unsupported,
        flagged=score >= flag_threshold,
        max_overlaps=[round(o, 4) for o in max_overlaps],
    )
