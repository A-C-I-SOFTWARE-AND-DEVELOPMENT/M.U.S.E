"""Operational monitoring for Hermes jobs, workers, and validation.

``MonitoringHub`` is the read-mostly companion to
``muse_cli.validation``: validation tells you *whether the change
is safe to publish*; monitoring tells you *what is happening right
now* across the local + remote runtime.

The hub is intentionally append-only and filesystem-native:

* Every observation is recorded as one JSON line in
  ``<workspace>/monitoring/events.jsonl``.
* The current snapshot is rolled up into
  ``<workspace>/monitoring/health.json`` on every
  ``snapshot()``.
* Nothing in this module talks to the network or spawns subprocesses
  on its own. The hub watches what the orchestrator, workers, and
  tunnel daemons have *already* written to disk and aggregates it.

Five signal sources feed the hub:

1. ``jobs/<id>/job.json``           — local job state
2. ``workers/<id>/status.json``     — local worker heartbeats
3. ``remote/tunnel.json``           — remote tunnel state
4. ``remote/workers/<id>/heartbeat.json`` — remote worker heartbeats
5. ``remote/queue.json``            — pending job queue
6. ``validation/results.json``      — last validation pass
7. ``health/app.json``              — optional app/backend health
                                      probe written by the gateway

Each source contributes one or more entries to the snapshot. Missing
sources never crash the hub — they just get marked ``unknown`` so
the dashboard can render them honestly.

The hub does NOT decide whether to alert; it just produces an
``MonitoringSnapshot.alerts`` list which the gateway / CLI may
choose to surface.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any


# A clock returns the current unix timestamp as a float. Hub callers
# inject a fixed-time clock in tests so snapshot output is
# deterministic.
Clock = Callable[[], float]


# ── Constants ──────────────────────────────────────────────────────────────

EVENTS_FILENAME = "events.jsonl"
HEALTH_FILENAME = "health.json"
MONITORING_DIRNAME = "monitoring"

# Per-source defaults. Mirror the validation module's remote freshness
# thresholds so the two stay in lockstep — operators expect "warn"
# windows to agree.
LOCAL_WORKER_STALE_S = 5 * 60
REMOTE_WORKER_STALE_S = 5 * 60
JOB_STALL_S = 30 * 60

# Severity levels used in alerts. ``info`` is for "the dashboard
# should mention this", ``warn`` is "the user should look soon",
# ``error`` is "something is actively broken". Anything more
# escalation-heavy belongs in the gateway, not here.
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_ERROR = "error"

# Event kinds. Keeping them as constants avoids drift between
# producers and consumers — the gateway and tests refer back to these
# rather than typing string literals.
EVENT_JOB_STATE = "job.state"
EVENT_WORKER_HEARTBEAT = "worker.heartbeat"
EVENT_REMOTE_TUNNEL = "remote.tunnel"
EVENT_REMOTE_WORKER = "remote.worker"
EVENT_REMOTE_QUEUE = "remote.queue"
EVENT_VALIDATION = "validation.result"
EVENT_APP_HEALTH = "app.health"
EVENT_ALERT = "alert"


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclasses.dataclass
class MonitoringEvent:
    """One observation recorded to ``events.jsonl``.

    ``kind`` is one of the ``EVENT_*`` constants. ``source`` is the
    path the observation came from (relative to the workspace, for
    portability). ``payload`` is opaque to the hub — consumers
    interpret it based on ``kind``.
    """

    timestamp: float
    kind: str
    source: str
    payload: dict[str, Any]
    severity: str = SEVERITY_INFO

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class MonitoringSnapshot:
    """Aggregate health snapshot produced by ``MonitoringHub.snapshot()``."""

    workspace: str
    generated_at: float
    jobs: dict[str, Any]
    local_workers: dict[str, Any]
    remote_tunnel: dict[str, Any]
    remote_workers: dict[str, Any]
    remote_queue: dict[str, Any]
    validation: dict[str, Any]
    app_health: dict[str, Any]
    alerts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ── Hub ────────────────────────────────────────────────────────────────────


class MonitoringHub:
    """Aggregate read-only health signals for a Hermes workspace.

    Two public entry points:

    * ``record(event)`` — append a single ``MonitoringEvent`` to the
      ``events.jsonl`` log. Producers (orchestrator, workers, gateway)
      call this when something interesting happens. The hub itself
      also calls it during ``snapshot()`` so each refresh leaves an
      audit trail.
    * ``snapshot()`` — scan the workspace, build a
      ``MonitoringSnapshot``, write ``health.json``, and return the
      snapshot.

    Construction is cheap. The hub is intentionally not threadsafe:
    spin up one per workspace.
    """

    def __init__(
        self,
        workspace: str | os.PathLike[str],
        *,
        output_dir: str | os.PathLike[str] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.output_dir = (
            Path(output_dir).resolve()
            if output_dir
            else self.workspace / MONITORING_DIRNAME
        )
        self._clock = clock or _wall_clock

    # — Event log ──────────────────────────────────────────────────────────

    def record(self, event: MonitoringEvent) -> None:
        """Append ``event`` as one JSON line to ``events.jsonl``."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        events_path = self.output_dir / EVENTS_FILENAME
        # Emit the payload and the trailing newline as a single
        # ``write()`` call so concurrent producers on an O_APPEND file
        # cannot interleave bytes mid-record. JSON is serialised
        # compactly to keep one observation per line.
        line = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def read_events(self, limit: int | None = None) -> list[MonitoringEvent]:
        """Return events from ``events.jsonl``, newest last."""
        events_path = self.output_dir / EVENTS_FILENAME
        if not events_path.exists():
            return []
        out: list[MonitoringEvent] = []
        for raw in events_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            try:
                out.append(
                    MonitoringEvent(
                        timestamp=float(data.get("timestamp") or 0),
                        kind=str(data.get("kind") or ""),
                        source=str(data.get("source") or ""),
                        payload=data.get("payload") or {},
                        severity=str(data.get("severity") or SEVERITY_INFO),
                    )
                )
            except (TypeError, ValueError):
                continue
        if limit is not None and len(out) > limit:
            return out[-limit:]
        return out

    # — Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> MonitoringSnapshot:
        """Scan the workspace and build a fresh health snapshot."""
        now = self._clock()
        jobs = self._scan_jobs(now)
        local_workers = self._scan_local_workers(now)
        remote_tunnel = self._scan_remote_tunnel()
        remote_workers = self._scan_remote_workers(now)
        remote_queue = self._scan_remote_queue(now)
        validation = self._scan_validation()
        app_health = self._scan_app_health(now)

        alerts: list[dict[str, Any]] = []
        alerts.extend(_alerts_for_jobs(jobs))
        alerts.extend(_alerts_for_workers(local_workers, scope="local"))
        alerts.extend(_alerts_for_workers(remote_workers, scope="remote"))
        alerts.extend(_alerts_for_tunnel(remote_tunnel))
        alerts.extend(_alerts_for_queue(remote_queue))
        alerts.extend(_alerts_for_validation(validation))
        alerts.extend(_alerts_for_app_health(app_health))

        snap = MonitoringSnapshot(
            workspace=str(self.workspace),
            generated_at=now,
            jobs=jobs,
            local_workers=local_workers,
            remote_tunnel=remote_tunnel,
            remote_workers=remote_workers,
            remote_queue=remote_queue,
            validation=validation,
            app_health=app_health,
            alerts=alerts,
        )
        self._write_snapshot(snap)
        # Record a single rollup event so the jsonl is the canonical
        # audit log of every snapshot, not just operator-issued events.
        self.record(
            MonitoringEvent(
                timestamp=now,
                kind=EVENT_ALERT,
                source=MONITORING_DIRNAME,
                payload={
                    "alert_count": len(alerts),
                    "max_severity": _max_severity(alerts),
                    "jobs_total": jobs.get("total", 0),
                    "queue_depth": remote_queue.get("depth"),
                },
                severity=_max_severity(alerts) or SEVERITY_INFO,
            )
        )
        return snap

    # — Source scanners ────────────────────────────────────────────────────

    def _scan_jobs(self, now: float) -> dict[str, Any]:
        jobs_root = self.workspace / "jobs"
        result: dict[str, Any] = {
            "total": 0,
            "by_status": {},
            "failed": [],
            "stalled": [],
            "recent": [],
        }
        if not jobs_root.is_dir():
            return result
        recent: list[dict[str, Any]] = []
        for job_dir in sorted(p for p in jobs_root.iterdir() if p.is_dir()):
            job_json = job_dir / "job.json"
            if not job_json.exists():
                continue
            try:
                data = json.loads(job_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            result["total"] += 1
            status = str(data.get("status") or "unknown")
            result["by_status"][status] = result["by_status"].get(status, 0) + 1
            if status in {"failed", "error"}:
                result["failed"].append(
                    {"id": data.get("id"), "status": status, "path": job_dir.name}
                )
            updated_at = _coerce_float(
                data.get("updated_at") or data.get("started_at")
            )
            if (
                status in {"running", "in_progress"}
                and updated_at is not None
                and now - updated_at > JOB_STALL_S
            ):
                result["stalled"].append(
                    {
                        "id": data.get("id"),
                        "status": status,
                        "stalled_for_s": int(now - updated_at),
                    }
                )
            recent.append(
                {
                    "id": data.get("id"),
                    "status": status,
                    "updated_at": updated_at,
                    "path": job_dir.name,
                }
            )
        # Newest jobs first when sorting by ``updated_at`` (None last).
        recent.sort(key=lambda j: j.get("updated_at") or 0, reverse=True)
        result["recent"] = recent[:10]
        return result

    def _scan_local_workers(self, now: float) -> dict[str, Any]:
        workers_root = self.workspace / "workers"
        return _scan_heartbeat_dir(
            workers_root,
            now=now,
            stale_after_s=LOCAL_WORKER_STALE_S,
            heartbeat_filename="status.json",
            timestamp_keys=("heartbeat", "updated_at", "timestamp"),
            workspace_root=self.workspace,
        )

    def _scan_remote_tunnel(self) -> dict[str, Any]:
        path = self.workspace / "remote" / "tunnel.json"
        if not path.exists():
            return {"state": "unknown", "present": False}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"state": "error", "present": True, "error": str(exc)}
        if not isinstance(data, dict):
            return {"state": "error", "present": True, "error": "not an object"}
        state = str(data.get("state") or data.get("status") or "unknown").lower()
        return {
            "state": state,
            "url": data.get("url") or data.get("public_url"),
            "present": True,
            "raw": {k: v for k, v in data.items() if k not in {"state", "status"}},
        }

    def _scan_remote_workers(self, now: float) -> dict[str, Any]:
        workers_root = self.workspace / "remote" / "workers"
        return _scan_heartbeat_dir(
            workers_root,
            now=now,
            stale_after_s=REMOTE_WORKER_STALE_S,
            heartbeat_filename="heartbeat.json",
            timestamp_keys=("timestamp", "heartbeat", "updated_at"),
            workspace_root=self.workspace,
        )

    def _scan_remote_queue(self, now: float) -> dict[str, Any]:
        path = self.workspace / "remote" / "queue.json"
        if not path.exists():
            return {"present": False, "depth": 0}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"present": True, "error": str(exc), "depth": 0}
        if isinstance(data, list):
            jobs = data
            extra: dict[str, Any] = {}
        elif isinstance(data, dict):
            raw = data.get("jobs", [])
            if not isinstance(raw, list):
                return {
                    "present": True,
                    "error": f"`jobs` must be a list, got {type(raw).__name__}",
                    "depth": 0,
                }
            jobs = raw
            extra = {k: v for k, v in data.items() if k != "jobs"}
        else:
            return {"present": True, "error": "not list/object", "depth": 0}
        oldest_age: float | None = None
        for job in jobs:
            if not isinstance(job, dict):
                continue
            ts = _coerce_float(job.get("enqueued_at") or job.get("created_at"))
            if ts is None:
                continue
            age = now - ts
            if oldest_age is None or age > oldest_age:
                oldest_age = age
        return {
            "present": True,
            "depth": len(jobs),
            "oldest_age_s": int(oldest_age) if oldest_age is not None else None,
            **extra,
        }

    def _scan_validation(self) -> dict[str, Any]:
        path = self.workspace / "validation" / "results.json"
        if not path.exists():
            return {"present": False}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"present": True, "error": str(exc)}
        if not isinstance(data, dict):
            return {"present": True, "error": "not an object"}
        checks = data.get("checks") or []
        counts: dict[str, int] = {}
        for c in checks:
            if not isinstance(c, dict):
                continue
            counts[c.get("status", "unknown")] = (
                counts.get(c.get("status", "unknown"), 0) + 1
            )
        return {
            "present": True,
            "publish_allowed": bool(data.get("publish_allowed")),
            "blocking_failures": list(data.get("blocking_failures") or []),
            "duration_ms": data.get("duration_ms"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "status_counts": counts,
            "total_checks": len(checks),
        }

    def _scan_app_health(self, now: float) -> dict[str, Any]:
        path = self.workspace / "health" / "app.json"
        if not path.exists():
            return {"present": False, "state": "unknown"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"present": True, "state": "error", "error": str(exc)}
        if not isinstance(data, dict):
            return {"present": True, "state": "error", "error": "not an object"}
        state = str(data.get("state") or data.get("status") or "unknown").lower()
        ts = _coerce_float(data.get("checked_at") or data.get("timestamp"))
        age = (now - ts) if ts is not None else None
        return {
            "present": True,
            "state": state,
            "checked_at": ts,
            "age_s": int(age) if age is not None else None,
            "components": data.get("components"),
            "raw": {
                k: v
                for k, v in data.items()
                if k not in {"state", "status", "checked_at", "timestamp"}
            },
        }

    # — Output ─────────────────────────────────────────────────────────────

    def _write_snapshot(self, snapshot: MonitoringSnapshot) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / HEALTH_FILENAME
        path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )


