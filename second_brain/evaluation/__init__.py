"""Evaluation framework for the Second Brain module.

Implements retrieval and grounding metrics plus a latency harness:

* :func:`precision_at_k`, :func:`average_precision` — ranking precision
* :func:`recall_at_k`, :func:`f1_at_k` — coverage of relevant items
* :func:`grounding_coverage` — answer faithfulness to retrieved context
* :func:`hallucination_score` — reference-free unsupported-claim proxy
* :class:`LatencyBenchmark` — latency/throughput measurement

All metrics are pure functions over plain data structures, so the suite runs
without a database, model, or network.
"""

from __future__ import annotations

from .grounding_tests import GroundingResult, grounding_coverage, split_claims
from .hallucination_proxy import HallucinationReport, hallucination_score
from .latency_benchmark import LatencyBenchmark, LatencyResult, percentile
from .recall import f1_at_k, mean_f1_at_k, mean_recall_at_k, recall_at_k
from .retrieval_precision import (
    EvalCase,
    average_precision,
    mean_precision_at_k,
    precision_at_k,
)

__all__ = [
    "EvalCase",
    "precision_at_k",
    "mean_precision_at_k",
    "average_precision",
    "recall_at_k",
    "mean_recall_at_k",
    "f1_at_k",
    "mean_f1_at_k",
    "GroundingResult",
    "grounding_coverage",
    "split_claims",
    "HallucinationReport",
    "hallucination_score",
    "LatencyBenchmark",
    "LatencyResult",
    "percentile",
]
