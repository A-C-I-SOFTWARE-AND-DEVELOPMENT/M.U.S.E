"""Canonical cockpit API schemas + adapters — the server is the source of truth.

The Android cockpit UI data models are the product specification. The
schemas described here mirror those models field-for-field so the cockpit
API emits **real** data with **no fabricated fields**.

Where a JARVIS-Prime subsystem stores a narrower shape than the UI needs,
an *adapter* in this module projects the subsystem record into the
canonical schema, deriving fields honestly and leaving genuinely-absent
values null (never invented). When a UI field is a real product need with
no source signal, it is persisted at the source (see
``MemoryRecord.category``) rather than guessed; when there is genuinely no
value, the canonical vocabulary carries an explicit "unknown" member
(e.g. memory category ``UNCATEGORIZED``) so the app renders an honest
absent state.

Wire conventions (contract §1): JSON object keys are ``snake_case``; enum
*values* are the Android enum **constant names** (e.g. ``OWNER_PREFERENCE``)
so the Kotlin `@Serializable` enums deserialize them directly.

Stdlib-only; no imports from the heavy runtime at module load.
"""

from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------------------
# Memory — mirrors com.aci.hermes.data.memory.MemoryItem
# ---------------------------------------------------------------------------

# Android `MemoryCategory` constants, plus an explicit UNCATEGORIZED member
# for records with no real classification signal (added to the canonical
# vocabulary so the server never has to invent one).
MEMORY_CATEGORIES: tuple[str, ...] = (
    "OWNER_PREFERENCE",
    "PROJECT_MEMORY",
    "WORKFLOW_LESSON",
    "TASK_CONTEXT",
    "DECISION_RECORD",
    "SOCIAL_SPEECH_PATTERN",
    "SESSION_MEMORY",
    "UNCATEGORIZED",
)

# Android `MemoryDurability` constants.
MEMORY_DURABILITIES: tuple[str, ...] = (
    "EPHEMERAL",
    "SESSION",
    "SHORT_TERM",
    "LONG_TERM",
    "PERMANENT",
)

# Android `MemoryConfidence` constants.
MEMORY_CONFIDENCES: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CONFIRMED")

# JARVIS memory store durability ("working"|"session"|"durable") → UI enum.
_DURABILITY_FROM_STORE: dict[str, str] = {
    "working": "EPHEMERAL",
    "session": "SESSION",
    "durable": "PERMANENT",
}

# UI durability (or a legacy store value) → store durability. Accepts both
# the canonical UI names and the raw store values so the create endpoint
# tolerates either without losing information.
_DURABILITY_TO_STORE: dict[str, str] = {
    "EPHEMERAL": "working",
    "WORKING": "working",
    "SESSION": "session",
    "SHORT_TERM": "session",
    "LONG_TERM": "durable",
    "PERMANENT": "durable",
    "DURABLE": "durable",
}

_CONFIDENCE_TO_FLOAT: dict[str, float] = {
    "LOW": 0.3,
    "MEDIUM": 0.6,
    "HIGH": 0.85,
    "CONFIRMED": 1.0,
}


def confidence_to_enum(value: float) -> str:
    """Map a stored confidence float to the UI's 4-level enum."""
    if value >= 0.999:
        return "CONFIRMED"
    if value >= 0.75:
        return "HIGH"
    if value >= 0.5:
        return "MEDIUM"
    return "LOW"


def confidence_to_float(raw: Any) -> float:
    """Map a UI confidence (enum name or number) back to a store float."""
    if isinstance(raw, bool):  # guard: bool is an int subclass
        return 1.0
    if isinstance(raw, (int, float)):
        return float(raw)
    return _CONFIDENCE_TO_FLOAT.get(str(raw).strip().upper(), 1.0)


def normalize_category(raw: Any) -> str:
    """Coerce an incoming category to a canonical member; unknown → UNCATEGORIZED."""
    if not raw:
        return "UNCATEGORIZED"
    up = str(raw).strip().upper().replace(" ", "_")
    return up if up in MEMORY_CATEGORIES else "UNCATEGORIZED"


def durability_from_store(store_value: Any) -> str:
    return _DURABILITY_FROM_STORE.get(str(store_value), "SESSION")


def durability_to_store(ui_value: Any) -> str:
    """Map a UI durability (or raw store value) to a store durability."""
    if not ui_value:
        return "session"
    return _DURABILITY_TO_STORE.get(str(ui_value).strip().upper(), "session")


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    iso = getattr(value, "isoformat", None)
    return iso() if callable(iso) else str(value)


def memory_item(record: Any) -> dict[str, Any]:
    """Project a ``jarvis_prime.memory.MemoryRecord`` into the canonical
    cockpit ``MemoryItem`` (Android product spec).

    Honest derivation only:
    - ``id``/``title`` are the store key (its stable identity + label);
      ``content`` is the value. Keeping ``id == key`` means DELETE-by-id
      keeps addressing the real record.
    - ``category`` is the persisted classification, or ``UNCATEGORIZED``.
    - timestamps come straight from the record; ``updated_at`` mirrors
      ``created_at`` until the store tracks edits (not invented as "now").
    - ``redacted`` is False: the store *rejects* secrets at write time, so
      a stored item is never a redaction.
    """
    captured = _iso(getattr(record, "captured_at", None))
    citations = list(getattr(record, "citations", ()) or ())
    return {
        "id": record.key,
        "category": normalize_category(getattr(record, "category", None)),
        "title": record.key,
        "content": record.value,
        "durability": durability_from_store(record.durability),
        "confidence": confidence_to_enum(float(getattr(record, "confidence", 1.0))),
        "provenance": {
            "source": getattr(record, "source", "user"),
            "session_id": None,
            "recorded_at": captured,
            "note": citations[0] if citations else None,
        },
        "created_at": captured,
        "updated_at": captured,
        "last_accessed_at": _iso(getattr(record, "last_recalled_at", None)),
        "tags": list(getattr(record, "tags", ()) or ()),
        "redacted": False,
        "hidden": bool(getattr(record, "hidden", False)),
    }


