"""Cockpit autonomy handlers — Owner High-Autonomy Coding mode.

Extracted verbatim from :mod:`gateway.cockpit.handlers` (the cockpit import
hub) as a cohesive, self-contained group: the FU-12 owner-gate cluster.
Behaviour is unchanged — this is a physical relocation plus a re-export from
``handlers`` so every existing reference (e.g. ``server.py``'s route table
calling ``h.autonomy_set``) keeps resolving exactly as before.

Like ``handlers``, this module is stdlib-only at import time; the policy
engine (``hermes_cli.approval_policy``) and the response ``contract`` are
imported lazily inside each handler so it loads under Termux / slim installs.

``Request`` / ``JsonResponse`` are imported from the sibling ``handlers``
module (their canonical definition site) rather than re-declared, so the
request/response model stays single-sourced and no duplicate types appear.
That import lives at the *bottom* of this module so the two-way relationship
with ``handlers`` (which re-exports the handlers below) resolves under any
import order: with ``from __future__ import annotations`` the signatures are
lazy strings, so the handlers can be *defined* before ``Request`` /
``JsonResponse`` are bound — they are only needed at call time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — runtime binding happens at module bottom
    from .handlers import JsonResponse, Request


# ---------------------------------------------------------------------------
# Autonomy (Owner High-Autonomy Coding mode)
# ---------------------------------------------------------------------------


def autonomy_get(_req: Request) -> JsonResponse:
    """Current autonomy level, workspace scope, and capability list.

    The capability list is derived from ``hermes_cli.approval_policy`` so the
    cockpit never hard-codes a list that could drift from the policy engine.
    """
    try:
        from hermes_cli import approval_policy as ap

        from . import contract

        record = ap.load_record()
        return JsonResponse(200, contract.autonomy_status(record, ap.capabilities(record.level)))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})


# Autonomy levels that grant more than the safe ASSISTED floor. Raising *to*
# any of these auto-approves real actions, so escalation is an owner-gated
# action (exact phrase required) — a bearer token alone must never escalate.
# Lowering to READ_ONLY / ASSISTED and ``revoke`` stay ungated (de-escalation
# is always safe).
_PRIVILEGED_AUTONOMY_LEVELS: frozenset[str] = frozenset(
    {"autonomous", "yolo", "owner_high_autonomy_coding"}
)


def _autonomy_raises_locked() -> bool:
    """True iff cockpit autonomy *raises* are hard-disabled via env.

    ``HERMES_COCKPIT_AUTONOMY_LOCKED`` is a deployment kill-switch / rollback:
    when set, no autonomy raise is accepted from the cockpit even with the owner
    phrase (lowering and ``revoke`` still work). It lets an operator lock down a
    shared or remotely-reachable cockpit without a code change.
    """
    import os

    return os.environ.get("HERMES_COCKPIT_AUTONOMY_LOCKED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def autonomy_set(req: Request) -> JsonResponse:
    """Set the autonomy level (owner action) or revoke back to ASSISTED.

    Body: ``{"level": "owner_high_autonomy_coding", "workspace_path": "...",
    "authorization": "<owner authorization>"}`` or ``{"revoke": true}``.

    **Owner gate:** raising autonomy to a privileged level (AUTONOMOUS / YOLO /
    OWNER_HIGH_AUTONOMY_CODING) requires the exact owner authorization phrase —
    the same gate that protects approvals, publish, and the paid-model flip. A
    bearer token alone may read autonomy and *lower* it, but cannot escalate it;
    de-escalation (READ_ONLY / ASSISTED) and ``revoke`` are never gated. The
    change is recorded in the approval audit log either way.
    """
    body = req.body or {}
    try:
        from hermes_cli import approval_policy as ap
        from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

        from . import contract

        if body.get("revoke"):
            record = ap.revoke(set_by="cockpit")
        else:
            raw_level = str(body.get("level", "")).strip().lower()
            try:
                level = ap.AutonomyLevel(raw_level)
            except ValueError:
                return JsonResponse(
                    400,
                    {"error": f"unknown autonomy level: {raw_level!r}"},
                )
            # Owner gate on escalation only (lowering / revoke stay open).
            if level.value in _PRIVILEGED_AUTONOMY_LEVELS:
                if _autonomy_raises_locked():
                    return JsonResponse(
                        403,
                        {
                            "error": "autonomy raises are disabled",
                            "hint": "HERMES_COCKPIT_AUTONOMY_LOCKED is set; this "
                            "cockpit may only lower or revoke autonomy",
                        },
                    )
                authorization = str(body.get("authorization", "")).strip()
                if authorization != AUTHORIZATION_PHRASE:
                    # Owner-gate contract: exact phrase required. Never bypass.
                    return JsonResponse(
                        403,
                        {
                            "error": "owner authorization required",
                            "authorization_required": True,
                        },
                    )
            workspace = str(body.get("workspace_path") or "")
            if level is ap.AutonomyLevel.OWNER_HIGH_AUTONOMY_CODING and not workspace:
                return JsonResponse(
                    400,
                    {"error": "owner_high_autonomy_coding requires a workspace_path scope"},
                )
            record = ap.save_level(level, workspace_root=workspace, set_by="cockpit")
        # Audit the mode change itself.
        try:
            audit_req = ap.ApprovalRequest(
                action=ap.Action.SAFE_READ,
                summary=f"autonomy set to {record.level.value}",
                target=record.workspace_root,
                details={"event": "autonomy_change", "set_by": record.set_by},
            )
            ap.record_decision(
                audit_req,
                ap.ApprovalResult(ap.Decision.ALLOW, "owner set autonomy", False),
                actor="cockpit",
            )
        except Exception:  # pragma: no cover - auditing is best-effort
            pass
        return JsonResponse(200, contract.autonomy_status(record, ap.capabilities(record.level)))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})


def autonomy_decisions(req: Request) -> JsonResponse:
    """Recent (already-redacted) policy decisions for the audit trail."""
    try:
        from hermes_cli import approval_policy as ap

        limit_raw = req.query.get("limit", "50")
        try:
            limit = max(1, min(500, int(limit_raw)))
        except (TypeError, ValueError):
            limit = 50
        return JsonResponse(200, {"decisions": ap.read_decisions(limit=limit)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})


__all__ = [
    "autonomy_decisions",
    "autonomy_get",
    "autonomy_set",
]


# Runtime binding of the request/response model, single-sourced from
# ``handlers``. Placed at the bottom so that whichever of ``handlers`` /
# ``handlers_autonomy`` is imported first, the other is already far enough
# along to satisfy the import: ``Request`` / ``JsonResponse`` are defined at
# the *top* of ``handlers``, and the handlers above are defined before this
# line — so neither side ever observes a missing name.
from .handlers import JsonResponse, Request  # noqa: E402,F401  (bottom-of-module to break the cycle)