# ── Heartbeat-directory helpers ────────────────────────────────────────────


def _scan_heartbeat_dir(
    root: Path,
    *,
    now: float,
    stale_after_s: float,
    heartbeat_filename: str,
    timestamp_keys: Sequence[str],
    workspace_root: Path,
) -> dict[str, Any]:
    """Scan ``root`` for per-worker heartbeat files.

    Returns a uniform structure regardless of whether the directory
    exists, has zero entries, or has a mix of fresh / stale workers.
    """
    if not root.is_dir():
        return {
            "present": False,
            "fresh": 0,
            "stale": [],
            "workers": [],
            "threshold_s": stale_after_s,
        }
    heartbeat_files = sorted(root.rglob(heartbeat_filename))
    if not heartbeat_files:
        return {
            "present": True,
            "fresh": 0,
            "stale": [],
            "workers": [],
            "threshold_s": stale_after_s,
        }
    workers: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    fresh = 0
    for hb in heartbeat_files:
        rel = str(hb.relative_to(workspace_root))
        try:
            data = json.loads(hb.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entry = {"path": rel, "error": str(exc), "fresh": False}
            workers.append(entry)
            stale.append(entry)
            continue
        if not isinstance(data, dict):
            entry = {
                "path": rel,
                "error": f"heartbeat must be a JSON object, got {type(data).__name__}",
                "fresh": False,
            }
            workers.append(entry)
            stale.append(entry)
            continue
        ts: float | None = None
        for key in timestamp_keys:
            if key in data:
                ts = _coerce_float(data.get(key))
                if ts is not None:
                    break
        age = (now - ts) if ts is not None else None
        is_fresh = age is not None and age <= stale_after_s
        worker_id = (
            data.get("id")
            or data.get("worker_id")
            or hb.parent.name
        )
        entry = {
            "path": rel,
            "id": worker_id,
            "state": data.get("state") or data.get("status"),
            "age_s": int(age) if age is not None else None,
            "fresh": bool(is_fresh),
        }
        workers.append(entry)
        if is_fresh:
            fresh += 1
        else:
            stale.append(entry)
    return {
        "present": True,
        "fresh": fresh,
        "stale": stale,
        "workers": workers,
        "threshold_s": stale_after_s,
    }


# ── Alert builders ─────────────────────────────────────────────────────────


def _alerts_for_jobs(jobs: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for job in jobs.get("failed", []):
        out.append(
            {
                "severity": SEVERITY_ERROR,
                "source": "jobs",
                "message": f"job {job.get('id')} failed",
                "detail": job,
            }
        )
    for job in jobs.get("stalled", []):
        out.append(
            {
                "severity": SEVERITY_WARN,
                "source": "jobs",
                "message": f"job {job.get('id')} stalled for {job.get('stalled_for_s')}s",
                "detail": job,
            }
        )
    return out


def _alerts_for_workers(workers: dict[str, Any], *, scope: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in workers.get("stale", []):
        out.append(
            {
                "severity": SEVERITY_WARN,
                "source": f"{scope}_workers",
                "message": f"{scope} worker stale: {entry.get('id') or entry.get('path')}",
                "detail": entry,
            }
        )
    return out


def _alerts_for_tunnel(tunnel: dict[str, Any]) -> list[dict[str, Any]]:
    if not tunnel.get("present"):
        return []
    state = tunnel.get("state")
    if state in {"down", "closed", "error", "failed"}:
        return [
            {
                "severity": SEVERITY_ERROR,
                "source": "remote_tunnel",
                "message": f"tunnel state: {state}",
                "detail": tunnel,
            }
        ]
    if state in {"up", "open", "healthy", "connected", "ready"}:
        return []
    return [
        {
            "severity": SEVERITY_WARN,
            "source": "remote_tunnel",
            "message": f"tunnel state unknown: {state}",
            "detail": tunnel,
        }
    ]


def _alerts_for_queue(queue: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if queue.get("error"):
        out.append(
            {
                "severity": SEVERITY_ERROR,
                "source": "remote_queue",
                "message": f"queue parse error: {queue['error']}",
                "detail": queue,
            }
        )
        return out
    oldest = queue.get("oldest_age_s")
    if oldest is not None and oldest > 30 * 60:
        out.append(
            {
                "severity": SEVERITY_WARN,
                "source": "remote_queue",
                "message": f"queue head age {oldest}s exceeds 30m",
                "detail": queue,
            }
        )
    return out


def _alerts_for_validation(validation: dict[str, Any]) -> list[dict[str, Any]]:
    if not validation.get("present"):
        return []
    if validation.get("error"):
        # The results.json is corrupt or unreadable — surface that as
        # the failure, don't misattribute it to a blocked publish gate.
        return [
            {
                "severity": SEVERITY_ERROR,
                "source": "validation",
                "message": f"validation artifact unreadable: {validation['error']}",
                "detail": {"error": validation["error"]},
            }
        ]
    if validation.get("publish_allowed"):
        return []
    failures = validation.get("blocking_failures") or []
    return [
        {
            "severity": SEVERITY_ERROR,
            "source": "validation",
            "message": "publish gate blocked",
            "detail": {"blocking_failures": failures},
        }
    ]


def _alerts_for_app_health(app_health: dict[str, Any]) -> list[dict[str, Any]]:
    if not app_health.get("present"):
        return []
    state = app_health.get("state")
    if state in {"down", "error", "unhealthy", "failed"}:
        return [
            {
                "severity": SEVERITY_ERROR,
                "source": "app_health",
                "message": f"app health: {state}",
                "detail": app_health,
            }
        ]
    if state in {"degraded", "warning"}:
        return [
            {
                "severity": SEVERITY_WARN,
                "source": "app_health",
                "message": f"app health: {state}",
                "detail": app_health,
            }
        ]
    return []


# ── Internals ──────────────────────────────────────────────────────────────


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_severity(alerts: Iterable[dict[str, Any]]) -> str | None:
    rank = {SEVERITY_INFO: 0, SEVERITY_WARN: 1, SEVERITY_ERROR: 2}
    best: str | None = None
    best_rank = -1
    for a in alerts:
        sev = a.get("severity")
        if sev in rank and rank[sev] > best_rank:
            best = sev
            best_rank = rank[sev]
    return best


def _wall_clock() -> float:
    return time.time()


__all__ = [
    "EVENT_ALERT",
    "EVENT_APP_HEALTH",
    "EVENT_JOB_STATE",
    "EVENT_REMOTE_QUEUE",
    "EVENT_REMOTE_TUNNEL",
    "EVENT_REMOTE_WORKER",
    "EVENT_VALIDATION",
    "EVENT_WORKER_HEARTBEAT",
    "EVENTS_FILENAME",
    "HEALTH_FILENAME",
    "JOB_STALL_S",
    "LOCAL_WORKER_STALE_S",
    "MONITORING_DIRNAME",
    "MonitoringEvent",
    "MonitoringHub",
    "MonitoringSnapshot",
    "REMOTE_WORKER_STALE_S",
    "SEVERITY_ERROR",
    "SEVERITY_INFO",
    "SEVERITY_WARN",
]
