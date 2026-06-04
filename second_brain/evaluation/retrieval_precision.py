"""Precision@k for retrieval evaluation.

Pure functions over id lists so they run without any database or model. A
:class:`EvalCase` pairs a query's retrieved node ids with its ground-truth
relevant ids.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Set

__all__ = ["EvalCase", "precision_at_k", "mean_precision_at_k", "average_precision"]


@dataclass(slots=True)
class EvalCase:
    """A single labelled retrieval example."""

    query: str
    retrieved_ids: List[str] = field(default_factory=list)
    relevant_ids: List[str] = field(default_factory=list)


def _relevant_set(relevant: Sequence[str]) -> Set[str]:
    return {str(r) for r in relevant}


def precision_at_k(
    retrieved_ids: Sequence[str], relevant_ids: Sequence[str], k: int
) -> float:
    """Fraction of the top-``k`` retrieved ids that are relevant.

    Returns ``0.0`` when ``k <= 0`` or nothing was retrieved.
    """
    if k <= 0:
        return 0.0
    top_k = list(retrieved_ids)[:k]
    if not top_k:
        return 0.0
    relevant = _relevant_set(relevant_ids)
    hits = sum(1 for rid in top_k if rid in relevant)
    return hits / float(len(top_k))


def mean_precision_at_k(cases: Sequence[EvalCase], k: int) -> float:
    """Mean Precision@k across evaluation cases."""
    if not cases:
        return 0.0
    total = sum(precision_at_k(c.retrieved_ids, c.relevant_ids, k) for c in cases)
    return total / float(len(cases))


def average_precision(
    retrieved_ids: Sequence[str], relevant_ids: Sequence[str]
) -> float:
    """Average Precision (AP) — the area under the precision-recall curve.

    Mean AP across cases gives MAP, a standard ranking-quality summary.
    """
    relevant = _relevant_set(relevant_ids)
    if not relevant:
        return 0.0
    hits = 0
    cumulative = 0.0
    for index, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant:
            hits += 1
            cumulative += hits / float(index)
    return cumulative / float(len(relevant))
