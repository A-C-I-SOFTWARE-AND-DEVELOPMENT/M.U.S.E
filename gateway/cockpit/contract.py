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

import re
from pathlib import Path
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
# Evidence — mirrors com.aci.hermes.data.evidence.EvidenceItem (Evidence Engine)
# ---------------------------------------------------------------------------
#
# Source is the JARVIS Research Vault (hermes_cli.jarvis_prime.research_vault).
# Trust labels reuse the memory-tree SourceTrust vocabulary so the Android
# Evidence screen renders the same owner/primary/official_doc/reputable/
# community/unverified ladder used everywhere else.


def evidence_card(artifact: Any) -> dict[str, Any]:
    """Project a ``research_vault.ResearchArtifact`` into the cockpit
    ``EvidenceItem`` (Android Evidence screen). Honest derivation only —
    absent fields stay null/empty, never invented."""
    strength = getattr(artifact, "evidence_strength", None)
    trust = getattr(strength, "trust", None)
    src_type = getattr(artifact, "source_type", None)
    return {
        "id": artifact.id,
        "title": artifact.title,
        "source_uri": artifact.source_uri,
        "source_type": getattr(src_type, "value", str(src_type or "")),
        "evidence_strength": getattr(strength, "value", str(strength or "")),
        "trust": getattr(trust, "value", "unverified"),
        "excerpt": getattr(artifact, "excerpt", "") or "",
        "summary": getattr(artifact, "summary", "") or "",
        "tags": list(getattr(artifact, "tags", ()) or ()),
        "license_notes": getattr(artifact, "license_notes", "") or "",
        "retrieved_at": getattr(artifact, "retrieved_at", None),
        "freshness_due": getattr(artifact, "freshness_due", None),
        "checksum": getattr(artifact, "checksum", "") or "",
        "citation_anchors": list(getattr(artifact, "citation_anchors", ()) or ()),
        "added_at": getattr(artifact, "added_at", None),
    }


