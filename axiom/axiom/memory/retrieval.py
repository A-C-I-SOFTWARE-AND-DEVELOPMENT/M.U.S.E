"""Query-type-routed retrieval (replaces fixed 0.5/0.3/0.2 weights).

A query is classified as temporal, decision, conceptual, or factual,
and each class gets its own recency/similarity/confidence weighting —
"when did we…" should favor recency; "why did we…" should favor the
recorded confidence of decisions; "what is…" should favor similarity.
"""

from __future__ import annotations

import time

QUERY_TEMPORAL = "temporal"
QUERY_FACTUAL = "factual"
QUERY_CONCEPTUAL = "conceptual"
QUERY_DECISION = "decision"

# Keyword cues, checked in priority order.
_TEMPORAL_CUES = ("yesterday", "last week", "last time", "when did", "ago", "recently")
_DECISION_CUES = ("why did", "decided", "chose", "decision", "rationale", "should we")
_CONCEPTUAL_CUES = ("explain", "how does", "concept", "architecture", "design")
_FACTUAL_CUES = ("what is",)

# Weight presets: rec(ency) / sim(ilarity) / conf(idence). Each sums to 1.
WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    QUERY_TEMPORAL: {"rec": 0.6, "sim": 0.3, "conf": 0.1},
    QUERY_FACTUAL: {"rec": 0.1, "sim": 0.6, "conf": 0.3},
    QUERY_CONCEPTUAL: {"rec": 0.2, "sim": 0.45, "conf": 0.35},
    QUERY_DECISION: {"rec": 0.2, "sim": 0.3, "conf": 0.5},
}


def classify_query(query: str) -> str:
    q = query.lower()
    if any(cue in q for cue in _TEMPORAL_CUES):
        return QUERY_TEMPORAL
    if any(cue in q for cue in _DECISION_CUES):
        return QUERY_DECISION
    if any(cue in q for cue in _CONCEPTUAL_CUES):
        return QUERY_CONCEPTUAL
    return QUERY_FACTUAL


def weights_for(query: str) -> dict[str, float]:
    return dict(WEIGHT_PRESETS[classify_query(query)])


def _similarity(query: str, content: str) -> float:
    """Token-overlap similarity in [0, 1]."""
    a = set(query.lower().split())
    b = set(content.lower().split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _recency(created_ts: float, now: float, horizon_s: float = 30 * 86400.0) -> float:
    age = max(0.0, now - created_ts)
    return max(0.0, 1.0 - age / horizon_s)


def score(
    query: str,
    item: dict,
    now: float | None = None,
) -> float:
    """Score one memory dict (content/created_ts/retrievability) for *query*."""
    w = weights_for(query)
    now = now or time.time()
    sim = _similarity(query, item["content"])
    rec = _recency(item.get("created_ts", now), now)
    conf = float(item.get("retrievability", 1.0))
    return w["rec"] * rec + w["sim"] * sim + w["conf"] * conf


def retrieve(query: str, items: list[dict], k: int = 5) -> list[dict]:
    """Top-k items by routed score."""
    ranked = sorted(items, key=lambda it: score(query, it), reverse=True)
    return ranked[:k]
