"""The Foundry loop spine — ``/v1/foundry/*`` persistence.

Implements the gateway-side state for the master plan §4.7 loop (observe
struggle patterns → hypothesize candidate → build from a vetted component
library → validate via simulated battles → ship as a discoverable rare with
a validation receipt), per ``docs/synapse/design/09-foundry-spec.md``.

Honesty rules (binding, spec §1 law 1 + §5):

* The gateway **stores** validation results; it never simulates. The actual
  battle-sim harness runs in UE on the owner machine (or a future server
  harness) and reports results via :func:`record_validation`. **No fake
  simulation numbers are ever generated server-side** — until a result is
  recorded, ``validation.status`` stays ``"pending"`` and ``receipt_text``
  is empty.
* A candidate may only flip ``shipped=true`` when
  ``validation.status == "validated"`` **and**
  ``candidate_survival > baseline_survival`` (a measured improvement) —
  :func:`ship_candidate` enforces this; the handler maps refusal to 409.
* Specs are **allowlist-validated** against the vetted component library
  embedded below (spec §4: closed archetype/ability/part libraries — the
  bounded-generation law). Unknown ids are rejected, never stored.

Storage: ``${HERMES_HOME}/jarvis_prime/foundry/`` — ``observations.jsonl``
(append-only struggle-pattern reports; the store records what it is told,
no inference here) and ``candidates.json`` (atomic tmp + ``os.replace``).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from gateway.cockpit.game_store import DOMAIN_RING, MAX_SLOTS

FOUNDRY_VERSION = 1


class FoundryValidationError(ValueError):
    """A request violated a Foundry constraint (-> HTTP 400)."""


class FoundryShipConflict(Exception):
    """Ship refused: the validated+improvement rule failed (-> HTTP 409)."""


# ---------------------------------------------------------------------------
# Vetted component library (closed; additions require a design-doc rev —
# 09-foundry-spec.md §4.2 archetypes, §4.4 abilities, §4.5 part bank)
# ---------------------------------------------------------------------------

OBSERVATION_KINDS: frozenset[str] = frozenset(
    {"gauntlet_deaths", "failed_parley", "economy_stall", "custom"}
)
CLIENTS: frozenset[str] = frozenset({"ue", "web"})

#: The 12 helper archetypes (spec §4.2 — closed library).
ARCHETYPES: tuple[str, ...] = (
    "INTERDICTOR",
    "BULWARK",
    "TRIAGE",
    "OVERCLOCKER",
    "DIPLOMAT",
    "LURE",
    "PROSPECTOR",
    "WEAVER",
    "MARKSMAN",
    "SABOTEUR",
    "BEACON",
    "WARDEN",
)

#: Vetted GAS ability ids (spec §4.4: drawn ONLY from the vetted component
#: library; T2 tiers exist for level-banded kits). No live-authored effects.
VETTED_ABILITIES: frozenset[str] = frozenset(
    {
        "GA_Interrupt_T1", "GA_Interrupt_T2",
        "GA_DamageShield_T1", "GA_DamageShield_T2",
        "GA_Taunt_T1", "GA_Taunt_T2",
        "GA_Cleanse_T1", "GA_Cleanse_T2",
        "GA_HealOverTime_T1", "GA_HealOverTime_T2",
        "GA_Haste_T1", "GA_Haste_T2",
        "GA_CooldownRefund_T1", "GA_CooldownRefund_T2",
        "GA_DispositionAura_T1", "GA_RerollToken_T1",
        "GA_ParleyOpener_T1", "GA_ParleyOpener_T2",
        "GA_CyclesFind_T1", "GA_CyclesFind_T2",
        "GA_ShardSense_T1",
        "GA_ThreadGen_T1", "GA_ThreadGen_T2",
        "GA_WiringDiscount_T1",
        "GA_FocusFire_T1", "GA_FocusFire_T2",
        "GA_ArmorShred_T1", "GA_ArmorShred_T2",
        "GA_Mark_T1", "GA_Mark_T2",
        "GA_TelegraphSlow_T1", "GA_TelegraphSlow_T2",
    }
)

#: Allowlisted modular part-bank ids (spec §4.5: skeleton + parts + palette
#: + FX accent, all pre-authored pak assets — NO live-generated art, ever).
VETTED_ART_PARTS: frozenset[str] = frozenset(
    {
        # skeletons
        "SK_Biped_S", "SK_Biped_M", "SK_Biped_L",
        "SK_Quadruped_S", "SK_Quadruped_M", "SK_Wisp",
        # parts
        "P_Carapace_01", "P_Carapace_02", "P_Carapace_03",
        "P_Visor_01", "P_Visor_02",
        "P_Tail_Cable_01", "P_Tail_Cable_02",
        "P_Pauldron_01", "P_Pauldron_02",
        "P_Halo_01", "P_Drape_01",
        # palettes (one per domain, 04-roster-24-agents.md §2 palette keys)
        "PAL_Architecture_Cobalt", "PAL_QA_Signal", "PAL_BuildOps_Forge",
        "PAL_Compliance_Hazard", "PAL_Behavior_Rose", "PAL_Research_Violet",
        "PAL_Security_Cool", "PAL_Release_Emerald",
        # FX accents
        "FX_Shield_Hex", "FX_Spark_Trail", "FX_Glyph_Orbit", "FX_Thread_Weave",
    }
)

#: The five attribute keys a CandidateSpec may budget (spec §4.1).
STAT_KEYS: frozenset[str] = frozenset(
    {"vitality", "resilience", "throughput", "latency", "bandwidth"}
)

#: The five bounded personality axes (spec §4.5), each in [0, 1].
PERSONALITY_AXES: frozenset[str] = frozenset(
    {"warmth", "candor", "patience", "pride", "curiosity"}
)

VALIDATION_STATUSES: tuple[str, ...] = ("pending", "validated", "rejected")

_PENDING_VALIDATION: dict[str, Any] = {
    "status": "pending",
    "method": None,
    "n_simulations": 0,
    "baseline_survival": None,
    "candidate_survival": None,
    "receipt_text": "",
}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def foundry_dir() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    d = Path(base) / "jarvis_prime" / "foundry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _observations_path() -> Path:
    return foundry_dir() / "observations.jsonl"


def _candidates_path() -> Path:
    return foundry_dir() / "candidates.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_candidates() -> list[dict]:
    try:
        return json.loads(_candidates_path().read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_candidates(candidates: list[dict]) -> None:
    path = _candidates_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Observations (append-only; opt-in flag mirrored from the game client —
# the store records what it's told, no inference here)
# ---------------------------------------------------------------------------


def append_observation(save_slot: Any, pattern: Any, client: Any) -> dict:
    """Append one struggle-pattern report. Validates shape, infers nothing."""
    try:
        slot = int(str(save_slot))
    except (TypeError, ValueError):
        raise FoundryValidationError(
            f"save_slot: must be an integer 1..{MAX_SLOTS} (got {save_slot!r})"
        ) from None
    if not 1 <= slot <= MAX_SLOTS:
        raise FoundryValidationError(f"save_slot: must be 1..{MAX_SLOTS} (got {slot})")
    if not isinstance(pattern, dict):
        raise FoundryValidationError("pattern: must be an object with a kind")
    kind = pattern.get("kind")
    if kind not in OBSERVATION_KINDS:
        raise FoundryValidationError(
            f"pattern.kind: {kind!r} is not one of "
            f"{', '.join(sorted(OBSERVATION_KINDS))}"
        )
    context = pattern.get("context", {})
    if not isinstance(context, dict):
        raise FoundryValidationError("pattern.context: must be an object")
    if client not in CLIENTS:
        raise FoundryValidationError(
            f"client: {client!r} is not one of {', '.join(sorted(CLIENTS))}"
        )
    record = {
        "id": "obs-" + uuid.uuid4().hex[:8],
        "ts": _now_iso(),
        "save_slot": slot,
        "pattern": {"kind": kind, "context": context},
        "client": client,
    }
    with _observations_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def list_observations() -> list[dict]:
    try:
        lines = _observations_path().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def _validate_spec(spec: Any) -> dict:
    if not isinstance(spec, dict):
        raise FoundryValidationError("spec: must be an object")
    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        raise FoundryValidationError("spec.name: must be a non-empty string")
    domain = spec.get("domain")
    if domain not in DOMAIN_RING:
        raise FoundryValidationError(
            f"spec.domain: {domain!r} is not one of {', '.join(DOMAIN_RING)}"
        )
    archetype = spec.get("archetype")
    if archetype is not None and archetype not in ARCHETYPES:
        raise FoundryValidationError(
            f"spec.archetype: {archetype!r} is not in the closed library of 12 "
            "(09-foundry-spec.md §4.2)"
        )
    stats = spec.get("stats", {})
    if not isinstance(stats, dict):
        raise FoundryValidationError("spec.stats: must be an object")
    for key, value in stats.items():
        if key not in STAT_KEYS:
            raise FoundryValidationError(
                f"spec.stats: unknown stat {key!r} — valid stats are "
                f"{', '.join(sorted(STAT_KEYS))} (spec §4.1)"
            )
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise FoundryValidationError(f"spec.stats.{key}: must be a number")
    abilities = spec.get("ability_ids")
    if not isinstance(abilities, list) or not 1 <= len(abilities) <= 4:
        raise FoundryValidationError(
            "spec.ability_ids: must be a list of 1-4 vetted ability ids (spec §4.4)"
        )
    for ability in abilities:
        if ability not in VETTED_ABILITIES:
            raise FoundryValidationError(
                f"spec.ability_ids: {ability!r} is not in the vetted GAS component "
                "library (09-foundry-spec.md §4.4) — no live-authored abilities"
            )
    if len(set(abilities)) != len(abilities):
        raise FoundryValidationError("spec.ability_ids: duplicate ability id")
    personality = spec.get("personality_card", {})
    if not isinstance(personality, dict):
        raise FoundryValidationError("spec.personality_card: must be an object")
    for axis, value in personality.items():
        if axis not in PERSONALITY_AXES:
            raise FoundryValidationError(
                f"spec.personality_card: unknown axis {axis!r} — the five bounded "
                f"axes are {', '.join(sorted(PERSONALITY_AXES))} (spec §4.5)"
            )
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            raise FoundryValidationError(
                f"spec.personality_card.{axis}: must be a number in [0, 1]"
            )
    art_parts = spec.get("art_parts", [])
    if not isinstance(art_parts, list):
        raise FoundryValidationError("spec.art_parts: must be a list of part-bank ids")
    for part in art_parts:
        if part not in VETTED_ART_PARTS:
            raise FoundryValidationError(
                f"spec.art_parts: {part!r} is not in the allowlisted modular "
                "part bank (09-foundry-spec.md §4.5) — no live-generated art"
            )
    return spec


def create_candidate(spec: Any, source_pattern_refs: Any = None) -> dict:
    """Register a forged-agent candidate. Status starts ``pending`` with an
    empty receipt — the gateway never invents validation numbers."""
    spec = _validate_spec(spec)
    refs = source_pattern_refs or []
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        raise FoundryValidationError(
            "source_pattern_refs: must be a list of observation ids"
        )
    candidate = {
        "id": "fc-" + uuid.uuid4().hex[:8],
        "created_at": _now_iso(),
        "source_pattern_refs": refs,
        "spec": spec,
        "validation": dict(_PENDING_VALIDATION),
        "shipped": False,
    }
    candidates = _load_candidates()
    candidates.append(candidate)
    _save_candidates(candidates)
    return candidate


def list_candidates(status: Optional[str] = None) -> list[dict]:
    candidates = _load_candidates()
    if status is None:
        return candidates
    if status not in VALIDATION_STATUSES:
        raise FoundryValidationError(
            f"status: {status!r} is not one of {', '.join(VALIDATION_STATUSES)}"
        )
    return [c for c in candidates if c["validation"]["status"] == status]


def get_candidate(candidate_id: str) -> Optional[dict]:
    for candidate in _load_candidates():
        if candidate.get("id") == candidate_id:
            return candidate
    return None


def record_validation(candidate_id: str, result: Any) -> Optional[dict]:
    """Store an externally-measured validation result (the honest receipt).

    The battle sim runs in UE on the owner machine (or a future server
    harness); this only records what it reports. Returns the updated
    candidate, or None for an unknown id. Raises
    :class:`FoundryValidationError` on a malformed result.
    """
    if not isinstance(result, dict):
        raise FoundryValidationError("result: must be an object")
    status = result.get("status")
    if status not in ("validated", "rejected"):
        raise FoundryValidationError(
            f"result.status: must be 'validated' or 'rejected' (got {status!r}) — "
            "'pending' is the absence of a result, never a recorded one"
        )
    method = result.get("method")
    if not isinstance(method, str) or not method.strip():
        raise FoundryValidationError(
            "result.method: must name the harness that produced the numbers"
        )
    n = result.get("n_simulations")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise FoundryValidationError(
            f"result.n_simulations: must be a positive integer (got {n!r})"
        )
    for key in ("baseline_survival", "candidate_survival"):
        value = result.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            raise FoundryValidationError(
                f"result.{key}: must be a number in [0, 1] (got {value!r})"
            )
    receipt = result.get("receipt_text", "")
    if not isinstance(receipt, str):
        raise FoundryValidationError("result.receipt_text: must be a string")

    candidates = _load_candidates()
    for candidate in candidates:
        if candidate.get("id") == candidate_id:
            candidate["validation"] = {
                "status": status,
                "method": method,
                "n_simulations": n,
                "baseline_survival": float(result["baseline_survival"]),
                "candidate_survival": float(result["candidate_survival"]),
                "receipt_text": receipt,
                "recorded_at": _now_iso(),
            }
            _save_candidates(candidates)
            return candidate
    return None


def ship_candidate(candidate_id: str) -> Optional[dict]:
    """Flip ``shipped=true`` — only for a validated, measurably-improving
    candidate. Returns the candidate, None for an unknown id, and raises
    :class:`FoundryShipConflict` when the rule fails (-> HTTP 409)."""
    candidates = _load_candidates()
    for candidate in candidates:
        if candidate.get("id") != candidate_id:
            continue
        validation = candidate["validation"]
        if validation["status"] != "validated":
            raise FoundryShipConflict(
                f"candidate {candidate_id} has validation status "
                f"{validation['status']!r} — only 'validated' candidates ship "
                "(09-foundry-spec.md §5.2: a candidate that didn't validate "
                "does not ship)"
            )
        if not validation["candidate_survival"] > validation["baseline_survival"]:
            raise FoundryShipConflict(
                f"candidate {candidate_id} shows no measured improvement "
                f"(baseline {validation['baseline_survival']}, candidate "
                f"{validation['candidate_survival']}) — promote only on a "
                "measured win (09-foundry-spec.md §5.2)"
            )
        if not candidate["shipped"]:
            candidate["shipped"] = True
            candidate["shipped_at"] = _now_iso()
            _save_candidates(candidates)
        return candidate
    return None


__all__ = [
    "ARCHETYPES",
    "CLIENTS",
    "FOUNDRY_VERSION",
    "FoundryShipConflict",
    "FoundryValidationError",
    "OBSERVATION_KINDS",
    "PERSONALITY_AXES",
    "STAT_KEYS",
    "VALIDATION_STATUSES",
    "VETTED_ABILITIES",
    "VETTED_ART_PARTS",
    "append_observation",
    "create_candidate",
    "foundry_dir",
    "get_candidate",
    "list_candidates",
    "list_observations",
    "record_validation",
    "ship_candidate",
]
