"""Cockpit handlers for the SYNAPSE game substrate — the ``/v1/game/*`` and
``/v1/foundry/*`` additive route families (master plan
``docs/plans/2026-06-10-project-synapse-master-plan.md`` §4 + §4.7, coupling
rule §1: gateway-side, additive, regenerated into the frozen contract).

All routes are bearer-authed (the standard CRUD default; none are
owner-phrase gated — saves and Foundry records are local game state, not
real-MUSE capability changes, which stay behind the existing approvals
queue per design doc 07 §9, the real-MUSE bridge).

Game saves (``gateway.cockpit.game_store``):

* ``GET    /v1/game/saves`` — slot summaries (never full documents).
* ``GET    /v1/game/saves/{slot}`` — full save; 404 for an empty slot.
* ``POST   /v1/game/saves/{slot}`` — validated **section-level merge**: the
  body carries any subset of muse/network/roster/den/progress/settings;
  each provided section replaces that section wholesale, omitted sections
  are untouched. 400 with a specific message on any constraint violation.
* ``DELETE /v1/game/saves/{slot}``
* ``GET    /v1/game/design`` — the static design constants the client
  needs (lattice geometry, thread costs, domains, gauntlet names), served
  verbatim from :data:`gateway.cockpit.game_store.DESIGN` which cites the
  design-doc paths it was sourced from.

Foundry (``gateway.cockpit.foundry_store`` — the honest loop spine):

* ``POST /v1/foundry/observe`` — append a struggle-pattern report.
* ``GET  /v1/foundry/candidates`` (``?status=``) / ``POST`` to create.
* ``POST /v1/foundry/candidates/{id}/validation`` — record an externally
  measured result. The gateway never simulates and never invents numbers.
* ``POST /v1/foundry/candidates/{id}/ship`` — enforce the
  validated-and-improving rule; 409 otherwise.

Like ``handlers_observatory_recs``, ``Request``/``JsonResponse`` are bound
from the sibling ``handlers`` module at the *bottom* so the two-way import
resolves under any import order; stores are imported lazily per handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — runtime binding happens at module bottom
    from .handlers import JsonResponse, Request

GAME_VERSION = 1


def _bad_request(detail: str) -> "JsonResponse":
    return JsonResponse(400, {"error": "bad_request", "detail": detail})


# ---------------------------------------------------------------------------
# /v1/game/*
# ---------------------------------------------------------------------------


def game_design(_req: Request) -> JsonResponse:
    """Static, source-cited design constants (lattice, costs, domains,
    gauntlets) — one read-only dict, no computation, no state."""
    from gateway.cockpit import game_store as gs

    return JsonResponse(200, gs.DESIGN)


def game_saves_list(_req: Request) -> JsonResponse:
    """Slot summaries for the save-select screen."""
    from gateway.cockpit import game_store as gs

    return JsonResponse(
        200, {"v": GAME_VERSION, "max_slots": gs.MAX_SLOTS, "slots": gs.list_slots()}
    )


def game_save_get(req: Request) -> JsonResponse:
    """Full save document. 400 for a bad slot number, 404 for an empty slot."""
    from gateway.cockpit import game_store as gs

    try:
        slot = gs.parse_slot(req.path_params.get("slot"))
    except gs.GameValidationError as exc:
        return _bad_request(str(exc))
    save = gs.load_slot(slot)
    if save is None:
        return JsonResponse(404, {"error": "empty_slot", "slot": slot})
    return JsonResponse(200, save)


def game_save_write(req: Request) -> JsonResponse:
    """Section-level merge write (semantics in the module docstring).

    201 when the write created the slot, 200 when it updated an existing
    save; 400 with the specific constraint message on any violation —
    rejected bodies write nothing.
    """
    from gateway.cockpit import game_store as gs

    try:
        slot = gs.parse_slot(req.path_params.get("slot"))
        save, created = gs.write_slot(slot, req.body)
    except gs.GameValidationError as exc:
        return _bad_request(str(exc))
    return JsonResponse(201 if created else 200, save)


def game_save_delete(req: Request) -> JsonResponse:
    from gateway.cockpit import game_store as gs

    try:
        slot = gs.parse_slot(req.path_params.get("slot"))
    except gs.GameValidationError as exc:
        return _bad_request(str(exc))
    deleted = gs.delete_slot(slot)
    return JsonResponse(200 if deleted else 404, {"deleted": deleted, "slot": slot})


# ---------------------------------------------------------------------------
# /v1/foundry/*
# ---------------------------------------------------------------------------


def foundry_observe(req: Request) -> JsonResponse:
    """Append one struggle-pattern observation (opt-in is the game client's
    gate, mirrored here as-stated; the store records, it never infers)."""
    from gateway.cockpit import foundry_store as fs

    try:
        record = fs.append_observation(
            req.body.get("save_slot"),
            req.body.get("pattern"),
            req.body.get("client"),
        )
    except fs.FoundryValidationError as exc:
        return _bad_request(str(exc))
    return JsonResponse(201, {"v": fs.FOUNDRY_VERSION, "observation": record})


def foundry_candidates_list(req: Request) -> JsonResponse:
    """List candidates, optionally filtered by ``?status=`` (pending /
    validated / rejected)."""
    from gateway.cockpit import foundry_store as fs

    try:
        candidates = fs.list_candidates(req.query.get("status"))
    except fs.FoundryValidationError as exc:
        return _bad_request(str(exc))
    return JsonResponse(200, {"v": fs.FOUNDRY_VERSION, "candidates": candidates})


def foundry_candidate_create(req: Request) -> JsonResponse:
    """Create a candidate from an allowlist-validated spec. Status starts
    ``pending`` with an empty receipt — no numbers until a real result."""
    from gateway.cockpit import foundry_store as fs

    try:
        candidate = fs.create_candidate(
            req.body.get("spec"), req.body.get("source_pattern_refs")
        )
    except fs.FoundryValidationError as exc:
        return _bad_request(str(exc))
    return JsonResponse(201, candidate)


def foundry_candidate_validation(req: Request) -> JsonResponse:
    """Record a validation result measured by the external battle-sim
    harness — the honest receipt. 404 unknown id, 400 malformed result."""
    from gateway.cockpit import foundry_store as fs

    candidate_id = req.path_params.get("id", "")
    try:
        candidate = fs.record_validation(candidate_id, req.body.get("result"))
    except fs.FoundryValidationError as exc:
        return _bad_request(str(exc))
    if candidate is None:
        return JsonResponse(404, {"error": "unknown_candidate", "id": candidate_id})
    return JsonResponse(200, candidate)


def foundry_candidate_ship(req: Request) -> JsonResponse:
    """Flip ``shipped=true``. 409 unless validation.status == 'validated'
    AND candidate_survival > baseline_survival (the measured-win rule)."""
    from gateway.cockpit import foundry_store as fs

    candidate_id = req.path_params.get("id", "")
    try:
        candidate = fs.ship_candidate(candidate_id)
    except fs.FoundryShipConflict as exc:
        return JsonResponse(409, {"error": "ship_refused", "detail": str(exc)})
    if candidate is None:
        return JsonResponse(404, {"error": "unknown_candidate", "id": candidate_id})
    return JsonResponse(200, candidate)


# ``Request`` / ``JsonResponse`` canonical definitions — bound at module
# bottom so the two-way import with ``handlers`` resolves under any import
# order (handlers_autonomy / handlers_observatory_recs pattern).
from .handlers import JsonResponse, Request  # noqa: E402,F401

__all__ = [
    "GAME_VERSION",
    "foundry_candidate_create",
    "foundry_candidate_ship",
    "foundry_candidate_validation",
    "foundry_candidates_list",
    "foundry_observe",
    "game_design",
    "game_save_delete",
    "game_save_get",
    "game_save_write",
    "game_saves_list",
]
