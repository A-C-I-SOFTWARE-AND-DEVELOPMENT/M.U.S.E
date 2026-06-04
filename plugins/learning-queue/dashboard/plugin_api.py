"""Learning-Queue dashboard plugin — backend API routes.

Mounted at ``/api/plugins/learning-queue/`` by the dashboard plugin system.

This layer is intentionally thin: every handler wraps
``hermes_cli.jarvis_prime.learning_dataset.DatasetStore`` using the same code
paths the ``jarvis_prime learning`` CLI and the cockpit
(``gateway/cockpit/handlers.py``) use, so the web, CLI, cockpit, and Android
surfaces cannot drift. In particular the **owner-approval gate is preserved**:
approving a candidate requires the exact authorization phrase
(``owner_auth.AUTHORIZATION_PHRASE``), exactly like the cockpit's
``learning_decide`` and the CLI ``learning approve``.

Security note: plugin HTTP routes already sit behind the dashboard's
session-token auth middleware (see ``plugins/kanban/dashboard/plugin_api.py``),
so these endpoints are owner-only on loopback. The phrase gate is an
additional, explicit confirmation for the irreversible "promote to training
data" action — never a bypass.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter()


def _store():
    """Load the profile-aware learning dataset store."""
    from hermes_cli.jarvis_prime.learning_dataset import DatasetStore

    return DatasetStore.load()


def _status_enum(value: Optional[str]):
    """Map a status query string to CandidateStatus, or None when absent/blank."""
    if not value:
        return None
    from hermes_cli.jarvis_prime.learning_dataset import CandidateStatus

    try:
        return CandidateStatus(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"unknown status: {value!r}")


# ---------------------------------------------------------------------------
# GET /queue  — provenance-first candidate cards
# ---------------------------------------------------------------------------

@router.get("/queue")
def get_queue(status: Optional[str] = None, trace_type: Optional[str] = None):
    """List learning candidates as audit cards (provenance + quality gates).

    Honest empty list when the store is missing — never fabricated.
    """
    try:
        store = _store()
        st = _status_enum(status)
        cards = []
        for cand in store.entries(status=st):
            if trace_type and cand.trace_type.value != trace_type:
                continue
            cards.append(cand.audit_card())
        return {"learning": cards, "count": len(cards)}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("learning queue load failed: %s", exc)
        return {"learning": [], "count": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# GET /candidate/{id}  — full candidate
# ---------------------------------------------------------------------------

@router.get("/candidate/{candidate_id}")
def get_candidate(candidate_id: str):
    store = _store()
    cand = store.get(candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail=f"unknown candidate: {candidate_id}")
    return {"candidate": cand.to_dict()}


# ---------------------------------------------------------------------------
# POST /candidate/{id}/decide  — approve (owner-gated) / reject
# ---------------------------------------------------------------------------

class DecideBody(BaseModel):
    decision: str  # "approve" | "reject"
    authorization: Optional[str] = None  # required for approve
    note: Optional[str] = None


@router.post("/candidate/{candidate_id}/decide")
def decide_candidate(candidate_id: str, payload: DecideBody):
    decision = (payload.decision or "").lower().strip()
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if decision == "approve":
        phrase = (payload.authorization or "").strip()
        if phrase != AUTHORIZATION_PHRASE:
            # Owner-gate contract: exact phrase required. Never bypass.
            raise HTTPException(
                status_code=403,
                detail=f"owner authorization required — reply exactly: {AUTHORIZATION_PHRASE!r}",
            )

    store = _store()
    if store.get(candidate_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown candidate: {candidate_id}")
    note = payload.note or f"{decision} via dashboard"
    if decision == "approve":
        store.approve(candidate_id, note=note)
    else:
        store.reject(candidate_id, note=note)
    return {"id": candidate_id, "status": decision}


# ---------------------------------------------------------------------------
# GET /stats  — header counts
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats():
    from hermes_cli.jarvis_prime.learning_dataset import CandidateStatus

    store = _store()
    entries = store.entries()
    by_status: dict[str, int] = {}
    by_trace: dict[str, int] = {}
    for c in entries:
        by_status[c.status.value] = by_status.get(c.status.value, 0) + 1
        by_trace[c.trace_type.value] = by_trace.get(c.trace_type.value, 0) + 1
    approved = store.entries(status=CandidateStatus.APPROVED)
    exportable = [c for c in approved if c.is_negative or c.quality.passed(c.trace_type)]
    return {
        "total": len(entries),
        "by_status": by_status,
        "by_trace_type": by_trace,
        "exportable": len(exportable),
    }


# ---------------------------------------------------------------------------
# POST /export  — write approved candidates to a local file
# ---------------------------------------------------------------------------

class ExportBody(BaseModel):
    format: str = "jsonl"  # jsonl | preference | eval | skill | parquet
    out: str


@router.post("/export")
def export(payload: ExportBody):
    fmt = (payload.format or "jsonl").lower().strip()
    out = payload.out
    if not out:
        raise HTTPException(status_code=400, detail="out path is required")
    store = _store()
    try:
        if fmt == "jsonl":
            n = store.export_jsonl(out)
        elif fmt == "preference":
            n = store.export_preference_pairs(out)
        elif fmt == "eval":
            n = store.export_eval_cases(out)
        elif fmt == "skill":
            n = store.export_skill_candidates(out)
        elif fmt == "parquet":
            from hermes_cli.jarvis_prime.learning_analytics import export_parquet

            n = export_parquet(store, out)
        else:
            raise HTTPException(status_code=400, detail=f"unknown format: {fmt}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"export failed: {exc}")
    return {"exported": n, "format": fmt, "out": out}
