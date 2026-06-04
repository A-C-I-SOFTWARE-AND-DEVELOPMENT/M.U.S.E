"""Recall@k (and F1@k) for retrieval evaluation."""

from __future__ import annotations

from typing import Sequence

from .retrieval_precision import EvalCase, precision_at_k

__all__ = ["recall_at_k", "mean_recall_at_k", "f1_at_k", "mean_f1_at_k"]


def recall_at_k(
    retrieved_ids: Sequence[str], relevant_ids: Sequence[str], k: int
) -> float:
    """Fraction of relevant ids found within the top-``k`` retrieved ids."""
    relevant = {str(r) for r in relevant_ids}
    if not relevant or k <= 0:
        return 0.0
    top_k = list(retrieved_ids)[:k]
    hits = sum(1 for rid in top_k if rid in relevant)
    return hits / float(len(relevant))


def mean_recall_at_k(cases: Sequence[EvalCase], k: int) -> float:
    """Mean Recall@k across evaluation cases."""
    if not cases:
        return 0.0
    total = sum(recall_at_k(c.retrieved_ids, c.relevant_ids, k) for c in cases)
    return total / float(len(cases))


def f1_at_k(
    retrieved_ids: Sequence[str], relevant_ids: Sequence[str], k: int
) -> float:
    """Harmonic mean of Precision@k and Recall@k."""
    precision = precision_at_k(retrieved_ids, relevant_ids, k)
    recall = recall_at_k(retrieved_ids, relevant_ids, k)
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def mean_f1_at_k(cases: Sequence[EvalCase], k: int) -> float:
    """Mean F1@k across evaluation cases."""
    if not cases:
        return 0.0
    total = sum(f1_at_k(c.retrieved_ids, c.relevant_ids, k) for c in cases)
    return total / float(len(cases))
