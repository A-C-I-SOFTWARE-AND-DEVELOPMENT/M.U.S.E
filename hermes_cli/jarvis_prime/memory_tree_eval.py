"""Held-out retrieval evaluation for the Memory Tree dense lane.

This is the empirical gate for Phase 1 of the JEPA integration: it measures
whether the optional dense-embedding lane actually beats plain keyword search
on a fixed query -> relevant-node set, and disposes of the result through the
same verifier the rest of MUSE uses
(:func:`hermes_cli.jarvis_prime.benchmark_gate.evaluate_improvement`).

Contract (from the plan): *if the candidate does not clear ``min_margin`` on a
held-out set, keep keyword search.* This module returns a structured result
whose ``gate.outcome`` is ``PASS`` only when the blended lane's MRR beats the
keyword baseline by at least ``min_margin`` — the signal for turning the lane
on in production.

The evaluation reuses the real :meth:`MemoryTreeStore.search`, so it scores the
exact ranking users would get. It is deterministic and dependency-light: the
only heavy piece (the embedding backend) is whatever the store resolves, so
tests can inject a fake backend and CI never needs a model download.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence


@dataclass(frozen=True)
class RetrievalCase:
    """One held-out query and the node ids that should be retrieved for it."""

    query: str
    relevant_ids: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalMetrics:
    """recall@k and mean reciprocal rank over a case set."""

    recall_at_k: float
    mrr: float
    k: int
    n_cases: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "k": self.k,
            "n_cases": self.n_cases,
        }


def _ranked_ids(store: Any, query: str, k: int) -> list[str]:
    # include_pending=True so the eval sees the full corpus, not just the
    # live-recall subset (the review gate is orthogonal to ranking quality).
    hits = store.search(query, limit=k, include_pending=True)
    return [h.node.id for h in hits]


def _metrics(store: Any, cases: Sequence[RetrievalCase], k: int) -> RetrievalMetrics:
    recall_hits = 0
    mrr_total = 0.0
    n = 0
    for case in cases:
        rel = set(case.relevant_ids)
        if not rel:
            continue
        n += 1
        ranked = _ranked_ids(store, case.query, k)
        if rel & set(ranked[:k]):
            recall_hits += 1
        for rank, nid in enumerate(ranked, 1):
            if nid in rel:
                mrr_total += 1.0 / rank
                break
    denom = n or 1
    return RetrievalMetrics(
        recall_at_k=recall_hits / denom,
        mrr=mrr_total / denom,
        k=k,
        n_cases=n,
    )


def _force_lane_off(store: Any) -> tuple:
    """Pin the dense lane off (returns the prior state for restoration)."""

    saved = (
        getattr(store, "_emb_ready", False),
        getattr(store, "_emb_index", None),
        getattr(store, "_emb_weight", 0.0),
    )
    store._emb_ready = True
    store._emb_index = None
    store._emb_weight = 0.0
    return saved


def _restore_lane(store: Any, saved: tuple) -> None:
    store._emb_ready, store._emb_index, store._emb_weight = saved


def score_retrieval(
    store: Any,
    cases: Iterable[RetrievalCase],
    *,
    k: int = 5,
    task: str = "memory_tree_retrieval",
    min_margin: float = 0.0,
    metric: str = "mrr",
) -> dict[str, Any]:
    """Compare keyword-only vs dense-blended retrieval and run the gate.

    ``store`` must have the dense lane configured (env flag / positive
    ``embedding_weight`` / an injected ``_emb_index``); the *candidate* uses
    that configuration and the *baseline* is the same store with the lane
    forced off, so the only difference measured is the dense term.

    Returns a dict with ``baseline`` / ``candidate`` metrics and the
    :class:`GateResult` from ``evaluate_improvement`` (higher-is-better on the
    chosen ``metric``). ``gate.outcome == PASS`` is the "turn the lane on"
    signal; anything else means keep keyword search.
    """

    from hermes_cli.jarvis_prime.benchmark_gate import evaluate_improvement

    cases = list(cases)

    # Candidate first, while the lane is in its configured state.
    candidate = _metrics(store, cases, k)

    # Baseline: identical store, dense lane pinned off.
    saved = _force_lane_off(store)
    try:
        baseline = _metrics(store, cases, k)
    finally:
        _restore_lane(store, saved)

    b_val = getattr(baseline, metric)
    c_val = getattr(candidate, metric)
    gate = evaluate_improvement(b_val, c_val, task=task, min_margin=min_margin)

    return {
        "task": task,
        "metric": metric,
        "min_margin": min_margin,
        "baseline": baseline.to_dict(),
        "candidate": candidate.to_dict(),
        "baseline_score": b_val,
        "candidate_score": c_val,
        "gate": gate.to_dict() if hasattr(gate, "to_dict") else {
            "outcome": getattr(gate.outcome, "value", str(gate.outcome)),
            "reason": getattr(gate, "reason", ""),
        },
        "promote": getattr(gate.outcome, "value", str(gate.outcome)) == "pass",
    }
