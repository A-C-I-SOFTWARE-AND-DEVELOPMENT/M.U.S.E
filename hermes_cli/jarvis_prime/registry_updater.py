"""REG-1 — model-registry updater (owner-gated, proposal-only).

Keeps the in-repo model registry (``config/model-catalog.yaml``) honest against
the live, remotely-published catalog manifest that ``hermes_cli.model_catalog``
already fetches and caches. When the live manifest lists curated provider models
the repo doesn't carry (or carries ones the live manifest dropped), this module
emits a structured **proposal** through the existing owner-approval
``ProposalBook`` — it never edits the YAML or reaches a model endpoint on its own.

Why proposal-only: adding a provider model id is a *new external surface* the
agent's ``/model`` picker and router can reach. That is exactly the class of
change the owner gate exists for. REG-1 surfaces the delta and the evidence;
the owner approves (``Yes, with authorization.``) before the existing
``proposal_executor`` ever builds an execution plan to touch the file. The
"auto-applying self-updates" half stays an owner-gated follow-up by design.

Design notes:
* Pure diff (`diff_provider_models`) is independent of the network and the
  ProposalBook, so it is trivially testable.
* Network/disk fetch goes through ``model_catalog.get_catalog`` which is itself
  fail-open (returns ``{}`` offline), so ``run_registry_update`` degrades to a
  no-op rather than raising when the manifest is unreachable.
* Risk scales with surface: adding brand-new model ids (new reachable endpoints)
  is RC3 (always needs owner approval); pruning stale ids is RC2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "model-catalog.yaml"
)


@dataclass(frozen=True)
class RegistryDelta:
    """Per-provider difference between the live manifest and the repo catalog."""

    provider: str
    added_ids: tuple[str, ...] = ()      # in live manifest, missing from repo
    removed_ids: tuple[str, ...] = ()    # in repo, gone from live manifest

    @property
    def is_empty(self) -> bool:
        return not self.added_ids and not self.removed_ids

    @property
    def risk_class(self) -> str:
        # Adding a reachable model endpoint is a new external surface ⇒ RC3.
        return "RC3" if self.added_ids else "RC2"

    def summary(self) -> str:
        bits: list[str] = []
        if self.added_ids:
            bits.append(f"+{len(self.added_ids)} ({', '.join(self.added_ids)})")
        if self.removed_ids:
            bits.append(f"-{len(self.removed_ids)} ({', '.join(self.removed_ids)})")
        return f"{self.provider}: " + "; ".join(bits) if bits else f"{self.provider}: no change"


@dataclass(frozen=True)
class _Entry:
    """One catalogued model: a display id plus every identifier it carries.

    The repo catalog and the live manifest use different id conventions for the
    same provider (the repo keys on a bare ``id`` plus a fully-qualified
    ``model`` slug; the manifest keys on the slug as ``id``). Collecting every
    identifier a model carries lets us match the same model across conventions
    instead of reporting it as both added and removed.
    """

    display: str
    keys: frozenset[str]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _provider_entries(catalog: Optional[dict[str, Any]], provider: str) -> list[_Entry]:
    """Extract one ``_Entry`` per model for a provider (tolerant of shapes)."""
    if not isinstance(catalog, dict):
        return []
    block = (catalog.get("providers") or {}).get(provider)
    if not isinstance(block, dict):
        return []
    entries: list[_Entry] = []
    for entry in block.get("models", []) or []:
        if isinstance(entry, dict):
            display = str(entry.get("id") or entry.get("model") or "").strip()
            keys = {_norm(entry.get("id")), _norm(entry.get("model"))} - {""}
        else:
            display = str(entry or "").strip()
            keys = {_norm(entry)} - {""}
        if display and keys:
            entries.append(_Entry(display=display, keys=frozenset(keys)))
    return entries


def _provider_model_ids(catalog: Optional[dict[str, Any]], provider: str) -> set[str]:
    """Back-compat helper: the set of display ids for a provider."""
    return {e.display for e in _provider_entries(catalog, provider)}


def _provider_names(*catalogs: Optional[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    for cat in catalogs:
        if isinstance(cat, dict):
            providers = cat.get("providers")
            if isinstance(providers, dict):
                names.update(str(k) for k in providers)
    return sorted(names)


def diff_provider_models(
    local: Optional[dict[str, Any]], remote: Optional[dict[str, Any]]
) -> list[RegistryDelta]:
    """Pure diff of provider model ids: repo (``local``) vs live (``remote``).

    Returns one non-empty :class:`RegistryDelta` per provider that differs,
    sorted by provider name. Providers absent from the live manifest are never
    reported as "removed" — a missing provider block in the manifest means
    "unknown / not published", not "delete everything we have".
    """
    deltas: list[RegistryDelta] = []
    for provider in _provider_names(local, remote):
        remote_entries = _provider_entries(remote, provider)
        # If the live manifest has nothing for this provider, treat it as
        # "no opinion" — don't propose deleting the repo's curated entries.
        if not remote_entries:
            continue
        local_entries = _provider_entries(local, provider)
        remote_keys: set[str] = set().union(*(e.keys for e in remote_entries))
        local_keys: set[str] = (
            set().union(*(e.keys for e in local_entries)) if local_entries else set()
        )
        # Entry-level match: a model is "added" only if NONE of its identifiers
        # appear anywhere in the repo (and vice-versa for "removed"), so a model
        # expressed under a different id convention is not double-counted.
        added = tuple(
            sorted(e.display for e in remote_entries if e.keys.isdisjoint(local_keys))
        )
        removed = tuple(
            sorted(e.display for e in local_entries if e.keys.isdisjoint(remote_keys))
        )
        delta = RegistryDelta(provider=provider, added_ids=added, removed_ids=removed)
        if not delta.is_empty:
            deltas.append(delta)
    return deltas


def load_local_catalog(path: Path | str | None = None) -> dict[str, Any]:
    """Load the in-repo ``config/model-catalog.yaml`` as a plain dict (fail-open)."""
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    try:
        import yaml

        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as err:
        logger.debug("[REG-1] could not load local catalog %s: %s", catalog_path, err)
        return {}


def propose_registry_updates(
    deltas: list[RegistryDelta],
    book,
    *,
    catalog_path: str = "config/model-catalog.yaml",
):
    """Emit one owner-gated proposal per provider delta. Returns the proposals.

    Nothing is written to disk and no endpoint is contacted — proposals are
    queued on ``book`` for owner review. RC3 deltas (new model surface) land in
    ``NEEDS_OWNER_APPROVAL`` automatically via ``ProposalBook.propose``.
    """
    from .self_update import ProposalEvidence, ProposalKind

    proposals = []
    for delta in deltas:
        if delta.is_empty:
            continue
        intent_bits: list[str] = []
        if delta.added_ids:
            intent_bits.append(
                f"add {len(delta.added_ids)} model(s) to providers.{delta.provider}: "
                + ", ".join(delta.added_ids)
            )
        if delta.removed_ids:
            intent_bits.append(
                f"remove {len(delta.removed_ids)} stale model(s) from "
                f"providers.{delta.provider}: " + ", ".join(delta.removed_ids)
            )
        evidence = (
            ProposalEvidence(
                kind="research_finding",
                text=(
                    "live model-catalog manifest differs from the in-repo "
                    f"registry for provider '{delta.provider}'"
                ),
                citation="hermes_cli.model_catalog.get_catalog()",
                confidence=0.7,
            ),
        )
        proposal = book.propose(
            kind=ProposalKind.MODEL_REGISTRY_UPDATE,
            target_path=catalog_path,
            rationale=(
                f"keep the model registry in sync with the published catalog "
                f"for provider '{delta.provider}'"
            ),
            diff_intent="; ".join(intent_bits),
            evidence=evidence,
            risk_class=delta.risk_class,
        )
        proposals.append(proposal)
    return proposals


def run_registry_update(
    book,
    *,
    catalog_path: Path | str | None = None,
    force_refresh: bool = True,
):
    """End-to-end REG-1 pass: fetch live manifest, diff vs repo, propose deltas.

    Fail-open: if the live manifest is unreachable (offline / disabled),
    ``get_catalog`` returns ``{}`` and this is a no-op returning ``[]``.
    Returns the list of created proposals (empty when in sync).
    """
    try:
        from hermes_cli.model_catalog import get_catalog

        remote = get_catalog(force_refresh=force_refresh)
    except Exception as err:  # never let a fetch error break a self-improve tick
        logger.debug("[REG-1] live catalog fetch failed: %s", err)
        remote = {}
    if not remote:
        return []
    local = load_local_catalog(catalog_path)
    deltas = diff_provider_models(local, remote)
    if not deltas:
        return []
    target = str(catalog_path) if catalog_path else "config/model-catalog.yaml"
    return propose_registry_updates(deltas, book, catalog_path=target)


def render_deltas(deltas: list[RegistryDelta]) -> str:
    """Human-readable one-block summary for owner review / logs."""
    if not deltas:
        return "REG-1: model registry is in sync with the live catalog."
    lines = ["REG-1 — MODEL REGISTRY DELTAS (proposal-only, owner-gated):"]
    for d in deltas:
        lines.append(f"  - {d.summary()}  [risk={d.risk_class}]")
    return "\n".join(lines)
