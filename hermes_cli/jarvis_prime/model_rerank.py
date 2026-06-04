"""W5 — model-lane reranker for the JARVIS Prime NL compiler.

Given a compile's task class and risk class, deterministically recommend a
model lane. Evidence preference order:

  1. **MEASURED** scorecard evidence (:class:`ScorecardBook`) — the strongest
     signal, because it reflects outcomes actually observed on this host.
  2. **OSS catalog** (:func:`load_oss_catalog`) — the cross-referenced
     open-weight model catalog, filtered to installed providers.
  3. **Route hint** — the cheap heuristic lane from
     :func:`route_request`, defaulting to Claude.

This module NEVER raises when the scorecard or catalog files are absent or
corrupt: every external call is wrapped so a missing file degrades to the
next evidence tier rather than propagating an exception. The result is
deterministic and makes no network call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    ModelLaneHint,
)
from hermes_cli.oss_model_brain import (
    installed_provider_names,
    load_oss_catalog,
)

__all__ = [
    "INTENT_TO_TASK_CLASS",
    "task_class_for",
    "LaneRecommendation",
    "recommend_model_lane",
]


# ---------------------------------------------------------------------------
# Intent -> task-class mapping
# ---------------------------------------------------------------------------

# Maps a coding intent to the scorecard/catalog "task class" used to rank
# evidence. CodingIntent has NO DEBUG member; TEST maps to "test_debug".
INTENT_TO_TASK_CLASS: dict[CodingIntent, str] = {
    CodingIntent.IMPLEMENT: "coding_build",
    CodingIntent.REFACTOR: "coding_build",
    CodingIntent.DOCUMENT: "coding_build",
    CodingIntent.REVIEW: "coding_review",
    CodingIntent.AUDIT: "coding_review",
    CodingIntent.SECURITY: "coding_review",
    CodingIntent.RESEARCH: "research",
    CodingIntent.TEST: "test_debug",
}

_DEFAULT_TASK_CLASS = "coding_build"


def task_class_for(intent: CodingIntent) -> str:
    """Return the task class for ``intent`` (default ``"coding_build"``)."""
    return INTENT_TO_TASK_CLASS.get(intent, _DEFAULT_TASK_CLASS)


# ---------------------------------------------------------------------------
# Recommendation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaneRecommendation:
    """A deterministic model-lane recommendation for a compile.

    ``source`` is one of ``"scorecard"`` | ``"oss_catalog"`` | ``"route_hint"``,
    indicating which evidence tier produced ``lane``. ``candidates`` carries
    the ordered shortlist (best first) the tier considered, for transparency.
    """

    lane: str
    source: str
    rationale: str
    candidates: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "lane": self.lane,
            "source": self.source,
            "rationale": self.rationale,
            "candidates": list(self.candidates),
        }


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------


def _from_scorecard(
    task_class: str, risk_class: str, scorecard_path
) -> Optional[LaneRecommendation]:
    """Best measured lane for the task/risk, or ``None`` if no evidence.

    Wraps the scorecard load+recommend so a missing or corrupt scorecard
    file degrades to the next tier instead of raising.
    """
    try:
        book = ScorecardBook.load(scorecard_path)
        ranked = book.recommend(
            task_class, risk_class=risk_class, task_class=task_class
        )
    except Exception:
        return None
    if not ranked:
        return None
    candidates = tuple(model for model, _score, _samples in ranked)
    top_model, top_score, top_samples = ranked[0]
    rationale = (
        f"measured scorecard: {top_model} leads {task_class}/{risk_class} "
        f"(mean {top_score:.2f} over {top_samples} sample"
        f"{'s' if top_samples != 1 else ''})."
    )
    return LaneRecommendation(
        lane=top_model,
        source="scorecard",
        rationale=rationale,
        candidates=candidates,
    )


def _from_oss_catalog(task_class: str) -> Optional[LaneRecommendation]:
    """Best OSS-catalog lane for the task, or ``None`` if none match.

    Wraps the catalog load+recommend so a missing/corrupt catalog or
    provider registry degrades to the next tier instead of raising.
    """
    try:
        catalog = load_oss_catalog()
        providers = installed_provider_names()
        hits = catalog.recommend(task_class, available_providers=providers)
    except Exception:
        return None
    if not hits:
        return None
    candidates = tuple(model.id for model in hits)
    top = hits[0]
    rationale = (
        f"oss catalog: {top.id} is the best open-weight fit for {task_class} "
        f"among installed providers."
    )
    return LaneRecommendation(
        lane=top.id,
        source="oss_catalog",
        rationale=rationale,
        candidates=candidates,
    )


def recommend_model_lane(
    task_class: str,
    risk_class: str,
    *,
    fallback_hint: Optional[ModelLaneHint] = None,
    scorecard_path=None,
) -> LaneRecommendation:
    """Deterministically recommend a model lane for a compile.

    Prefers MEASURED scorecard evidence, then the OSS catalog (filtered to
    installed providers), then the route hint. Never raises when the
    scorecard/catalog files are absent or corrupt, and makes no network
    call — each external call is wrapped so a missing file simply falls
    through to the next evidence tier.
    """
    measured = _from_scorecard(task_class, risk_class, scorecard_path)
    if measured is not None:
        return measured

    catalog = _from_oss_catalog(task_class)
    if catalog is not None:
        return catalog

    lane = (fallback_hint or ModelLaneHint.CLAUDE).value
    rationale = (
        f"no measured or catalog evidence for {task_class}/{risk_class}; "
        f"using route hint lane '{lane}'."
    )
    return LaneRecommendation(
        lane=lane,
        source="route_hint",
        rationale=rationale,
        candidates=(lane,),
    )