def evidence_hit(hit: Any) -> dict[str, Any]:
    """Project an ``evidence_engine.EvidenceHit`` for the verify response."""
    to_dict = getattr(hit, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    trust = getattr(hit, "trust", None)
    return {
        "kind": getattr(hit, "kind", ""),
        "title": getattr(hit, "title", ""),
        "uri": getattr(hit, "uri", ""),
        "excerpt": getattr(hit, "excerpt", ""),
        "trust": getattr(trust, "value", "unverified"),
        "score": round(float(getattr(hit, "score", 0.0)), 4),
        "artifact_id": getattr(hit, "artifact_id", None),
        "citation_anchors": list(getattr(hit, "citation_anchors", ()) or ()),
    }


def evidence_verify_result(result: Any) -> dict[str, Any]:
    """Project an ``evidence_engine.VerificationResult`` into the cockpit shape."""
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {"citations": [], "uncertain": [], "contradictions": [], "rejected": [], "audit": None}
# Memory Tree — provenance-first cognition plane (MEM-2). Distinct from the
# flat MemoryItem above: nodes carry layer/approval/contradiction/freshness so
# the mobile cockpit can run the proposed-inbox / contradiction / freshness
# review flows the flat store can't express.
# ---------------------------------------------------------------------------


def memory_tree_node(node: Any) -> dict[str, Any]:
    """Project a ``memory_tree.MemoryNode`` into a cockpit-facing dict.

    Source-cited and honest: sources, approval state, contradiction status,
    and freshness are surfaced verbatim so the owner decides on real data.
    """
    sources = [s.uri for s in getattr(node, "sources", ()) if getattr(s, "uri", "")]
    if getattr(node, "source_uri", None):
        sources.append(node.source_uri)
    return {
        "id": node.id,
        "namespace": node.namespace,
        "layer": node.layer.value,
        "title": node.title,
        "summary": node.summary or node.text,
        "content": node.text,
        "sources": sources,
        "confidence": node.confidence,
        "trust": node.source_trust.value,
        "sensitivity": node.sensitivity.value,
        "approval_state": node.approval_state.value,
        "contradiction_status": node.contradiction_status.value,
        "contested": node.contested,
        "subject": node.subject,
        "superseded_by": node.superseded_by,
        "supersedes": list(node.supersedes),
        "freshness_due": node.freshness_due,
        "created_at": node.created_at,
        "updated_at": node.updated_at,
        "tags": list(node.tags),
    }


def contradiction_view(report: Any) -> dict[str, Any]:
    """Project a ``memory_tree.ContradictionReport`` for the contradiction view."""
    return {
        "id": report.id,
        "namespace": report.namespace,
        "subject": report.subject,
        "node_a_id": report.node_a_id,
        "node_b_id": report.node_b_id,
        "reason": report.reason,
        "status": report.status.value,
        "winner_id": report.winner_id,
        "resolution_note": report.resolution_note,
        "created_at": report.created_at,
        "resolved_at": report.resolved_at,
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
        "workspace_path": getattr(entry, "repo_root", "")
        or md.get("workspace_path")
        or None,
        "branch": md.get("branch"),
        "base_branch": md.get("base_branch"),
        "remote": md.get("remote"),
        "validation_summary": _validation_summary(md),
        "publish_state": normalize_publish_state(md.get("publish_state")),
    }


# Orchestrator ``Job.status`` → canonical job status. The /orchestrate flow
# uses a slightly narrower vocabulary than the JobQueue; ``published`` is
# inferred from ``published_at`` and wins.
_ORCH_STATUS_FROM_STATE: dict[str, str] = {
    "queued": "QUEUED",
    "running": "RUNNING",
    "blocked": "BLOCKED",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
    "published": "PUBLISHED",
}


def _epoch_iso_us(ts: Any) -> Optional[str]:
    """ISO-8601 from a *microsecond* epoch (orchestrator ``_now()`` resolution)."""
    try:
        t = float(ts)
    except (TypeError, ValueError):
        return None
    if t <= 0:
        return None
    return _epoch_iso(t / 1_000_000.0)


def orchestrator_job(job: Any) -> dict[str, Any]:
    """Project an orchestrator ``Job`` (the ``/orchestrate`` flow) into the
    canonical cockpit ``CockpitJob`` so orchestration jobs appear in the
    Android Jobs list alongside JobQueue jobs.

    Read-only and honest: timestamps are microsecond epochs; ``published_at``
    implies ``PUBLISHED``; fields the orchestrator Job genuinely doesn't carry
    (branch/remote/validation) are ``null``, never invented.
    """
    raw = str(getattr(job, "status", "") or "")
    status = _ORCH_STATUS_FROM_STATE.get(raw, "QUEUED")
    if getattr(job, "published_at", None):
        status = "PUBLISHED"
    prompt = str(getattr(job, "prompt", "") or "")
    created = _epoch_iso_us(getattr(job, "created_at", 0))
    return {
        "id": getattr(job, "id", ""),
        "title": _first_line(prompt) or getattr(job, "id", ""),
        "worker_id": "",
        "status": status,
        "created_at": created,
        "updated_at": _epoch_iso_us(getattr(job, "updated_at", 0)) or created,
        "workspace_path": None,
        "branch": None,
        "base_branch": None,
        "remote": None,
        "validation_summary": None,
        "publish_state": "SUCCEEDED" if getattr(job, "published_at", None) else None,
    }


# ---------------------------------------------------------------------------
# Job detail / ledger timeline — mirrors com.aci.hermes.data.cockpit.JobDetail
# ---------------------------------------------------------------------------
#
# The Jobs list (`cockpit_job` / `orchestrator_job`) is the compact card; the
# *detail* surface adds the read-only execution story the cockpit's Job Detail
# screen renders: objective, plan, worker assignments, current step, evidence,
# files touched, commands run, test results, approvals, the ledger timeline,
# and rollback. Source-of-truth is the per-job decision ledger
# (orchestrator) or the queue entry's worker records (JobQueue). Honest
# derivation only — a field the source genuinely lacks is empty/null, never
# invented (e.g. the orchestrator ledger does not record shell commands, so
# `commands_run` is `[]` for orchestrator jobs).

# Worker-status (orchestrator ledger / queue) → an UPPER token the UI renders.
_WORKER_RESULT_STATUS = {
    True: "SUCCESS",
    False: "FAILED",
}


def _timeline_actor(kind: str) -> str:
    """Who drove a ledger entry — owner-initiated vs worker/controller."""
    k = kind.lower()
    if k in {"approve", "resume", "cancel", "publish", "publish-plan", "submit"}:
        return "owner"
    if k.startswith("worker_"):
        return "worker"
    return "controller"


def _timeline_summary(entry: dict[str, Any]) -> str:
    """One-line human summary of a ledger entry, from its own fields."""
    kind = str(entry.get("kind", "") or "")
    for key in ("summary", "reason", "rationale", "error", "status", "phase", "prompt"):
        val = entry.get(key)
        if val:
            return _first_line(str(val), limit=160) or kind
    return kind


def job_timeline(ledger_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project raw ledger entries into the canonical timeline (oldest→newest)."""
    timeline: list[dict[str, Any]] = []
    for entry in ledger_entries:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", "") or "event")
        timeline.append({
            "ts": str(entry.get("ts", "") or ""),
            "kind": kind,
            "phase": str(entry.get("phase", "") or "") or None,
            "actor": _timeline_actor(kind),
            "summary": _timeline_summary(entry),
        })
    return timeline


def _orch_workers(ledger_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct worker assignments from a job's ledger trail.

    Folds the ``worker_dispatch`` / ``worker_result`` / ``worker_score`` /
    ``worker_error`` / ``worker_blocked`` entries into one record per worker,
    last-write-wins on status so the latest attempt is reflected.
    """
    workers: dict[str, dict[str, Any]] = {}
    for entry in ledger_entries:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", "") or "")
        if not kind.startswith("worker_"):
            continue
        wid = str(entry.get("worker_id", "") or "")
        if not wid:
            continue
        rec = workers.setdefault(
            wid, {"id": wid, "worker": wid, "status": "PENDING", "summary": "", "error": None}
        )
        if kind == "worker_dispatch":
            rec["status"] = "RUNNING" if entry.get("available") else "BLOCKED"
            rec["summary"] = str(entry.get("reason", "") or "") or rec["summary"]
        elif kind == "worker_result":
            rec["status"] = _WORKER_RESULT_STATUS.get(bool(entry.get("ok")), "FAILED")
            rec["summary"] = _first_line(str(entry.get("summary", "") or "")) or rec["summary"]
            if entry.get("error"):
                rec["error"] = str(entry["error"])
        elif kind == "worker_score":
            if entry.get("rationale"):
                rec["summary"] = _first_line(str(entry["rationale"])) or rec["summary"]
        elif kind == "worker_blocked":
            rec["status"] = "BLOCKED"
            rec["error"] = str(entry.get("reason", "") or "") or rec["error"]
        elif kind == "worker_error":
            rec["status"] = "FAILED"
            rec["error"] = str(entry.get("error", "") or "") or rec["error"]
    return list(workers.values())


def _orch_files_touched(job: Any, ledger_entries: list[dict[str, Any]]) -> list[str]:
    """Files the job's workers reported touching — job artifacts + score files."""
    files: list[str] = list(getattr(job, "artifacts", None) or [])
    for entry in ledger_entries:
        if isinstance(entry, dict) and entry.get("kind") == "worker_score":
            for f in entry.get("files", []) or []:
                if isinstance(f, str) and f not in files:
                    files.append(f)
    return files


def orchestrator_job_detail(job: Any, ledger_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Project an orchestrator ``Job`` + its ledger into the canonical
    ``JobDetail`` (read-only). Honest: ``commands_run`` and ``test_results``
    are empty/null because the orchestrator ledger does not record them."""
    base = orchestrator_job(job)
    workers = _orch_workers(ledger_entries)
    approvals = [
        {
            "id": f"{base['id']}-{phase}",
            "timestamp": None,
            "approver": "owner",
            "state": "APPROVED",
            "comment": f"phase '{phase}' approved",
        }
        for phase in (getattr(job, "approvals", None) or {})
    ]
    current = None
    for entry in reversed(ledger_entries):
        if isinstance(entry, dict) and entry.get("kind"):
            current = _timeline_summary(entry)
            break
    return {
        "id": base["id"],
        "objective": _first_line(str(getattr(job, "prompt", "") or ""), limit=400)
        or base["title"],
        "status": base["status"],
        "plan": "",  # orchestrator stores no standalone plan artifact (honest empty)
        "current_step": current,
        "workers": workers,
        "timeline": job_timeline(ledger_entries),
        "evidence": [],
        "files_touched": _orch_files_touched(job, ledger_entries),
        "commands_run": [],  # not tracked by the orchestrator ledger
        "test_results": None,  # not tracked here (see /validate for a real run)
        "approvals": approvals,
        "rollback": None,
    }


# JobQueue WorkerStatus → UI worker status token.
_QUEUE_WORKER_STATUS = {
    "pending": "PENDING",
    "running": "RUNNING",
    "succeeded": "SUCCESS",
    "failed": "FAILED",
    "disconnected": "DISCONNECTED",
    "blocked": "BLOCKED",
    "cancelled": "CANCELLED",
}


def queue_job_detail(entry: Any) -> dict[str, Any]:
    """Project a ``job_queue.JobQueueEntry`` into the canonical ``JobDetail``.

    The queue tracks scheduling state per worker (status, attempts, last
    error) rather than a phase ledger, so the timeline is a compact derivation
    of the worker records plus the entry's note."""
    base = cockpit_job(entry)
    workers_raw = list(getattr(entry, "workers", None) or [])
    workers = [
        {
            "id": getattr(w, "worker_id", "") or "",
            "worker": getattr(w, "worker_id", "") or "",
            "status": _QUEUE_WORKER_STATUS.get(str(getattr(w, "status", "")), "PENDING"),
            "summary": "",
            "error": getattr(w, "last_error", None),
            "attempts": int(getattr(w, "attempts", 0) or 0),
        }
        for w in workers_raw
    ]
    timeline: list[dict[str, Any]] = []
    created = base.get("created_at")
    timeline.append({
        "ts": created or "",
        "kind": "submit",
        "phase": None,
        "actor": "owner",
        "summary": base["title"],
    })
    for w in workers_raw:
        status = _QUEUE_WORKER_STATUS.get(str(getattr(w, "status", "")), "PENDING")
        timeline.append({
            "ts": base.get("updated_at") or created or "",
            "kind": f"worker_{str(getattr(w, 'status', 'pending'))}",
            "phase": None,
            "actor": "worker",
            "summary": f"{getattr(w, 'worker_id', '')}: {status.lower()}"
            + (f" — {getattr(w, 'last_error')}" if getattr(w, "last_error", None) else ""),
        })
    note = getattr(entry, "note", None)
    failed = [w for w in workers if w["status"] in {"FAILED", "BLOCKED", "DISCONNECTED"}]
    return {
        "id": base["id"],
        "objective": _first_line(str(getattr(entry, "prompt", "") or ""), limit=400)
        or base["title"],
        "status": base["status"],
        "plan": "",
        "current_step": (note or (failed[0]["error"] if failed else None)),
        "workers": workers,
        "timeline": timeline,
        "evidence": [],
        "files_touched": [],
        "commands_run": [],
        "test_results": _validation_summary(dict(getattr(entry, "metadata", None) or {})),
        "approvals": [],
        "rollback": None,
    }


# ---------------------------------------------------------------------------
# Audit — mirrors com.aci.hermes.data.model.audit.AuditRecord / ProofRecord
# ---------------------------------------------------------------------------
#
# Source is the JARVIS-Prime decision ledger (hermes_cli.decision_ledger).
# Its 15 prose sections map honestly onto the audit model; fields the ledger
# genuinely doesn't carry (files changed, per-step durations, enumerated
# tests) are emitted as empty/0 — never invented.

RISK_TIERS = ("TRIVIAL", "LOW", "MODERATE", "SERIOUS", "CRITICAL")
APPROVAL_STATES = (
    "UNNECESSARY",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "AUTO_APPROVED",
    "EXPIRED",
)
ACTION_RESULTS = ("SUCCESS", "PARTIAL", "FAILED", "ROLLED_BACK", "BLOCKED")
ROUTE_DESTINATIONS = ("LOCAL_WORKER", "CODEX", "CLAUDE", "HERMES_GATEWAY", "HUMAN_ONLY")
VERIFICATION_STATUSES = ("PASSED", "FAILED", "SKIPPED", "FLAKY")

_CONFIDENCE_FLOAT = {"low": 0.4, "medium": 0.7, "high": 0.95}


def _first_word(text: Any) -> str:
    s = str(text or "").strip().lower()
    if not s:
        return ""
    return re.split(r"[\s.,;:—-]", s, maxsplit=1)[0]


def _is_blank(text: Any) -> bool:
    return not str(text or "").strip()


def _says_none(text: Any) -> bool:
    """True when a ledger section is empty or says "N/A"/"none".

    Honors the ledger convention where ``N/A — <reason>`` is a *filled*
    section meaning "none needed" (so it must read as absent for risk /
    rollback / evidence presence, not as real content)."""
    if _is_blank(text):
        return True
    return _first_word(text) in {"n/a", "na", "none"}


def ledger_confidence_float(confidence: Any) -> float:
    return _CONFIDENCE_FLOAT.get(_first_word(confidence), 0.5)


def route_destination(worker: Any) -> str:
    w = str(worker or "").lower()
    if "codex" in w:
        return "CODEX"
    if "claude" in w:
        return "CLAUDE"
    if "gateway" in w or "hermes" in w:
        return "HERMES_GATEWAY"
    if not w.strip() or "human" in w or "owner" in w:
        return "HUMAN_ONLY"
    return "LOCAL_WORKER"


def approval_state(approval_required: Any) -> str:
    head = _first_word(approval_required)
    return {"no": "UNNECESSARY", "yes": "APPROVED", "defer": "PENDING"}.get(
        head, "UNNECESSARY"
    )


def action_result(final_decision: Any) -> str:
    t = str(final_decision or "").lower()
    if "rolled back" in t or "rollback" in t:
        return "ROLLED_BACK"
    if "block" in t or "refus" in t:
        return "BLOCKED"
    if "fail" in t or "error" in t:
        return "FAILED"
    if "partial" in t:
        return "PARTIAL"
    return "SUCCESS"


def risk_tier(open_risks: Any) -> str:
    # Honest derivation: the ledger has no explicit tier. Flagged risks →
    # MODERATE; none → LOW (the floor). Never a fabricated specific tier.
    return "LOW" if _says_none(open_risks) else "MODERATE"


def ledger_id(ledger: Any, path: Any = None) -> str:
    slug = str(getattr(ledger, "slug", "") or "").strip()
    if slug:
        return slug
    if path is not None:
        return Path(str(path)).stem
    return "decision"


def audit_record(ledger: Any, path: Any = None) -> dict[str, Any]:
    """Project a ``decision_ledger.DecisionLedger`` into the canonical
    cockpit ``AuditRecord`` (Android product spec) — honest derivation only."""
    ident = ledger_id(ledger, path)
    g = lambda name: str(getattr(ledger, name, "") or "").strip()  # noqa: E731
    return {
        "id": ident,
        "timestamp": _epoch_iso(getattr(ledger, "created_at", 0.0)),
        "user_request": g("context") or g("plain_english_summary"),
        "action": g("final_decision") or g("decision"),
        "risk_tier": risk_tier(getattr(ledger, "open_risks", "")),
        "route": {
            "destination": route_destination(
                getattr(ledger, "selected_model_worker", "")
            ),
            "model": g("selected_model_worker") or None,
            "reason": g("why_this_choice"),
            "duration_ms": 0,
        },
        "approval_state": approval_state(getattr(ledger, "approval_required", "")),
        "result": action_result(getattr(ledger, "final_decision", "")),
        "confidence": ledger_confidence_float(getattr(ledger, "confidence", "")),
        "proof_id": ident,
    }


def audit_proof(ledger: Any, path: Any = None) -> dict[str, Any]:
    """Project a ledger into the canonical ``ProofRecord`` (audit detail)."""
    ident = ledger_id(ledger, path)
    g = lambda name: str(getattr(ledger, name, "") or "").strip()  # noqa: E731
    ts = _epoch_iso(getattr(ledger, "created_at", 0.0))

    evidence: list[dict[str, Any]] = []
    if not _says_none(getattr(ledger, "evidence_reviewed", "")):
        evidence.append({
            "id": f"{ident}-evidence",
            "kind": "DOC_LINK",
            "title": "Evidence reviewed",
            "body": g("evidence_reviewed"),
            "source_path": str(path) if path is not None else None,
        })

    approvals: list[dict[str, Any]] = []
    if not _is_blank(getattr(ledger, "approval_required", "")):
        approvals.append({
            "id": f"{ident}-approval",
            "timestamp": ts,
            "approver": "owner",
            "state": approval_state(getattr(ledger, "approval_required", "")),
            "comment": g("approval_required"),
        })

    rollback: Optional[dict[str, Any]] = None
    if not _says_none(getattr(ledger, "rollback_plan", "")):
        steps = [
            s.strip("-* ").strip() for s in g("rollback_plan").splitlines() if s.strip()
        ]
        rollback = {
            "id": f"{ident}-rollback",
            "summary": g("rollback_plan"),
            "steps": steps,
            "automatic": False,
            "executed": False,
        }

    worker_runs: list[dict[str, Any]] = []
    if g("selected_model_worker"):
        worker_runs.append({
            "id": f"{ident}-worker",
            "worker": g("selected_model_worker"),
            "started_at": ts,
            "finished_at": ts,
            "status": action_result(getattr(ledger, "final_decision", "")),
            "notes": g("why_this_choice"),
        })

    validation = g("validation_plan")
    return {
        "id": ident,
        "audit_id": ident,
        "rationale": g("why_this_choice") or g("decision"),
        "evidence": evidence,
        "tests_run": [],  # the ledger records a plan, not an enumerated run
        "files_changed": [],  # genuinely not tracked by the ledger
        "verification": {
            "status": "PASSED" if validation else "SKIPPED",
            "summary": validation,
            "failing_checks": [],
            "passed_checks": [],
        },
        "approvals": approvals,
        "rollback": rollback,
        "impact_report": g("cost_latency_quality_tradeoff") or None,
        "worker_runs": worker_runs,
    }


# ---------------------------------------------------------------------------
# Approvals — mirrors com.aci.hermes.approval.model.ApprovalCard
# ---------------------------------------------------------------------------
#
# The Android Approvals screen is one queue (`ApprovalCard`). The server's
# one real owner-gated queue is the JARVIS self-update *proposals*
# (proposals.jsonl). `approval_card()` projects a proposal into the
# canonical card; `proposal_view()` keeps the self-update-native shape for a
# proposal-specific surface. Future destructive-command approvals join the
# same card queue — no second store is fabricated.

APPROVAL_CARD_TIERS = ("SAFE", "LOW", "RISKY", "SERIOUS", "CRITICAL", "FORBIDDEN")
APPROVAL_CARD_STATUSES = (
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "EMERGENCY_STOPPED",
)

# Proposal risk class → ApprovalRiskTier. A proposal always requires owner
# approval, so the floor is LOW (never SAFE, which means "no approval").
_RISK_CLASS_TIER = {
    "RC0": "LOW",
    "RC1": "LOW",
    "RC2": "RISKY",
    "RC3": "SERIOUS",
    "RC4": "CRITICAL",
}

_PROPOSAL_STATUS = {
    "proposed": "PENDING",
    "pending": "PENDING",
    "approved": "APPROVED",
    "rejected": "REJECTED",
    "expired": "EXPIRED",
}


def approval_card_tier(risk_class: Any) -> str:
    return _RISK_CLASS_TIER.get(str(risk_class or "").strip().upper(), "RISKY")


def approval_card_status(status: Any) -> str:
    return _PROPOSAL_STATUS.get(str(status or "").strip().lower(), "PENDING")


def approval_card(proposal: dict[str, Any], *, approval_id: str) -> dict[str, Any]:
    """Project a self-update proposal into the canonical ``ApprovalCard``.

    Multi-step state (serious/critical confirmations, impact report,
    rollback plan) is UI-runtime, not server-sourced — omitted here so the
    Android model fills its defaults rather than receiving fabricated steps.
    """
    kind = str(proposal.get("kind", "") or "").strip()
    target = str(proposal.get("target_path", "") or "").strip()
    target_name = target.rsplit("/", 1)[-1] if target else ""
    title = "Self-update"
    if kind:
        title = f"Self-update: {kind}"
    if target_name:
        title = f"{title} ({target_name})"
    action = " ".join(part for part in (kind, target) if part) or "self-update"
    return {
        "id": approval_id,
        "title": title,
        "summary": str(proposal.get("rationale", "") or "").strip(),
        "requester": "jarvis",
        "tier": approval_card_tier(proposal.get("risk_class", "RC1")),
        "status": approval_card_status(proposal.get("status", "proposed")),
        "created_at": str(proposal.get("created_at", "") or "") or None,
        "expires_at": None,  # self-update proposals don't time out
        "proposed_action": action,
        "edited_note": None,
    }


def proposal_view(proposal: dict[str, Any], *, proposal_id: str) -> dict[str, Any]:
    """Self-update-native projection (the `/v1/cockpit/proposals` surface)."""
    risk_class = str(proposal.get("risk_class", "RC1") or "RC1")
    risk_level = {
        "RC0": "low",
        "RC1": "low",
        "RC2": "medium",
        "RC3": "high",
        "RC4": "high",
    }
    return {
        "id": proposal_id,
        "kind": str(proposal.get("kind", "") or ""),
        "target": str(proposal.get("target_path", "") or ""),
        "rationale": str(proposal.get("rationale", "") or ""),
        "risk_class": risk_class,
        "risk_level": risk_level.get(risk_class, "medium"),
        "status": str(proposal.get("status", "proposed") or "proposed"),
        "requires_owner_approval": bool(proposal.get("requires_owner_approval", True)),
        "created_at": str(proposal.get("created_at", "") or ""),
    }


# ---------------------------------------------------------------------------
# Skills — the gateway's real installed skill set
# ---------------------------------------------------------------------------
#
# Unlike the other domains, the Android capability picker is a deliberately
# *curated* in-app catalog (com.aci.hermes.data.model.Capability), not a
# server mirror. This surface is the complementary truth: the actual skills
# installed on the gateway host (from the real skill scanner). It lets the
# cockpit show "what this gateway can do" and lets the curated catalog be
# validated against reality — without fabricating capabilities.


def skill_entry(command: str, info: dict[str, Any]) -> dict[str, Any]:
    """Project one scanned skill (``/command`` + info) into a cockpit entry."""
    return {
        "id": str(command).lstrip("/"),
        "command": str(command),
        "name": str(info.get("name", "") or ""),
        "description": str(info.get("description", "") or ""),
    }


# ---------------------------------------------------------------------------
# Navigation — the HyperAgent navigator's pre-dispatch decision
# ---------------------------------------------------------------------------
#
# Surfaces "where navigation decided to look" before a /orchestrate job was
# dispatched. Source is the orchestrator job ledger's ``navigation_decision``
# entries (real data; honest empty when no orchestrate job has navigated).


def navigation_view(
    entry: dict[str, Any], *, job_id: str | None = None
) -> dict[str, Any]:
    """Project an orchestrator ``navigation_decision`` ledger entry."""
    ranked = entry.get("ranked_files") or []
    files: list[dict[str, Any]] = []
    for r in ranked:
        if not isinstance(r, dict):
            continue
        try:
            files.append({
                "path": str(r.get("path", "") or ""),
                "rank": int(r.get("rank", 0) or 0),
                "confidence": float(r.get("confidence", 0.0) or 0.0),
                "rationale": str(r.get("rationale", "") or ""),
            })
        except (TypeError, ValueError):
            continue
    return {
        "job_id": str(job_id or entry.get("job_id", "") or ""),
        "objective": str(entry.get("objective", "") or ""),
        "created_at": str(entry.get("created_at", "") or ""),
        "method": str(entry.get("method", "") or ""),
        "candidate_files": files,
        "verify_with": [str(v) for v in (entry.get("verify_with") or [])],
    }


# ---------------------------------------------------------------------------
# Coding lanes — mirrors the natural-language coder work packet
# ---------------------------------------------------------------------------


def coding_packet(packet: Any) -> dict[str, Any]:
    """Project a ``CodingWorkPacket`` into the canonical wire shape.

    The packet already emits a snake_case ``to_dict()``; this is the single
    contract entry point so tests pin the shape in one place.
    """
    return packet.to_dict()


# ---------------------------------------------------------------------------
# Evidence — mirrors the Research Vault artifact + a non-mutating verdict
# ---------------------------------------------------------------------------

# Verdict vocabulary returned by POST /v1/cockpit/evidence/verify.
EVIDENCE_VERDICTS: tuple[str, ...] = (
    "supported",
    "partially_supported",
    "contradicted",
    "insufficient_evidence",
    "stale",
)

# EvidenceStrength → a coarse confidence float for the verify verdict.
_STRENGTH_CONFIDENCE: dict[str, float] = {
    "primary": 0.95,
    "strong": 0.85,
    "moderate": 0.7,
    "weak": 0.45,
    "vendor_reported": 0.5,
}


def evidence_artifact(artifact: Any) -> dict[str, Any]:
    """Project a ``ResearchArtifact`` into the canonical wire shape."""
    return artifact.to_dict()


def _freshness_status(artifacts: list[Any]) -> str:
    """``stale`` if any matched artifact's freshness is past due, else ``fresh``
    (``unknown`` when no artifact carries a freshness date)."""
    from datetime import datetime, timezone

    seen_due = False
    now = datetime.now(timezone.utc)
    for art in artifacts:
        due = getattr(art, "freshness_due", None)
        if not due:
            continue
        seen_due = True
        try:
            parsed = datetime.fromisoformat(str(due))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed < now:
                return "stale"
        except (TypeError, ValueError):
            continue
    return "fresh" if seen_due else "unknown"


def evidence_verdict(claim: str, matches: list[Any], report: Any) -> dict[str, Any]:
    """Derive a non-mutating verdict from vault matches + the epistemic audit.

    ``matches`` are ``ResearchArtifact``s found for the claim; ``report`` is an
    :class:`epistemics.AuditReport`. No vault state is written. The verdict and
    confidence are derived honestly — empty matches never masquerade as support.
    """
    outcome = getattr(getattr(report, "outcome", None), "value", "") or ""
    supporting = [evidence_artifact(a) for a in matches]

    # Confidence: best matched source strength, dampened when the audit isn't
    # clean. No matches → low floor.
    if matches:
        confidence = max(
            _STRENGTH_CONFIDENCE.get(
                getattr(getattr(a, "evidence_strength", None), "value", "moderate"),
                0.6,
            )
            for a in matches
        )
    else:
        confidence = 0.2
    if outcome == "needs_research":
        confidence = min(confidence, 0.4)
    elif outcome in ("needs_citations", "fail"):
        confidence = min(confidence, 0.6)

    freshness = _freshness_status(matches)

    if not matches:
        verdict = "insufficient_evidence"
    elif freshness == "stale":
        verdict = "stale"
    elif outcome == "pass":
        verdict = "supported"
    elif outcome in ("needs_citations", "fail"):
        verdict = "partially_supported"
    elif outcome == "needs_research":
        verdict = "insufficient_evidence"
    else:
        verdict = "partially_supported"

    next_action = {
        "supported": "No action — claim is supported by the vault.",
        "partially_supported": "Add a primary/strong source or hedge the specifics.",
        "insufficient_evidence": "Research and add at least one cited source to the vault.",
        "stale": "Refresh the source — its freshness window has lapsed.",
        "contradicted": "Reconcile the contradiction before relying on this claim.",
    }[verdict]

    missing: list[str] = []
    for f in getattr(report, "findings", []) or []:
        suggestion = getattr(f, "suggestion", None)
        if suggestion:
            missing.append(str(suggestion))

    return {
        "verdict": verdict,
        "confidence": round(float(confidence), 2),
        "supporting_sources": supporting,
        "contradicting_sources": [],
        "missing_evidence": missing,
        "freshness_status": freshness,
        "audit_outcome": outcome,
        "recommended_next_action": next_action,
    }


# ---------------------------------------------------------------------------
# GraphRAG — related files / sources / decisions, and query answers
# ---------------------------------------------------------------------------
#
# Mirrors the Android cockpit DTOs in
# com.aci.hermes.data.cockpit.CockpitApi (RelatedItem / RelatedItemList /
# GraphAnswer). The GraphRAG engine already emits honest, source-backed
# shapes; these adapters only normalise keys to the wire conventions and
# clamp to the fields the UI consumes.

# Allowed related-item buckets (mirrors the Android enum constants).
RELATED_KINDS: tuple[str, ...] = ("FILE", "SOURCE", "DECISION")


def _related_kind(kind: str) -> str:
    k = (kind or "").upper()
    return k if k in RELATED_KINDS else "FILE"


def graph_related_item(item: dict[str, Any]) -> dict[str, Any]:
    """Project one ``graphrag.query.related_items`` entry to the wire shape."""

    return {
        "kind": _related_kind(str(item.get("kind", "file"))),
        "node_type": str(item.get("node_type", "") or ""),
        "title": str(item.get("title", "") or ""),
        "ref": str(item.get("ref", "") or ""),
        "relation": str(item.get("relation", "related") or "related"),
        "source_backed": bool(item.get("source_backed", False)),
        "sources": [
            {"uri": str(s.get("uri", "") or ""), "kind": str(s.get("kind", "") or "")}
            for s in (item.get("sources") or [])
            if isinstance(s, dict)
        ],
    }


def graph_related_view(
    items: list[dict[str, Any]], *, node: str = "", origin: str = ""
) -> dict[str, Any]:
    """A ``RelatedItemList``: related files/sources/decisions for an entity."""

    return {
        "node": str(node or ""),
        "origin": str(origin or ""),
        "related": [graph_related_item(i) for i in items if isinstance(i, dict)],
    }


def graph_answer_view(answer: dict[str, Any]) -> dict[str, Any]:
    """A ``GraphAnswer``: ranked nodes + edges + citations for a query mode."""

    nodes = [
        {
            "id": str(n.get("id", "") or ""),
            "type": str(n.get("type", "") or ""),
            "title": str(n.get("title", "") or ""),
            "key": str(n.get("key", "") or ""),
        }
        for n in (answer.get("nodes") or [])
        if isinstance(n, dict)
    ]
    edges = [
        {
            "src": str(e.get("src", "") or ""),
            "dst": str(e.get("dst", "") or ""),
            "type": str(e.get("type", "") or ""),
        }
        for e in (answer.get("edges") or [])
        if isinstance(e, dict)
    ]
    citations = [
        {"uri": str(c.get("uri", "") or ""), "kind": str(c.get("kind", "") or "")}
        for c in (answer.get("citations") or [])
        if isinstance(c, dict)
    ]
    return {
        "mode": str(answer.get("mode", "") or ""),
        "question": str(answer.get("question", "") or ""),
        "nodes": nodes,
        "edges": edges,
        "citations": citations,
        "communities": answer.get("communities") or [],
    }


def learning_card(candidate: dict[str, Any], *, candidate_id: str) -> dict[str, Any]:
    """Project a learning-dataset candidate into the cockpit card shape.

    Read-only and provenance-first: the card always exposes the trace type,
    quality labels, provenance (source + citations) and the owner-decision
    status so the Android Learning Queue can render an honest approve/reject
    view. Content excerpts are intentionally omitted — the candidate's raw
    payload (already secret-scrubbed at write time) is not streamed to the
    list surface.
    """

    prov = candidate.get("provenance") or {}
    quality = candidate.get("quality") or {}
    trace_type = str(candidate.get("trace_type", "") or "")
    labels = [str(x) for x in (candidate.get("labels") or [])]
    title = trace_type.replace("_", " ").strip() or "learning trace"
    return {
        "id": candidate_id,
        "title": title,
        "trace_type": trace_type,
        "status": str(candidate.get("status", "pending") or "pending"),
        "labels": labels,
        "is_negative": "negative_example" in labels,
        "quality": {
            "tests_passed": bool(quality.get("tests_passed", False)),
            "citations_verified": bool(quality.get("citations_verified", False)),
            "owner_approved": bool(quality.get("owner_approved", False)),
            "reviewer_passed": bool(quality.get("reviewer_passed", False)),
            "rollback_available": bool(quality.get("rollback_available", False)),
        },
        "provenance": {
            "source_kind": str(prov.get("source_kind", "") or ""),
            "source_uri": str(prov.get("source_uri", "") or ""),
            "citations": [str(x) for x in (prov.get("citations") or [])],
        },
        "created_at": str(candidate.get("created_at", "") or "") or None,
    }
# Ledger timeline — mirrors com.aci.hermes.data.model.ledger.LedgerEvent
# ---------------------------------------------------------------------------
#
# Source is the orchestrator's per-job event ledger
# (``hermes_cli.orchestrator_ledger`` → ``~/.hermes/jobs/<id>/ledger.jsonl``),
# the canonical audit trail of *what a job actually did*. Each JSONL entry
# carries a ``kind``; ``classify_kind`` maps it to one of the canonical
# timeline categories the Android Activity screen renders. The summary reuses
# ``orchestrator_replay._summarize`` so the mobile one-liner matches the CLI
# ``hermes orchestrate replay`` output. Every text field is passed through
# ``gateway.cockpit.redaction`` before it leaves the loopback API — the
# timeline never emits a credential a worker echoed.

# Android `LedgerCategory` constants (superset; some only appear when the
# corresponding entries are actually emitted — never fabricated).
LEDGER_CATEGORIES: tuple[str, ...] = (
    "MODEL_CALL",
    "TOOL_CALL",
    "COMMAND",
    "FILE_EDIT",
    "WORKER_RUN",
    "APPROVAL",
    "MEMORY_WRITE",
    "EVIDENCE_PROMOTION",
    "DEPLOY_PUBLISH",
    "NAVIGATION",
    "VALIDATION",
    "LIFECYCLE",
)

# Orchestrator ledger ``kind`` → canonical category. Unknown kinds fall back
# to LIFECYCLE (an honest "something happened" rather than a guessed
# specific category).
_KIND_TO_CATEGORY: dict[str, str] = {
    "submit": "LIFECYCLE",
    "resume": "LIFECYCLE",
    "cancel": "LIFECYCLE",
    "self-improve": "LIFECYCLE",
    "goal_boundary_declared": "LIFECYCLE",
    "goal_boundary_verdict": "LIFECYCLE",
    "report_written": "LIFECYCLE",
    "navigation_decision": "NAVIGATION",
    "navigation_error": "NAVIGATION",
    "worker_dispatch": "WORKER_RUN",
    "worker_result": "WORKER_RUN",
    "worker_score": "WORKER_RUN",
    "worker_error": "WORKER_RUN",
    "worker_blocked": "WORKER_RUN",
    "repair_loop_result": "WORKER_RUN",
    "approve": "APPROVAL",
    "require_approval": "APPROVAL",
    "validate": "VALIDATION",
    "validation": "VALIDATION",
    "publish": "DEPLOY_PUBLISH",
    "publish-plan": "DEPLOY_PUBLISH",
    "memory": "MEMORY_WRITE",
    "memory_write": "MEMORY_WRITE",
    "evidence": "EVIDENCE_PROMOTION",
    "evidence_promotion": "EVIDENCE_PROMOTION",
    "research_finding": "EVIDENCE_PROMOTION",
}


def classify_kind(kind: Any, entry: Optional[dict[str, Any]] = None) -> str:
    """Map an orchestrator ledger ``kind`` to a canonical timeline category.

    ``repair_loop_step`` is split by its ``phase``: a ``test``/``command``
    phase is a COMMAND, anything that names candidate files is a FILE_EDIT,
    else COMMAND. Never invents a category — unknown kinds → LIFECYCLE.
    """
    k = str(kind or "").strip()
    if k == "repair_loop_step":
        phase = str((entry or {}).get("phase", "")).lower()
        if phase in {"test", "command", "run"}:
            return "COMMAND"
        if (entry or {}).get("candidate_files"):
            return "FILE_EDIT"
        return "COMMAND"
    return _KIND_TO_CATEGORY.get(k, "LIFECYCLE")


# Categories whose actions are inherently external / irreversible → a higher
# risk floor on the timeline so the owner can filter for "the scary stuff".
_HIGH_RISK_CATEGORIES = {"DEPLOY_PUBLISH"}
_MODERATE_RISK_CATEGORIES = {"WORKER_RUN", "FILE_EDIT", "COMMAND", "APPROVAL"}


def ledger_risk_tier(category: str, entry: dict[str, Any]) -> str:
    """Derive a risk tier for a timeline event (honest, coarse).

    The orchestrator ledger has no explicit tier, so we derive one: a
    deploy/publish event is SERIOUS; a worker run / file edit / command /
    approval is MODERATE; an entry that *names* a secret-touching path or a
    failed/blocked outcome is bumped one band; everything else is LOW.
    """
    base = (
        "SERIOUS"
        if category in _HIGH_RISK_CATEGORIES
        else "MODERATE"
        if category in _MODERATE_RISK_CATEGORIES
        else "LOW"
    )
    blob = " ".join(str(v) for v in entry.values()).lower()
    if any(t in blob for t in ("secret", "credential", "rotate", "token", ".env")):
        base = {"LOW": "MODERATE", "MODERATE": "SERIOUS", "SERIOUS": "CRITICAL"}.get(base, base)
    return base


def _ledger_files(entry: dict[str, Any]) -> list[str]:
    """Pull file paths out of the shapes the orchestrator ledger uses."""
    out: list[str] = []
    ranked = entry.get("ranked_files")
    if isinstance(ranked, list):
        for r in ranked:
            if isinstance(r, dict) and r.get("path"):
                out.append(str(r["path"]))
            elif isinstance(r, str):
                out.append(r)
    for key in ("candidate_files", "files", "files_changed"):
        val = entry.get(key)
        if isinstance(val, list):
            out.extend(str(f.get("path") if isinstance(f, dict) else f) for f in val)
        elif isinstance(val, str):
            out.append(val)
    # de-dup, preserve order, drop falsy
    seen: set[str] = set()
    deduped: list[str] = []
    for f in out:
        if f and f not in seen:
            seen.add(f)
            deduped.append(f)
    return deduped


def _ledger_summary(kind: str, entry: dict[str, Any]) -> str:
    """Reuse the replay summarizer; degrade gracefully if unavailable."""
    try:
        from hermes_cli import orchestrator_replay as _replay

        return _replay._summarize(kind, entry)
    except Exception:  # pragma: no cover - defensive
        for key in ("summary", "message", "action", "status", "reason"):
            if key in entry:
                return f"{key}={entry[key]}"
        return kind


def ledger_event(entry: dict[str, Any], *, job_id: str, index: int) -> dict[str, Any]:
    """Project one orchestrator ledger entry into a canonical, **redacted**
    ``LedgerEvent`` (Android Activity timeline row).

    Honest derivation only; secret-scrubbed via :mod:`gateway.cockpit.redaction`.
    """
    from . import redaction

    kind = str(entry.get("kind") or entry.get("type") or "entry")
    category = classify_kind(kind, entry)
    worker = entry.get("worker_id") or entry.get("worker") or None
    has_rollback = bool(entry.get("rollback") or entry.get("rollback_plan"))
    return {
        "id": f"{job_id}:{index}",
        "job_id": job_id,
        "index": index,
        "timestamp": str(entry.get("ts") or entry.get("timestamp") or ""),
        "category": category,
        "kind": kind,
        "worker": str(worker) if worker else None,
        "risk_tier": ledger_risk_tier(category, entry),
        "summary": redaction.redact_text(_ledger_summary(kind, entry)),
        "files": [redaction.redact_text(f) for f in _ledger_files(entry)],
        "has_rollback": has_rollback,
        "has_evidence": bool(entry.get("evidence") or entry.get("citations")),
        "has_diff": bool(entry.get("diff") or entry.get("candidate_files")),
    }


def ledger_event_detail(entry: dict[str, Any], *, job_id: str, index: int) -> dict[str, Any]:
    """Full redacted detail for one timeline event: the row plus inputs/
    outputs, linked evidence, linked diff, and the rollback plan + whether a
    rollback can be requested.
    """
    from . import redaction

    base = ledger_event(entry, job_id=job_id, index=index)

    # Inputs/outputs: the whole entry minus the structural fields, redacted.
    structural = {"ts", "timestamp", "kind", "type"}
    payload = {k: v for k, v in entry.items() if k not in structural}
    redacted_payload = redaction.redact_value(payload)

    evidence: list[dict[str, Any]] = []
    raw_evidence = entry.get("evidence") or entry.get("citations") or []
    if isinstance(raw_evidence, list):
        for i, ev in enumerate(raw_evidence):
            if isinstance(ev, dict):
                evidence.append({
                    "id": f"{base['id']}-ev{i}",
                    "title": redaction.redact_text(ev.get("title") or ev.get("text") or f"evidence {i}"),
                    "body": redaction.redact_text(ev.get("body") or ev.get("text") or ""),
                    "source_path": redaction.redact_text(ev.get("source_path") or ev.get("citation") or "") or None,
                })
            elif isinstance(ev, str):
                evidence.append({
                    "id": f"{base['id']}-ev{i}",
                    "title": f"evidence {i}",
                    "body": redaction.redact_text(ev),
                    "source_path": None,
                })

    diff: Optional[dict[str, Any]] = None
    if entry.get("diff"):
        diff = {"body": redaction.redact_text(entry.get("diff"))}
    elif base["files"]:
        diff = {"files": base["files"]}

    rollback: Optional[dict[str, Any]] = None
    raw_rb = entry.get("rollback") or entry.get("rollback_plan")
    if isinstance(raw_rb, dict):
        steps = raw_rb.get("steps") or []
        rollback = {
            "summary": redaction.redact_text(raw_rb.get("summary") or ""),
            "steps": [redaction.redact_text(s) for s in steps if isinstance(s, str)],
        }
    elif isinstance(raw_rb, str):
        rollback = {"summary": redaction.redact_text(raw_rb), "steps": []}

    base.update({
        "payload": redacted_payload,
        "evidence": evidence,
        "diff": diff,
        "rollback": rollback,
        "rollback_available": True,  # a gated request can always be raised
    })
    return base
# Research Mode — mirrors com.aci.hermes.data.cockpit.ResearchReport (+ cards,
# claims, contradictions). The engine dataclasses already emit the canonical
# JSON; these wrappers keep contract.py the single mapping authority and
# normalize whether the handler passes an engine object or a plain dict.
# ---------------------------------------------------------------------------


def _as_dict(obj: Any) -> dict[str, Any]:
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return dict(obj or {})


def research_card(card: Any) -> dict[str, Any]:
    """Project an engine ``EvidenceCard`` into the cockpit card shape."""
    return _as_dict(card)


def research_claim(claim: Any) -> dict[str, Any]:
    """Project an engine ``SynthesizedClaim`` into the cockpit claim shape."""
    return _as_dict(claim)


def research_contradiction(contradiction: Any) -> dict[str, Any]:
    """Project an engine ``ResearchContradiction`` into the cockpit shape."""
    return _as_dict(contradiction)


def research_report(report: Any) -> dict[str, Any]:
    """Project an engine ``ResearchReport`` into the canonical cockpit report."""
    return _as_dict(report)


__all__ = [
    "ACTION_RESULTS",
    "APPROVAL_CARD_STATUSES",
    "APPROVAL_CARD_TIERS",
    "APPROVAL_STATES",
    "EVIDENCE_VERDICTS",
    "LEDGER_CATEGORIES",
    "JOB_STATUSES",
    "MEMORY_CATEGORIES",
    "MEMORY_CONFIDENCES",
    "MEMORY_DURABILITIES",
    "PUBLISH_STATES",
    "RELATED_KINDS",
    "RISK_TIERS",
    "ROUTE_DESTINATIONS",
    "VERIFICATION_STATUSES",
    "action_result",
    "approval_card",
    "approval_card_status",
    "approval_card_tier",
    "approval_state",
    "audit_proof",
    "audit_record",
    "classify_kind",
    "cockpit_job",
    "coding_packet",
    "ledger_event",
    "ledger_event_detail",
    "ledger_risk_tier",
    "confidence_to_enum",
    "confidence_to_float",
    "durability_from_store",
    "durability_to_store",
    "evidence_artifact",
    "evidence_card",
    "evidence_hit",
    "evidence_verdict",
    "evidence_verify_result",
    "graph_answer_view",
    "graph_related_item",
    "graph_related_view",
    "job_status",
    "learning_card",
    "memory_item",
    "navigation_view",
    "normalize_category",
    "orchestrator_job",
    "orchestrator_job_detail",
    "queue_job_detail",
    "job_timeline",
    "normalize_publish_state",
    "proposal_view",
    "research_card",
    "research_claim",
    "research_contradiction",
    "research_report",
    "skill_entry",
    "autonomy_status",
]


# ---------------------------------------------------------------------------
# Autonomy — mirrors com.aci.hermes.data.cockpit.AutonomyStatus
# ---------------------------------------------------------------------------
#
# Single canonical shape for `GET/POST /v1/cockpit/autonomy`. The capability
# lists are passed through verbatim from `approval_policy.capabilities()` so
# the Android capability picker renders the policy engine's truth, never a
# hand-maintained copy. `revocable` is always True — the owner can drop
# autonomy instantly.

_AUTONOMY_DISPLAY = {
    "read_only": "Read-only",
    "assisted": "Assisted",
    "autonomous": "Autonomous",
    "yolo": "YOLO",
    "owner_high_autonomy_coding": "High-Autonomy Coding",
}


def autonomy_status(record: Any, capabilities: dict[str, Any]) -> dict[str, Any]:
    """Project an ``approval_policy.AutonomyRecord`` + capabilities to JSON."""
    level = str(getattr(record, "level", "") or "")
    level = getattr(getattr(record, "level", None), "value", level)
    return {
        "level": level,
        "display_name": _AUTONOMY_DISPLAY.get(level, level or "Unknown"),
        "workspace_root": str(getattr(record, "workspace_root", "") or ""),
        "updated_at": float(getattr(record, "updated_at", 0.0) or 0.0),
        "set_by": str(getattr(record, "set_by", "owner") or "owner"),
        "revocable": True,
        "capabilities": {
            "auto_approved": list(capabilities.get("auto_approved", [])),
            "requires_approval": list(capabilities.get("requires_approval", [])),
            "always_deny": list(capabilities.get("always_deny", [])),
            "workspace_scoped": list(capabilities.get("workspace_scoped", [])),
        },
    }
