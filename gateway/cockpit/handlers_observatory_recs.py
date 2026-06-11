"""Cockpit Neural Observatory recommendation handlers — the
``/v1/observatory/recommendations*`` routes (SYNAPSE Phase 3, master plan
§3.4, ``docs/synapse/design/10-observatory-spec.md`` §6).

Two routes, both bearer-authed:

* ``GET /v1/observatory/recommendations`` — recomputes verdict cards from
  the :mod:`gateway.cockpit.observatory_recommend` engine over the passive
  collector. Read-only. When the collector is dormant (nothing has ever
  been recorded in this HERMES_HOME) the response is honestly
  ``{"cards": [], "status": "dormant"}`` — no fake cards.
* ``POST /v1/observatory/recommendations/{id}/stage`` — stages one card
  into the EXISTING owner-gated proposals queue. Bearer auth, NOT
  owner-phrase: staging only *feeds* the approval queue; the owner gate
  lives where it always has — ``POST /v1/cockpit/approvals/{id}`` (exact
  authorization phrase) for Apply, and the existing ledger rollback route
  for rollback. No new owner-gated surface.

Honesty rules (binding, spec §6 hard rule): cards carry a percentage/CI
only when both counterfactual arms reached the evidence threshold
(``observatory_recommend.MIN_EVIDENCE_N``); below it the card states
"insufficient evidence (n=X) — collecting" with zero projected numbers.

Like ``handlers_observatory``, this module is stdlib-only at import time;
the collector and engine are imported lazily inside each handler.
``Request`` / ``JsonResponse`` are imported from the sibling ``handlers``
module at the *bottom* (the ``handlers_autonomy`` pattern) so the two-way
re-export relationship resolves under any import order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — runtime binding happens at module bottom
    from .handlers import JsonResponse, Request

RECOMMENDATIONS_VERSION = 1

_DEFAULT_WINDOW = "24h"


def _bad_request(detail: str) -> "JsonResponse":
    return JsonResponse(400, {"error": "bad_request", "detail": detail})


def observatory_recommendations(req: Request) -> JsonResponse:
    """Recommendation verdict cards (spec §6) — bearer-authed, read-only.

    ``window`` ∈ 15m|1h|24h|7d (default 24h). Cards are recomputed from the
    collector on each call (the collector's rollup is already in-memory and
    bounded — cheap enough that no extra cache layer is warranted yet).
    """
    window = req.query.get("window", _DEFAULT_WINDOW)
    try:
        from gateway.cockpit import observatory_metrics as om
        from gateway.cockpit import observatory_recommend as rec
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})
    if window not in om.WINDOWS:
        return _bad_request(
            f"window: must be one of {', '.join(sorted(om.WINDOWS))} (got {window!r})"
        )
    from .handlers import _now_iso

    try:
        collector = om.get_collector()
        rollup = collector.rollup(window)
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})
    if rollup["collector"]["events_recorded"] == 0:
        # Collector disabled/dormant — nothing has ever been recorded here.
        return JsonResponse(
            200,
            {
                "v": RECOMMENDATIONS_VERSION,
                "generated_at": _now_iso(),
                "window": rollup["window"],
                "cards": [],
                "status": "dormant",
            },
        )
    cards = rec.build_cards(collector, window)
    rec.mark_staged(cards)
    return JsonResponse(
        200,
        {
            "v": RECOMMENDATIONS_VERSION,
            "generated_at": _now_iso(),
            "window": rollup["window"],
            "cards": cards,
            "status": "ok",
        },
    )


def observatory_recommendation_stage(req: Request) -> JsonResponse:
    """Stage one card into the existing owner-gated proposals queue.

    404 for an unknown card id; 409 when the card is already staged
    (idempotency guard — the queue never gets duplicates). On success the
    response carries the proposal id plus the existing approval route that
    owner-gated Apply rides.
    """
    rec_id = req.path_params.get("id", "")
    window = req.query.get("window", _DEFAULT_WINDOW)
    try:
        from gateway.cockpit import observatory_metrics as om
        from gateway.cockpit import observatory_recommend as rec
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})
    if window not in om.WINDOWS:
        return _bad_request(
            f"window: must be one of {', '.join(sorted(om.WINDOWS))} (got {window!r})"
        )
    try:
        collector = om.get_collector()
        cards = rec.build_cards(collector, window)
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})
    rec.mark_staged(cards)
    card = next((c for c in cards if c["id"] == rec_id), None)
    if card is None:
        return JsonResponse(404, {"error": "unknown_recommendation", "id": rec_id})
    if card["state"] == "staged":
        return JsonResponse(
            409,
            {
                "error": "already_staged",
                "id": rec_id,
                "proposal_id": card.get("proposal_id"),
            },
        )
    proposal_id, created = rec.stage_recommendation(card)
    if not created:  # pragma: no cover - race between mark_staged and stage
        return JsonResponse(
            409,
            {"error": "already_staged", "id": rec_id, "proposal_id": proposal_id},
        )
    return JsonResponse(
        201,
        {
            "v": RECOMMENDATIONS_VERSION,
            "id": rec_id,
            "state": "staged",
            "proposal_id": proposal_id,
            "approval_ref": f"/v1/cockpit/approvals/{proposal_id}",
        },
    )


# ``Request`` / ``JsonResponse`` canonical definitions — bound at module
# bottom so the two-way import with ``handlers`` resolves under any import
# order (handlers_autonomy / handlers_observatory pattern).
from .handlers import JsonResponse, Request  # noqa: E402,F401

__all__ = [
    "RECOMMENDATIONS_VERSION",
    "observatory_recommendation_stage",
    "observatory_recommendations",
]