# ---------------------------------------------------------------------------
# Jobs — mirrors com.aci.hermes.data.cockpit.CockpitJob (+ JobStatus / PublishState)
# ---------------------------------------------------------------------------

# Canonical job status — a SUPERSET of the JARVIS-Prime queue states and the
# UI's build→approve→publish workflow states, so both are expressible
# honestly with real data. The store produces the execution states
# (queued/running/paused/blocked/disconnected/completed/failed/cancelled);
# the publish-workflow states (draft/waiting_for_approval/approved/
# publishing/published) come from a pipeline-set ``metadata.workflow_status``.
# The Android ``JobStatus`` enum gains PAUSED/BLOCKED/DISCONNECTED/COMPLETED
# when it is aligned to this contract.
JOB_STATUSES: tuple[str, ...] = (
    "DRAFT",
    "QUEUED",
    "RUNNING",
    "PAUSED",
    "BLOCKED",
    "DISCONNECTED",
    "COMPLETED",
    "WAITING_FOR_APPROVAL",
    "APPROVED",
    "PUBLISHING",
    "PUBLISHED",
    "FAILED",
    "CANCELLED",
)

PUBLISH_STATES: tuple[str, ...] = ("NOT_STARTED", "IN_PROGRESS", "SUCCEEDED", "FAILED")

# JobQueue ``state`` → canonical job status.
_JOB_STATUS_FROM_STATE: dict[str, str] = {
    "queued": "QUEUED",
    "running": "RUNNING",
    "paused": "PAUSED",
    "blocked": "BLOCKED",
    "disconnected": "DISCONNECTED",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
}


def job_status(state: Any, workflow_status: Any = None) -> str:
    """Resolve the canonical job status.

    A pipeline-set ``workflow_status`` (e.g. ``waiting_for_approval``,
    ``published``) takes precedence when it is a known canonical member;
    otherwise the raw queue ``state`` is mapped. Honest fallback: QUEUED.
    """
    if workflow_status:
        up = str(workflow_status).strip().upper()
        if up in JOB_STATUSES:
            return up
    return _JOB_STATUS_FROM_STATE.get(str(state), "QUEUED")


def normalize_publish_state(raw: Any) -> Optional[str]:
    if not raw:
        return None
    up = str(raw).strip().upper()
    return up if up in PUBLISH_STATES else None


def _epoch_iso(ts: Any) -> Optional[str]:
    try:
        t = float(ts)
    except (TypeError, ValueError):
        return None
    if t <= 0:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def _first_line(text: Any, limit: int = 120) -> Optional[str]:
    if not text:
        return None
    stripped = str(text).strip()
    if not stripped:
        return None
    line = stripped.splitlines()[0].strip()
    if not line:
        return None
    return (line[: limit - 3] + "...") if len(line) > limit else line


def _validation_summary(md: dict[str, Any]) -> Optional[dict[str, int]]:
    v = md.get("validation") or md.get("validation_summary")
    if not isinstance(v, dict):
        return None
    try:
        return {
            "pass": int(v.get("pass", 0) or 0),
            "fail": int(v.get("fail", 0) or 0),
            "pending": int(v.get("pending", 0) or 0),
        }
    except (TypeError, ValueError):
        return None


def cockpit_job(entry: Any) -> dict[str, Any]:
    """Project a ``job_queue.JobQueueEntry`` into the canonical cockpit
    ``CockpitJob`` (Android product spec).

    Honest derivation: title from ``metadata.title`` or the first prompt
    line or the id; the primary worker from the workers list; git/publish
    metadata surfaced from ``metadata`` when the pipeline has populated it,
    else ``null`` (never invented).
    """
    md = dict(getattr(entry, "metadata", None) or {})
    workers = list(getattr(entry, "workers", None) or [])
    worker_id = md.get("worker_id") or (
        getattr(workers[0], "worker_id", "") if workers else ""
    )
    created = _epoch_iso(getattr(entry, "created_at", 0))
    return {
        "id": getattr(entry, "job_id", ""),
        "title": md.get("title")
        or _first_line(getattr(entry, "prompt", ""))
        or getattr(entry, "job_id", ""),
        "worker_id": worker_id,
        "status": job_status(getattr(entry, "state", ""), md.get("workflow_status")),
        "created_at": created,
        "updated_at": _epoch_iso(getattr(entry, "updated_at", 0)) or created,
        "workspace_path": getattr(entry, "repo_root", "") or md.get("workspace_path") or None,
        "branch": md.get("branch"),
        "base_branch": md.get("base_branch"),
        "remote": md.get("remote"),
        "validation_summary": _validation_summary(md),
        "publish_state": normalize_publish_state(md.get("publish_state")),
    }


__all__ = [
    "JOB_STATUSES",
    "MEMORY_CATEGORIES",
    "MEMORY_CONFIDENCES",
    "MEMORY_DURABILITIES",
    "PUBLISH_STATES",
    "cockpit_job",
    "confidence_to_enum",
    "confidence_to_float",
    "durability_from_store",
    "durability_to_store",
    "job_status",
    "memory_item",
    "normalize_category",
    "normalize_publish_state",
]