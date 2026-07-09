"""Seat portfolio management — evidence-backed, owner-gated seat model swaps.

The orchestrator roster (``hermes_cli.orchestrator_trio.FULL_ROSTER``) pins one
model per seat. This module answers two questions about that portfolio:

* ``seat_report()`` — for every seat: what model is pinned, is the profile
  installed, what *measured* scorecard evidence exists for that model's
  family, and which same-provider catalog models are plausible alternatives.
* ``build_seat_swap_proposal()`` / ``append_seat_proposal()`` — turn "swap
  seat X to candidate Y" into an owner-gated :class:`~hermes_cli.jarvis_prime.
  self_update.Proposal` queued in the same ``proposals.jsonl`` store the
  ``proposals {list|approve|reject}`` CLI reads.

Hard rules (mirrors the Gemma promotion lane in ``gemma_cli``):

* **Proposal-only.** Nothing here ever writes a profile's ``config.yaml``,
  never applies a swap, and never opens a PR. Approval + execution stay
  separate, owner-gated steps.
* **Vendor benchmarks never promote.** Only measured scorecards
  (:class:`~hermes_cli.jarvis_prime.model_scorecard.ScorecardBook`) count as
  evidence; when none exist the proposal says so explicitly instead of
  dressing catalog metadata up as measurement.

All imports of heavier hermes modules are lazy so this module stays cheap to
import in light contexts.
"""

from __future__ import annotations

from typing import Any, Optional


def _family_scorecard_summary(book: Any, model: str) -> dict[str, Any]:
    """Measured-evidence summary for ``model``'s family. Honest when empty."""
    from hermes_cli.jarvis_prime.model_scorecard import model_family

    family = model_family(model)
    cards = [c for c in book.scorecards if model_family(c.model) == family]
    if not cards:
        return {
            "family": family,
            "measured": False,
            "samples": 0,
            "mean_score": None,
            "models": [],
        }
    return {
        "family": family,
        "measured": True,
        "samples": len(cards),
        "mean_score": round(sum(c.score for c in cards) / len(cards), 4),
        "models": sorted({c.model for c in cards}),
    }


def _candidate_alternatives(catalog: Any, role: Any) -> list[str]:
    """Same-provider catalog refs sharing ≥1 tag with the seat's model.

    Deterministic (sorted refs); excludes the seat's own pinned catalog entry.
    Returns ``[]`` when the seat's ``catalog_ref`` is missing from the catalog
    rather than guessing.
    """
    entry = catalog.by_ref(role.catalog_ref)
    if entry is None:
        return []
    tags = set(entry.tags)
    return sorted(
        m.ref
        for m in catalog.models_for_provider(role.provider)
        if m.ref != entry.ref and tags & set(m.tags)
    )


def seat_report(*, book: Any = None) -> dict[str, Any]:
    """Report the full seat portfolio: pins, install state, evidence, options.

    Returns::

        {
          "seats": {
            <profile>: {
              "title": ..., "provider": ..., "catalog_ref": ...,
              "installed": bool,
              "pinned_model": str | None,   # measured from the profile config
              "preset_model": str,          # what the roster preset would pin
              "scorecards": {family, measured, samples, mean_score, models},
              "candidates": [catalog refs, ...],
            }, ...
          },
          "scorecards_recorded": int,       # total cards in the book
        }

    A missing scorecard file is reported honestly as zero measured evidence,
    never as an error.
    """
    from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
    from hermes_cli.orchestrator_trio import FULL_ROSTER, trio_status
    from hermes_model_catalog import load_catalog

    if book is None:
        book = ScorecardBook.load()
    catalog = load_catalog()
    status = trio_status()

    seats: dict[str, Any] = {}
    for role in FULL_ROSTER:
        seat_status = status.get(role.profile) or {"installed": False, "model": None}
        raw_model = seat_status.get("model")
        pinned: Optional[str] = raw_model if isinstance(raw_model, str) else None
        seats[role.profile] = {
            "title": role.title,
            "provider": role.provider,
            "catalog_ref": role.catalog_ref,
            "installed": bool(seat_status.get("installed")),
            "pinned_model": pinned,
            "preset_model": role.model,
            "scorecards": _family_scorecard_summary(book, pinned or role.model),
            "candidates": _candidate_alternatives(catalog, role),
        }
    return {
        "seats": seats,
        "scorecards_recorded": len(book.scorecards),
    }


