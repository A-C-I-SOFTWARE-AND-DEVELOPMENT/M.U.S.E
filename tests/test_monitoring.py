"""Tests for the orchestrator's monitoring + observability surfaces.

The orchestrator exposes two pieces a dashboard / supervisor can poll:

* the AI-radar snapshot (``hermes_cli.orchestrator.ai_radar_*``) — a
  freshness marker the AI-improvement skill writes.
* the "best coding tool" mission status — a rollup of job counts the
  orchestrator updates from live job data on every read.

These tests cover both, plus the in-memory event stream on
``JobStore`` (the surface a websocket subscriber depends on).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from hermes_cli import orchestrator as orch


# ── AI radar ──────────────────────────────────────────────────────────


class TestAiRadar:
    def test_status_before_first_update(self) -> None:
        snapshot = orch.ai_radar_status()
        # No file yet — defaults to ``updated_at: 0``.
        assert snapshot.get("updated_at") == 0

    def test_update_writes_snapshot(self) -> None:
        snapshot = orch.ai_radar_update()
        assert snapshot["updated_at"] > 0
        assert "source" in snapshot
        # Persisted under HERMES_HOME/orchestrator/ai_radar.json.
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "ai_radar.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == snapshot

    def test_update_then_status_round_trips(self) -> None:
        snapshot = orch.ai_radar_update()
        reread = orch.ai_radar_status()
        assert reread == snapshot

    def test_slash_dispatch_returns_status_line(self) -> None:
        out = orch.run_ai_radar("update")
        assert "ai-radar snapshot written" in out
        assert "updated_at:" in out

    def test_slash_help_when_empty(self) -> None:
        assert "Usage:" in orch.run_ai_radar("")

    def test_slash_rejects_unknown_subcommand(self) -> None:
        out = orch.run_ai_radar("delete")
        assert "unknown subcommand" in out


# ── Best coding tool mission ──────────────────────────────────────────


class TestMissionStatus:
    def test_default_snapshot_has_mission_and_metrics(self) -> None:
        snapshot = orch.best_coding_tool_mission_status()
        assert "mission" in snapshot
        metrics = snapshot["metrics"]
        assert metrics["jobs_submitted"] == 0
        assert metrics["jobs_published"] == 0
        assert metrics["jobs_resumed"] == 0

    def test_metrics_reflect_live_jobs(self) -> None:
        a = orch.submit_job("alpha")
        b = orch.submit_job("bravo")
        orch.publish_job(a.id)
        # Move bravo to paused then resume to increment resumed_count.
        all_jobs = orch._load_jobs()
        for job in all_jobs:
            if job.id == b.id:
                job.status = "paused"
        orch._save_jobs(all_jobs)
        orch.resume_job(b.id)

        snapshot = orch.best_coding_tool_mission_status()
        metrics = snapshot["metrics"]
        assert metrics["jobs_submitted"] == 2
        assert metrics["jobs_published"] == 1
        assert metrics["jobs_resumed"] == 1

    def test_slash_status_renders_metrics(self) -> None:
        orch.submit_job("seed")
        out = orch.run_best_coding_tool_mission("status")
        assert "mission:" in out
        assert "jobs_submitted:" in out

    def test_slash_help_when_empty(self) -> None:
        assert "Usage:" in orch.run_best_coding_tool_mission("")

    def test_slash_rejects_unknown_subcommand(self) -> None:
        out = orch.run_best_coding_tool_mission("burn-everything")
        assert "unknown subcommand" in out


# ── Event stream (JobStore) ───────────────────────────────────────────

pytest.importorskip("fastapi")

from hermes_cli.orchestrator_api import (  # noqa: E402
    ALL_EVENTS,
    EVENT_JOB_CREATED,
    EVENT_PUBLISH_READY,
    EVENT_WORKER_STARTED,
    JobStore,
)


def _run(coro):
    return asyncio.run(coro)


class TestEventStream:
    def test_unknown_event_is_rejected(self) -> None:
        async def _go():
            store = JobStore()
            job = await store.create("x", {})
            with pytest.raises(ValueError):
                await store.emit_event(job.id, "not.a.real.event")

        _run(_go())

    def test_created_event_lands_in_replay(self) -> None:
        async def _go():
            store = JobStore()
            job = await store.create("x", {"k": "v"})
            replay = await store.replay(job.id)
            assert any(e["event"] == EVENT_JOB_CREATED for e in replay)

        _run(_go())

    def test_subscriber_receives_subsequent_events(self) -> None:
        async def _go():
            store = JobStore()
            job = await store.create("x", {})
            queue = await store.subscribe(job.id)
            await store.emit_event(job.id, EVENT_WORKER_STARTED, {"reason": "go"})
            envelope = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert envelope["event"] == EVENT_WORKER_STARTED
            assert envelope["data"]["reason"] == "go"
            await store.unsubscribe(job.id, queue)

        _run(_go())

    def test_unsubscribe_does_not_raise_when_already_gone(self) -> None:
        async def _go():
            store = JobStore()
            job = await store.create("x", {})
            queue = await store.subscribe(job.id)
            await store.unsubscribe(job.id, queue)
            # Second unsubscribe is a no-op, not an error.
            await store.unsubscribe(job.id, queue)

        _run(_go())

    def test_all_events_table_has_canonical_names(self) -> None:
        # The dashboard imports ALL_EVENTS for its filter dropdown;
        # protect callers from a typo in this table.
        for name in ALL_EVENTS:
            assert "." in name
            assert name == name.lower()
        # Two anchors that must always exist.
        assert EVENT_JOB_CREATED in ALL_EVENTS
        assert EVENT_PUBLISH_READY in ALL_EVENTS
