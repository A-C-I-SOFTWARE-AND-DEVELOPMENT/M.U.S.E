"""Full-registry model ranking — choose the best model from the ENTIRE catalog.

The default router (:func:`hermes_cli.jarvis_prime.task_router.route_for_task`)
ranks models only within the *enabled* route tiers (local-first → hosted →
workers → paid), so a strong model in a disabled tier never competes. This
module is the opt-in complement: it enumerates the **entire** open-model catalog
(:mod:`hermes_cli.oss_model_brain`) with **no tier gating** and ranks every
family on the merits — measured scorecard evidence first, then catalog signals
(task fit, benchmark quality, tier). It lets MUSE pick any model in the registry
it judges best, not just the ones the local-first policy happened to enable.

Pure, deterministic, network-free, and strictly additive: it reads the in-repo
catalog plus the local scorecard book and returns a ranking. It never calls a
provider, never edits the registry, and does not change the default routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from hermes_cli.oss_model_brain import OssCatalog, OssModel, load_oss_catalog

_TIER_RANK = {"frontier": 3, "strong": 2, "local": 1}


@dataclass
class RankedModel:
    """One catalog family scored for a task across the whole registry."""

    model: str
    tier: str
    measured_score: Optional[float] = None
    samples: int = 0
    task_fit: bool = False
    quality: float = 0.0  # top benchmark — a coarse quality proxy
    vendor: str = ""

    @property
    def measured(self) -> bool:
        return self.measured_score is not None

    @property
    def sort_key(self) -> tuple:
        # Measured evidence is authoritative; among unmeasured candidates rank by
        # task fit, then benchmark quality, then tier. Sorted descending.
        return (
            1 if self.measured else 0,
            self.measured_score if self.measured_score is not None else 0.0,
            1.0 if self.task_fit else 0.0,
            self.quality,
            float(_TIER_RANK.get(self.tier, 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "tier": self.tier,
            "measured_score": self.measured_score,
            "samples": self.samples,
            "task_fit": self.task_fit,
            "quality": self.quality,
            "vendor": self.vendor,
        }


def _measured_scores(task: str, book: Any) -> dict[str, tuple[float, int]]:
    """``{model_id: (score, samples)}`` from the scorecard book, best-effort.

    ``task`` is matched against the scorecard ``task_type`` as-is; evidence is
    only applied when the scorecard task name matches the one passed here.
    """

    if book is None:
        try:
            from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook

            book = ScorecardBook.load()
        except Exception:  # pragma: no cover - defensive (stripped install)
            return {}
    try:
        rows = book.recommend(task, task_class=task)
    except Exception:  # pragma: no cover - defensive
        return {}
    return {model: (score, n) for model, score, n in rows}


def _family_of(model: str) -> str:
    """Coarse family id for ``model`` (best-effort; identity on failure)."""

    try:
        from hermes_cli.jarvis_prime.model_scorecard import model_family

        return model_family(model) or model
    except Exception:  # pragma: no cover - defensive (stripped install)
        return model


def _by_family(
    measured: dict[str, tuple[float, int]],
) -> dict[str, tuple[float, int]]:
    """Best score per model family, so a scorecard recorded under a variant id
    (e.g. ``gemma4-e4b``) still informs its family (``gemma4``) — mirroring the
    family-level fallback in :mod:`hermes_cli.jarvis_prime.task_router`."""

    out: dict[str, tuple[float, int]] = {}
    for model, sn in measured.items():
        fam = _family_of(model)
        if fam and (fam not in out or sn[0] > out[fam][0]):
            out[fam] = sn
    return out


def _task_fit(catalog: OssCatalog, model: OssModel, task: str) -> bool:
    want_local = task.startswith("local_")
    base = task[len("local_") :] if want_local else task
    # A local_* task only fits a family that actually has a local variant —
    # mirrors OssCatalog._ordered_for_task's locality narrowing.
    if want_local and not model.local:
        return False
    if task in model.best_for or base in model.best_for:
        return True
    routed = catalog.routing_dict.get(task) or catalog.routing_dict.get(base)
    return bool(routed and model.id in routed)


def rank_full_registry(
    task: str,
    *,
    catalog: Optional[OssCatalog] = None,
    book: Any = None,
) -> list[RankedModel]:
    """Rank **every** catalog family for ``task``, best first (no tier gating).

    ``book`` is any object exposing ``recommend(task, task_class=...)`` →
    ``[(model, score, samples), ...]``; the local scorecard book is loaded when
    omitted. Family-level scorecard ids match a catalog family by exact id.
    """

    task = (task or "").strip().lower()
    catalog = catalog or load_oss_catalog()
    measured = _measured_scores(task, book)
    measured_by_family = _by_family(measured)

    ranked: list[RankedModel] = []
    for fam in catalog.families:
        # Exact id wins; else a scorecard recorded under a *variant* of this
        # family (its family id == fam.id) informs it. Catalog ids are already
        # family-level, so look up by fam.id (not its family-of) to avoid
        # spreading one score across unrelated same-family catalog entries.
        score_n = measured.get(fam.id)
        if score_n is None and measured_by_family:
            score_n = measured_by_family.get(fam.id)
        ranked.append(
            RankedModel(
                model=fam.id,
                tier=fam.tier,
                measured_score=score_n[0] if score_n else None,
                samples=score_n[1] if score_n else 0,
                task_fit=_task_fit(catalog, fam, task),
                quality=fam.top_benchmark,
                vendor=fam.vendor,
            )
        )

    # Stable: name asc as the final tie-break, then sort_key desc.
    ranked.sort(key=lambda r: r.model)
    ranked.sort(key=lambda r: r.sort_key, reverse=True)
    return ranked


def best_model(
    task: str,
    *,
    catalog: Optional[OssCatalog] = None,
    book: Any = None,
) -> Optional[RankedModel]:
    """The single best model across the entire registry for ``task``."""

    ranked = rank_full_registry(task, catalog=catalog, book=book)
    return ranked[0] if ranked else None


def explain(decision: Sequence[RankedModel], *, top: int = 5) -> str:
    """A short human-readable ranking summary."""

    if not decision:
        return "no models in the registry"
    lines = []
    for r in decision[:top]:
        if r.measured:
            basis = f"measured {r.measured_score:.2f} (n={r.samples})"
        elif r.task_fit:
            basis = f"task-fit, benchmark {r.quality:.1f}, {r.tier}"
        else:
            basis = f"benchmark {r.quality:.1f}, {r.tier}"
        lines.append(f"{r.model:<24} {basis}")
    return "\n".join(lines)


__all__ = [
    "RankedModel",
    "best_model",
    "explain",
    "rank_full_registry",
]
