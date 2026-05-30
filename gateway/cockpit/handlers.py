"""Cockpit route handlers — each backed by a real Hermes subsystem.

Handlers are pure functions of a :class:`Request` returning a
:class:`JsonResponse` (buffered JSON) or, for chat, a stream generator.
Every handler is defensive: a missing optional subsystem degrades to an
honest empty/typed response (never a crash, never fake data).

Stdlib-only at import time; subsystems are imported lazily inside each
handler so the module loads under Termux / slim installs.
"""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Request / response model
# ---------------------------------------------------------------------------


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    path_params: dict[str, str] = field(default_factory=dict)


@dataclass
class JsonResponse:
    status: int
    payload: dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Health + runtime
# ---------------------------------------------------------------------------

COCKPIT_API_VERSION = "1.0.0"


def health(_req: Request) -> JsonResponse:
    """Unauthenticated liveness + version probe (contract §2)."""
    version = _gateway_version()
    return JsonResponse(
        200,
        {
            "ok": True,
            "service": "hermes-cockpit",
            "api_version": COCKPIT_API_VERSION,
            "gateway_version": version,
            "time": _now_iso(),
        },
    )


def runtime_status(_req: Request) -> JsonResponse:
    """Real runtime status: gateway, host, and live queue snapshot."""
    return JsonResponse(
        200,
        {
            "gateway": {
                "version": _gateway_version(),
                "started_at": _process_start_iso(),
                "pid": _safe(lambda: __import__("os").getpid()),
                "mode": "local",
            },
            "host": {
                "platform": platform.system() or "unknown",
                "arch": platform.machine() or "unknown",
                "hostname": _safe(socket.gethostname) or "unknown",
            },
            "queue": _queue_snapshot(),
        },
    )


def runtime_workers(_req: Request) -> JsonResponse:
    """Detected worker lanes (Claude Code / Codex) — detection only, no keys."""
    workers: list[dict[str, Any]] = []
    try:
        from hermes_cli.jarvis_prime import worker_registry as wr

        for status in wr.detect_lanes():
            workers.append({
                "id": status.lane.id,
                "display_name": status.lane.display_name,
                "kind": status.lane.role,
                "available": status.available,
                "version": status.version,
                "path": status.path,
                "notes": status.detail or None,
            })
    except Exception:  # pragma: no cover - defensive
        pass
    return JsonResponse(200, {"workers": workers})


# ---------------------------------------------------------------------------
# Diagnostics + models
# ---------------------------------------------------------------------------


def diagnostics(_req: Request) -> JsonResponse:
    """Launch-readiness diagnostics (reuses the JARVIS launch doctor)."""
    try:
        from hermes_cli.jarvis_prime.launch_doctor import run_launch_doctor

        report = run_launch_doctor()
        payload = report.to_dict()
    except Exception as exc:  # pragma: no cover - defensive
        payload = {"ok": False, "checks": [], "error": str(exc)}
    payload["generated_at"] = _now_iso()
    return JsonResponse(200, payload)


def models(_req: Request) -> JsonResponse:
    """Read-only model policy (free-first routing). Never accepts API keys."""
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        policy = mb.load_policy()
        if policy is None:
            result = mb.bootstrap(dry_run=True, record_memory=False)
            policy = result.config
            policy["_note"] = "policy not yet written; this is a dry-run preview"
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"routes": {}, "error": str(exc)})
    return JsonResponse(200, policy)


# ---------------------------------------------------------------------------
# Memory (real JARVIS memory store; secret-rejection preserved)
# ---------------------------------------------------------------------------


def memory_list(req: Request) -> JsonResponse:
    query = req.query.get("q") or req.query.get("query")
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore

        store = MemoryStore()
        if query:
            records = store.recollect(query, limit=int(req.query.get("limit", "50")))
        else:
            records = list(store.durable) + list(store.session)
        items = [r.to_dict() for r in records]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"items": [], "error": str(exc)})
    return JsonResponse(200, {"items": items})


