"""AXIOM attestation adapter for Foundry specialist promotion (§71/§72).

AXIOM's Unit/Verifier does not natively model ML lineage (confirmed Phase-0
audit §5), so this adapter does NOT distort Units to fit. Instead it:

  1. Builds a promotion Unit whose EARS intent + effect vocabulary describe the
     act of promotion (a `regulated:` effect — visibly exceptional by design).
  2. Verifies it through the real AXIOM Verifier (intent:EARS, effects:vocab,
     refs:resolve-or-fail, contracts:z3, cycle detection).
  3. Records the ML lineage (base/schema/dataset/adapter/model/eval hashes) as
     a ledger event payload — the ledger accepts arbitrary JSON payloads —
     linked to the verified unit_hash + attestation event_hash.

The result is a verifiable lineage chain anchored in AXIOM's ledger without
weakening any AXIOM check.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_AXIOM_ROOT = Path(__file__).resolve().parent.parent / "axiom"
if str(_AXIOM_ROOT) not in sys.path:
    sys.path.insert(0, str(_AXIOM_ROOT))

from axiom.core.canonical import Unit                      # noqa: E402
from axiom.core.registry import Registry                   # noqa: E402
from axiom.core.ledger import Ledger                       # noqa: E402
from axiom.core.verifier import Verifier, Attestation      # noqa: E402

PROMOTION_EFFECT = "regulated:model.promotion"


@dataclass
class PromotionAttestation:
    specialist_id: str
    unit_hash: str
    attestation_event_hash: str
    lineage_event_hash: str
    checks: tuple[str, ...]
    warnings: tuple[str, ...]
    lineage: dict[str, Any]
    at: float = field(default_factory=time.time)


def build_promotion_unit(specialist_id: str, niche_id: str, version: str) -> Unit:
    """EARS intent for the promotion act. No params, no body ops, one
    regulated effect. Contracts stay empty (nothing Z3-provable about an ML
    hash chain; the lineage evidence lives in the ledger payload)."""
    intent = (
        f"WHEN the Foundry proposes promotion of specialist {specialist_id} "
        f"version {version} for niche {niche_id}, THE system SHALL record the "
        f"promotion only after all promotion gates have passed."
    )
    return Unit(
        name=f"foundry.promote.{specialist_id}.{version}",
        doc=f"Promotion of {specialist_id} v{version} (niche {niche_id})",
        intent=intent,
        effects=(PROMOTION_EFFECT,),
    )


def attest_promotion(
    *,
    specialist_id: str,
    niche_id: str,
    version: str,
    lineage: dict[str, Any],
    registry: Registry,
    ledger: Ledger,
    signing_key,
) -> PromotionAttestation:
    """Verify the promotion Unit through AXIOM and append the lineage event.

    Raises ValueError if AXIOM rejects the unit — the adapter cannot weaken
    the verifier, so a rejection is a hard stop (§91).
    """
    verifier = Verifier(registry, ledger)
    unit = build_promotion_unit(specialist_id, niche_id, version)
    result = verifier.verify(unit)
    if not isinstance(result, Attestation):
        raise ValueError(f"AXIOM rejected promotion unit: {result.errors}")

    lineage_payload = {
        "specialist_id": specialist_id,
        "niche_id": niche_id,
        "version": version,
        "unit_hash": result.unit_hash,
        "attestation_event": result.event_hash,
        "lineage": lineage,
    }
    lineage_event = ledger.append("foundry.model.promotion", lineage_payload)
    return PromotionAttestation(
        specialist_id=specialist_id,
        unit_hash=result.unit_hash,
        attestation_event_hash=result.event_hash,
        lineage_event_hash=lineage_event,
        checks=result.checks,
        warnings=result.warnings,
        lineage=lineage,
    )