def build_seat_swap_proposal(
    seat: str, candidate_ref: str, *, book: Any = None
) -> dict[str, Any]:
    """Build (but never apply) an owner-gated proposal to re-pin ``seat``.

    Validates that ``seat`` is a roster profile and ``candidate_ref`` resolves
    in the model catalog; raises :class:`ValueError` otherwise. The returned
    dict is a :class:`~hermes_cli.jarvis_prime.self_update.Proposal` dict plus
    ``rollback`` and ``seat_swap`` keys — the same shape the Gemma promotion
    lane appends to ``proposals.jsonl``. This function does **not** write the
    profile's ``config.yaml`` and does **not** persist the proposal; pass the
    result to :func:`append_seat_proposal` to queue it for owner review.
    """
    from hermes_cli import profiles as profiles_mod
    from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
    from hermes_cli.jarvis_prime.self_update import (
        Proposal,
        ProposalEvidence,
        ProposalKind,
    )
    from hermes_cli.orchestrator_trio import FULL_ROSTER
    from hermes_model_catalog import load_catalog

    role = next((r for r in FULL_ROSTER if r.profile == seat), None)
    if role is None:
        known = ", ".join(r.profile for r in FULL_ROSTER)
        raise ValueError(f"unknown seat {seat!r} — roster seats: {known}")

    candidate = load_catalog().by_ref(candidate_ref)
    if candidate is None:
        raise ValueError(
            f"unknown candidate ref {candidate_ref!r} — not in config/model-catalog.yaml"
        )

    if book is None:
        book = ScorecardBook.load()

    profile_dir = profiles_mod.get_profile_dir(role.profile)
    current_model, _provider = profiles_mod._read_config_model(profile_dir)
    current_model = current_model or role.model  # preset pin when uninstalled
    target_path = str(profile_dir / "config.yaml")

    evidence_summary = _family_scorecard_summary(book, candidate.model)
    if evidence_summary["measured"]:
        rationale = (
            f"Swap seat '{seat}' ({role.title}) from '{current_model}' to "
            f"'{candidate.model}' ({candidate.ref}). Measured evidence: "
            f"{evidence_summary['samples']} scorecard(s) for family "
            f"'{evidence_summary['family']}' with mean score "
            f"{evidence_summary['mean_score']:.2f} "
            f"(models: {', '.join(evidence_summary['models'])})."
        )
        evidence = (
            ProposalEvidence(
                kind="scorecard",
                text=(
                    f"{evidence_summary['samples']} measured scorecard(s) for "
                    f"family '{evidence_summary['family']}', mean score "
                    f"{evidence_summary['mean_score']:.2f}."
                ),
                confidence=1.0,
            ),
        )
    else:
        rationale = (
            f"Swap seat '{seat}' ({role.title}) from '{current_model}' to "
            f"'{candidate.model}' ({candidate.ref}). "
            "no measured scorecards — evidence is catalog metadata only, "
            "do not approve without a bench run."
        )
        evidence = (
            ProposalEvidence(
                kind="catalog_metadata",
                text=(
                    f"catalog metadata only: {candidate.ref} tags="
                    f"{list(candidate.tags)}, context={candidate.context}. "
                    "No measured scorecards exist for this model family — "
                    "run a bench before approving."
                ),
                confidence=0.2,
            ),
        )

    proposal = Proposal(
        kind=ProposalKind.ROUTING_RULE_UPDATE,
        target_path=target_path,
        rationale=rationale,
        diff_intent=(
            f"re-pin the '{seat}' profile's model block to provider "
            f"'{candidate.provider}', model '{candidate.model}' in "
            f"{target_path} (owner-gated; this proposal never edits the file)"
        ),
        evidence=evidence,
        risk_class="RC2",
        requires_owner_approval=True,
    )
    d = proposal.to_dict()
    d["rollback"] = (
        f"reversible: re-pin '{seat}' to '{current_model}' (provider "
        f"'{role.provider}') in {target_path}; install_trio(force=True) "
        "restores the full preset roster."
    )
    d["seat_swap"] = {
        "seat": seat,
        "current_model": current_model,
        "candidate_ref": candidate.ref,
        "candidate_model": candidate.model,
        "candidate_provider": candidate.provider,
        "scorecards": evidence_summary,
    }
    return d


def append_seat_proposal(proposal: dict[str, Any]) -> bool:
    """Append a proposal dict to ``${HERMES_HOME}/jarvis_prime/proposals.jsonl``.

    Reuses the Gemma promotion lane's appender (one JSON line, best-effort
    ``chmod 600``). Returns ``True`` when the line was written.
    """
    from hermes_cli.jarvis_prime.gemma_cli import _append_proposal

    return _append_proposal(proposal)


__all__ = [
    "seat_report",
    "build_seat_swap_proposal",
    "append_seat_proposal",
]