def memory_create(req: Request) -> JsonResponse:
    key = str(req.body.get("key", "")).strip()
    value = str(req.body.get("value", "")).strip()
    if not key or not value:
        return JsonResponse(400, {"error": "key and value are required"})
    durability = str(req.body.get("durability", "session"))
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore

        store = MemoryStore()
        record = store.remember(
            key=key,
            value=value,
            durability=durability
            if durability in ("session", "durable")
            else "session",
            source="cockpit",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if record is None:
        # Rejected (secret-like or below confidence floor) — honest, not fake.
        return JsonResponse(
            422, {"stored": False, "reason": "rejected (secret-like or low confidence)"}
        )
    return JsonResponse(201, {"stored": True, "item": record.to_dict()})


def memory_delete(req: Request) -> JsonResponse:
    key = req.path_params.get("id") or str(req.body.get("key", ""))
    if not key:
        return JsonResponse(400, {"error": "memory key required"})
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore

        removed = MemoryStore().forget(key)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, {"removed": removed})


# ---------------------------------------------------------------------------
# Audit (decision ledger) + tasks (job queue)
# ---------------------------------------------------------------------------


def audit_events(req: Request) -> JsonResponse:
    limit = int(req.query.get("limit", "100"))
    events: list[dict[str, Any]] = []
    try:
        from hermes_cli import decision_ledger as dl

        for path in dl.list_ledgers()[:limit]:
            try:
                ledger = dl.read_ledger(path)
                events.append(_ledger_summary(ledger, path))
            except Exception:
                continue
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"events": [], "error": str(exc)})
    return JsonResponse(200, {"events": events})


def jobs_list(_req: Request) -> JsonResponse:
    jobs: list[dict[str, Any]] = []
    try:
        from hermes_cli.job_queue import JobQueue

        queue = JobQueue()
        for entry in queue.list_jobs():
            jobs.append(_job_summary(entry))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"jobs": [], "error": str(exc)})
    return JsonResponse(200, {"jobs": jobs})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe(fn):
    try:
        return fn()
    except Exception:  # pragma: no cover - defensive
        return None


def _gateway_version() -> str:
    try:
        from hermes_cli import __version__ as v  # type: ignore

        return str(v)
    except Exception:
        pass
    try:
        from hermes_cli.jarvis_prime import __version__ as v  # type: ignore

        return str(v)
    except Exception:
        return "unknown"


_PROC_START = _now_iso()


def _process_start_iso() -> str:
    return _PROC_START


def _queue_snapshot() -> dict[str, int]:
    snap = {"running": 0, "queued": 0, "waiting_approval": 0}
    try:
        from hermes_cli.job_queue import JobQueue

        queue = JobQueue()
        for entry in queue.list_jobs():
            status = str(getattr(entry, "status", "")).lower()
            if "run" in status:
                snap["running"] += 1
            elif "queue" in status or "pending" in status:
                snap["queued"] += 1
            elif "approval" in status or "wait" in status:
                snap["waiting_approval"] += 1
    except Exception:  # pragma: no cover - defensive
        pass
    return snap


def _job_summary(entry: Any) -> dict[str, Any]:
    to_dict = getattr(entry, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            pass
    return {
        "id": str(getattr(entry, "id", "")),
        "title": str(getattr(entry, "title", getattr(entry, "goal", ""))),
        "status": str(getattr(entry, "status", "unknown")),
    }


def _ledger_summary(ledger: Any, path: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(ledger, "id", "") or path),
        "title": str(getattr(ledger, "title", "") or ""),
        "type": "decision",
        "status": str(getattr(ledger, "status", "") or ""),
        "source": str(path),
        "timestamp": str(getattr(ledger, "created_at", "") or ""),
    }


__all__ = [
    "COCKPIT_API_VERSION",
    "JsonResponse",
    "Request",
    "audit_events",
    "diagnostics",
    "health",
    "jobs_list",
    "memory_create",
    "memory_delete",
    "memory_list",
    "models",
    "runtime_status",
    "runtime_workers",
]
