"""Fusion ranking — multi-signal retrieval result fusion, DB-free.

This is a faithful, database-free port of the fusion ranking in
``second_brain/knowledge/retrieval_orchestrator.py`` (`_rank`): it blends three
signals into one ``priority_score`` and sorts best-first —

    priority_score = w_sim · clamp(similarity, 0, 1)
                   + w_conf · confidence
                   + w_rec  · recency

where ``recency`` is a half-life decay of the candidate's age. The weights and
their ``SECOND_BRAIN_W_*`` env overrides match Second Brain exactly, so the two
agree on identical inputs.

Why a port: the full Second Brain orchestrator needs Postgres + Neo4j to *fetch*
candidates, but the *ranking* is pure arithmetic over already-scored results. This
module exposes that ranking so MUSE can fuse the candidates its own retrieval
(GraphRAG + evidence + memory) already produces — no database required. It does
not replace Second Brain's DB-backed pipeline; it makes the fusion *ranking*
usable in MUSE today.

Pure, deterministic, stdlib-only. No network, no DB, no LLM.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class FusionWeights:
    """Blend weights + recency half-life. Defaults + env vars mirror Second Brain."""

    similarity: float = 0.5
    confidence: float = 0.3
    recency: float = 0.2
    half_life_days: float = 30.0

    @classmethod
    def from_env(cls) -> "FusionWeights":
        return cls(
            similarity=_env_float("SECOND_BRAIN_W_SIMILARITY", 0.5),
            confidence=_env_float("SECOND_BRAIN_W_CONFIDENCE", 0.3),
            recency=_env_float("SECOND_BRAIN_W_RECENCY", 0.2),
            half_life_days=_env_float("SECOND_BRAIN_RECENCY_HALFLIFE", 30.0),
        )


def recency_score(
    created_at: Optional[datetime], *, now: datetime, half_life_days: float
) -> float:
    """Map a candidate's age to a recency weight in ``(0, 1]`` via half-life decay.

    Mirrors ``second_brain ... recency_score``. A missing ``created_at`` yields
    ``0.0`` (no recency signal) rather than guessing an age.
    """

    if created_at is None:
        return 0.0
    # Tolerate naive datetimes by assuming UTC, so subtraction never raises.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    ref = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (ref - created_at).total_seconds() / 86400.0)
    half_life = max(1e-6, half_life_days)
    return math.pow(0.5, age_days / half_life)


@dataclass
class FusionCandidate:
    """One retrieval candidate to be fused. ``similarity``/``confidence`` are the
    upstream signals; ``recency``/``priority_score``/``hybrid`` are filled by
    :func:`fuse`."""

    id: str
    similarity: float = 0.0
    confidence: float = 0.0
    created_at: Optional[datetime] = None
    sources: tuple[str, ...] = ()
    recency: float = 0.0
    priority_score: float = 0.0
    hybrid: bool = False

    @classmethod
    def from_obj(cls, obj: Any) -> "FusionCandidate":
        """Coerce a dict or attr-bearing object into a candidate."""

        get = (
            (lambda k, d=None: obj.get(k, d))
            if isinstance(obj, dict)
            else (lambda k, d=None: getattr(obj, k, d))
        )
        return cls(
            id=str(get("id", "")),
            similarity=float(get("similarity", 0.0) or 0.0),
            confidence=float(get("confidence", 0.0) or 0.0),
            created_at=get("created_at", None),
            sources=tuple(get("sources", ()) or ()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "similarity": self.similarity,
            "confidence": self.confidence,
            "recency": self.recency,
            "priority_score": self.priority_score,
            "sources": list(self.sources),
            "hybrid": self.hybrid,
        }


def fuse(
    candidates: Iterable[Any],
    *,
    weights: Optional[FusionWeights] = None,
    now: Optional[datetime] = None,
) -> list[FusionCandidate]:
    """Fuse + rank ``candidates`` best-first by blended ``priority_score``.

    ``candidates`` may be :class:`FusionCandidate`s, dicts, or attr-bearing
    objects (e.g. retrieval results) exposing ``id`` / ``similarity`` /
    ``confidence`` / optional ``created_at`` / ``sources``.
    """

    w = weights or FusionWeights()
    ref = now or datetime.now(timezone.utc)

    out: list[FusionCandidate] = []
    for raw in candidates:
        c = raw if isinstance(raw, FusionCandidate) else FusionCandidate.from_obj(raw)
        c.recency = recency_score(c.created_at, now=ref, half_life_days=w.half_life_days)
        similarity_unit = max(0.0, min(1.0, c.similarity))
        c.priority_score = (
            w.similarity * similarity_unit
            + w.confidence * c.confidence
            + w.recency * c.recency
        )
        c.hybrid = len(c.sources) > 1
        out.append(c)

    # Stable: id asc as the final tie-break, then priority_score desc.
    out.sort(key=lambda c: c.id)
    out.sort(key=lambda c: c.priority_score, reverse=True)
    return out


__all__ = [
    "FusionCandidate",
    "FusionWeights",
    "fuse",
    "recency_score",
]
