"""Tests for ``muse_cli.monitoring``.

The hub is read-mostly: it scans a workspace, builds a snapshot, and
appends to a JSONL log. These tests pin each source scanner in
isolation (so the failure mode reads as "remote tunnel scanner
broke" rather than "snapshot is wrong somewhere") and add end-to-end
assertions on the artefact shape.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from muse_cli.monitoring import (
    EVENT_ALERT,
    EVENT_JOB_STATE,
    HEALTH_FILENAME,
    JOB_STALL_S,
    LOCAL_WORKER_STALE_S,
    REMOTE_WORKER_STALE_S,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARN,
    MonitoringEvent,
    MonitoringHub,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_hub(tmp_path: Path, *, now: float | None = None) -> MonitoringHub:
    if now is None:
        return MonitoringHub(tmp_path)
    return MonitoringHub(tmp_path, clock=lambda: now)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ── Event log ──────────────────────────────────────────────────────────────


class TestEventLog:
    def test_record_appends_one_line_per_event(self, tmp_path: Path) -> None:
        hub = _make_hub(tmp_path)
        hub.record(
            MonitoringEvent(
                timestamp=1.0,
                kind=EVENT_JOB_STATE,
                source="jobs/a/job.json",
                payload={"status": "queued"},
            )
        )
        hub.record(
            MonitoringEvent(
                timestamp=2.0,
                kind=EVENT_JOB_STATE,
                source="jobs/b/job.json",
                payload={"status": "running"},
                severity=SEVERITY_INFO,
            )
        )
        events_path = tmp_path / "monitoring" / "events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["kind"] == EVENT_JOB_STATE
        assert first["payload"] == {"status": "queued"}

    def test_read_events_round_trips(self, tmp_path: Path) -> None:
        hub = _make_hub(tmp_path)
        for i in range(3):
            hub.record(
                MonitoringEvent(
                    timestamp=float(i),
                    kind=EVENT_JOB_STATE,
                    source=f"jobs/{i}",
                    payload={"i": i},
                )
            )
        events = hub.read_events()
        assert [e.timestamp for e in events] == [0.0, 1.0, 2.0]
        assert [e.payload["i"] for e in events] == [0, 1, 2]

    def test_read_events_limit(self, tmp_path: Path) -> None:
        hub = _make_hub(tmp_path)
        for i in range(5):
            hub.record(
                MonitoringEvent(
                    timestamp=float(i),
                    kind=EVENT_JOB_STATE,
                    source="x",
                    payload={},
                )
            )
        last_two = hub.read_events(limit=2)
        assert [e.timestamp for e in last_two] == [3.0, 4.0]

    def test_read_events_ignores_malformed_lines(self, tmp_path: Path) -> None:
        events_path = tmp_path / "monitoring" / "events.jsonl"
        events_path.parent.mkdir(parents=True)
        events_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": 1.0,
                            "kind": "job.state",
                            "source": "x",
                            "payload": {},
                            "severity": "info",
                        }
                    ),
                    "not valid json",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        hub = _make_hub(tmp_path)
        events = hub.read_events()
        assert len(events) == 1
        assert events[0].kind == "job.state"


# ── Job scanning ───────────────────────────────────────────────────────────


class TestJobScan:
    def test_no_jobs_dir_returns_empty_totals(self, tmp_path: Path) -> None:
        snap = _make_hub(tmp_path).snapshot()
        assert snap.jobs["total"] == 0
        assert snap.jobs["failed"] == []

    def test_counts_jobs_by_status(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "jobs" / "a" / "job.json",
            {"id": "a", "status": "running"},
        )
        _write_json(
            tmp_path / "jobs" / "b" / "job.json",
            {"id": "b", "status": "failed"},
        )
        _write_json(
            tmp_path / "jobs" / "c" / "job.json",
            {"id": "c", "status": "done"},
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.jobs["total"] == 3
        assert snap.jobs["by_status"]["running"] == 1
        assert snap.jobs["by_status"]["failed"] == 1
        assert snap.jobs["by_status"]["done"] == 1
        failed_ids = [j["id"] for j in snap.jobs["failed"]]
        assert failed_ids == ["b"]

    def test_stalled_running_job_flagged(self, tmp_path: Path) -> None:
        now = 10_000.0
        long_ago = now - JOB_STALL_S - 60
        _write_json(
            tmp_path / "jobs" / "z" / "job.json",
            {"id": "z", "status": "running", "updated_at": long_ago},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        stalled = snap.jobs["stalled"]
        assert len(stalled) == 1
        assert stalled[0]["id"] == "z"
        assert stalled[0]["stalled_for_s"] >= JOB_STALL_S

    def test_malformed_job_json_skipped(self, tmp_path: Path) -> None:
        bad = tmp_path / "jobs" / "bad"
        bad.mkdir(parents=True)
        (bad / "job.json").write_text("{not json", encoding="utf-8")
        snap = _make_hub(tmp_path).snapshot()
        # Malformed jobs don't count and don't crash.
        assert snap.jobs["total"] == 0


# ── Local + remote worker scanning ─────────────────────────────────────────


class TestWorkerScan:
    def test_local_worker_fresh(self, tmp_path: Path) -> None:
        now = 10_000.0
        _write_json(
            tmp_path / "workers" / "w-1" / "status.json",
            {"heartbeat": now - 10, "state": "idle"},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        assert snap.local_workers["fresh"] == 1
        assert snap.local_workers["stale"] == []

    def test_local_worker_stale(self, tmp_path: Path) -> None:
        now = 10_000.0
        _write_json(
            tmp_path / "workers" / "w-old" / "status.json",
            {"heartbeat": now - LOCAL_WORKER_STALE_S - 1, "state": "lost"},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        assert snap.local_workers["fresh"] == 0
        assert len(snap.local_workers["stale"]) == 1

    def test_remote_worker_fresh(self, tmp_path: Path) -> None:
        now = 10_000.0
        _write_json(
            tmp_path / "remote" / "workers" / "rw-1" / "heartbeat.json",
            {"timestamp": now - 10, "state": "running"},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        assert snap.remote_workers["fresh"] == 1

    def test_remote_worker_stale_creates_alert(self, tmp_path: Path) -> None:
        now = 10_000.0
        _write_json(
            tmp_path / "remote" / "workers" / "rw-old" / "heartbeat.json",
            {"timestamp": now - REMOTE_WORKER_STALE_S - 1},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        warn_alerts = [a for a in snap.alerts if a["severity"] == SEVERITY_WARN]
        assert any("remote_workers" == a["source"] for a in warn_alerts)

    def test_non_object_heartbeat_does_not_crash(self, tmp_path: Path) -> None:
        # A list / null parses but isn't a dict — must degrade to
        # stale instead of raising AttributeError.
        _write_json(
            tmp_path / "remote" / "workers" / "rw" / "heartbeat.json",
            [],
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.remote_workers["fresh"] == 0
        assert len(snap.remote_workers["stale"]) == 1
        assert "object" in snap.remote_workers["stale"][0]["error"]


# ── Remote tunnel scanning ─────────────────────────────────────────────────


class TestTunnelScan:
    def test_no_tunnel_file(self, tmp_path: Path) -> None:
        snap = _make_hub(tmp_path).snapshot()
        assert snap.remote_tunnel["state"] == "unknown"
        assert snap.remote_tunnel["present"] is False

    def test_up_state(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "remote" / "tunnel.json",
            {"state": "up", "url": "https://x.example"},
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.remote_tunnel["state"] == "up"
        assert snap.remote_tunnel["url"] == "https://x.example"
        # ``up`` is healthy → no alert.
        assert not any(a["source"] == "remote_tunnel" for a in snap.alerts)

    def test_down_state_alerts_error(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "remote" / "tunnel.json",
            {"state": "down"},
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.remote_tunnel["state"] == "down"
        errors = [a for a in snap.alerts if a["source"] == "remote_tunnel"]
        assert len(errors) == 1
        assert errors[0]["severity"] == SEVERITY_ERROR

    def test_unknown_state_alerts_warn(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "remote" / "tunnel.json",
            {"state": "transitioning"},
        )
        snap = _make_hub(tmp_path).snapshot()
        alerts = [a for a in snap.alerts if a["source"] == "remote_tunnel"]
        assert len(alerts) == 1
        assert alerts[0]["severity"] == SEVERITY_WARN


# ── Queue scanning ─────────────────────────────────────────────────────────


class TestQueueScan:
    def test_no_queue_file(self, tmp_path: Path) -> None:
        snap = _make_hub(tmp_path).snapshot()
        assert snap.remote_queue["present"] is False
        assert snap.remote_queue["depth"] == 0

    def test_object_with_jobs(self, tmp_path: Path) -> None:
        now = 10_000.0
        _write_json(
            tmp_path / "remote" / "queue.json",
            {"jobs": [{"id": "a", "enqueued_at": now}]},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        assert snap.remote_queue["depth"] == 1

    def test_bare_list(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "remote" / "queue.json",
            [{"id": "a"}, {"id": "b"}],
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.remote_queue["depth"] == 2

    def test_old_head_alerts(self, tmp_path: Path) -> None:
        now = 10_000.0
        old = now - 60 * 60  # 1 hour stale
        _write_json(
            tmp_path / "remote" / "queue.json",
            {"jobs": [{"id": "stuck", "enqueued_at": old}]},
        )
        snap = _make_hub(tmp_path, now=now).snapshot()
        warn = [a for a in snap.alerts if a["source"] == "remote_queue"]
        assert warn and warn[0]["severity"] == SEVERITY_WARN

    def test_malformed_queue_errors(self, tmp_path: Path) -> None:
        path = tmp_path / "remote" / "queue.json"
        path.parent.mkdir(parents=True)
        path.write_text("{nope", encoding="utf-8")
        snap = _make_hub(tmp_path).snapshot()
        assert "error" in snap.remote_queue
        errors = [a for a in snap.alerts if a["source"] == "remote_queue"]
        assert errors and errors[0]["severity"] == SEVERITY_ERROR

    def test_non_list_jobs_errors(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "remote" / "queue.json",
            {"jobs": {"a": 1}},
        )
        snap = _make_hub(tmp_path).snapshot()
        assert "error" in snap.remote_queue
        assert snap.remote_queue["depth"] == 0
        errors = [a for a in snap.alerts if a["source"] == "remote_queue"]
        assert errors and errors[0]["severity"] == SEVERITY_ERROR


# ── Validation passthrough ─────────────────────────────────────────────────


class TestValidationPassthrough:
    def test_blocked_publish_creates_error_alert(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "validation" / "results.json",
            {
                "workspace": str(tmp_path),
                "publish_allowed": False,
                "blocking_failures": ["python.py_compile"],
                "duration_ms": 12,
                "started_at": 0,
                "finished_at": 1,
                "checks": [
                    {
                        "name": "python.py_compile",
                        "category": "language",
                        "status": "fail",
                        "summary": "syntax err",
                    },
                ],
            },
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.validation["publish_allowed"] is False
        assert "python.py_compile" in snap.validation["blocking_failures"]
        errors = [a for a in snap.alerts if a["source"] == "validation"]
        assert errors and errors[0]["severity"] == SEVERITY_ERROR

    def test_open_gate_no_alert(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "validation" / "results.json",
            {
                "workspace": str(tmp_path),
                "publish_allowed": True,
                "blocking_failures": [],
                "duration_ms": 5,
                "started_at": 0,
                "finished_at": 1,
                "checks": [],
            },
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.validation["publish_allowed"] is True
        assert not any(a["source"] == "validation" for a in snap.alerts)

    def test_corrupt_results_json_reported_as_artifact_error(
        self, tmp_path: Path
    ) -> None:
        # When the results.json itself can't be parsed, the alert
        # should name the corrupt artifact — not pretend the publish
        # gate is blocked.
        path = tmp_path / "validation" / "results.json"
        path.parent.mkdir(parents=True)
        path.write_text("{partial", encoding="utf-8")
        snap = _make_hub(tmp_path).snapshot()
        errors = [a for a in snap.alerts if a["source"] == "validation"]
        assert errors and errors[0]["severity"] == SEVERITY_ERROR
        assert "unreadable" in errors[0]["message"]
        assert "publish gate" not in errors[0]["message"]


# ── App health passthrough ─────────────────────────────────────────────────


class TestAppHealth:
    def test_no_app_file(self, tmp_path: Path) -> None:
        snap = _make_hub(tmp_path).snapshot()
        assert snap.app_health["state"] == "unknown"

    def test_down_state(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "health" / "app.json",
            {"state": "down", "timestamp": time.time()},
        )
        snap = _make_hub(tmp_path).snapshot()
        assert snap.app_health["state"] == "down"
        errs = [a for a in snap.alerts if a["source"] == "app_health"]
        assert errs and errs[0]["severity"] == SEVERITY_ERROR

    def test_degraded_state_warn(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "health" / "app.json",
            {"state": "degraded", "timestamp": time.time()},
        )
        snap = _make_hub(tmp_path).snapshot()
        warns = [a for a in snap.alerts if a["source"] == "app_health"]
        assert warns and warns[0]["severity"] == SEVERITY_WARN


# ── Snapshot artefacts ─────────────────────────────────────────────────────


class TestSnapshotArtefacts:
    def test_health_json_written(self, tmp_path: Path) -> None:
        hub = _make_hub(tmp_path)
        hub.snapshot()
        health_path = tmp_path / "monitoring" / HEALTH_FILENAME
        assert health_path.exists()
        data = json.loads(health_path.read_text(encoding="utf-8"))
        for key in (
            "workspace",
            "generated_at",
            "jobs",
            "local_workers",
            "remote_tunnel",
            "remote_workers",
            "remote_queue",
            "validation",
            "app_health",
            "alerts",
        ):
            assert key in data

    def test_snapshot_records_rollup_event(self, tmp_path: Path) -> None:
        hub = _make_hub(tmp_path)
        hub.snapshot()
        events = hub.read_events()
        # Exactly one rollup event from the snapshot itself.
        rollups = [e for e in events if e.kind == EVENT_ALERT]
        assert len(rollups) == 1
        assert "alert_count" in rollups[0].payload

    def test_snapshot_returns_alerts_for_failures(self, tmp_path: Path) -> None:
        # Stack three problems and check they all surface.
        _write_json(
            tmp_path / "jobs" / "a" / "job.json",
            {"id": "a", "status": "failed"},
        )
        _write_json(
            tmp_path / "remote" / "tunnel.json",
            {"state": "down"},
        )
        _write_json(
            tmp_path / "validation" / "results.json",
            {
                "workspace": str(tmp_path),
                "publish_allowed": False,
                "blocking_failures": ["secrets.staged_diff"],
                "checks": [],
            },
        )
        snap = _make_hub(tmp_path).snapshot()
        sources = {a["source"] for a in snap.alerts}
        assert {"jobs", "remote_tunnel", "validation"}.issubset(sources)
        severities = {a["severity"] for a in snap.alerts}
        assert SEVERITY_ERROR in severities


# ── Severity ranking ───────────────────────────────────────────────────────


class TestSeverity:
    def test_rollup_uses_max_severity(self, tmp_path: Path) -> None:
        _write_json(
            tmp_path / "remote" / "tunnel.json",
            {"state": "down"},
        )
        hub = _make_hub(tmp_path)
        hub.snapshot()
        rollups = [e for e in hub.read_events() if e.kind == EVENT_ALERT]
        assert rollups[-1].severity == SEVERITY_ERROR
