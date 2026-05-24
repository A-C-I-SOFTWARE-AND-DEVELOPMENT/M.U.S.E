"""Tests for the orchestrator job queue.

The "queue" surface in Hermes is a flat JSON file under
``$HERMES_HOME/orchestrator/jobs.json`` plus the in-memory store in
``hermes_cli.orchestrator_api.JobStore``. These tests pin the queue
contract: submission order, status transitions, prefix-match lookup,
and the in-memory store's listing + update behaviour.

Both pieces are exercised here because the user-facing notion of a
"queue" spans both — the persistent surface (CLI) and the volatile
surface (local API).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from hermes_cli import orchestrator as orch
from hermes_cli.orchestrator_api import JobStore


# ── persistent queue (orchestrator.py) ────────────────────────────────


class TestPersistentQueue:
    def test_submit_writes_jobs_json(self) -> None:
        job = orch.submit_job("ship it")
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "jobs.json"
        raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(raw, list)
        assert any(entry["id"] == job.id for entry in raw)

    def test_submit_rejects_empty_prompt(self) -> None:
        with pytest.raises(ValueError):
            orch.submit_job("   ")

    def test_jobs_default_queued(self) -> None:
        job = orch.submit_job("queued state")
        assert job.status == "queued"

    def test_listing_returns_newest_first(self) -> None:
        a = orch.submit_job("first")
        b = orch.submit_job("second")
        c = orch.submit_job("third")
        listed = orch.list_jobs()
        # Newest job first.
        assert listed[0].id == c.id
        assert listed[1].id == b.id
        assert listed[2].id == a.id

    def test_get_job_by_full_id(self) -> None:
        job = orch.submit_job("findable")
        assert orch.get_job(job.id) == job

    def test_get_job_by_prefix(self) -> None:
        job = orch.submit_job("prefix lookup")
        # ``orc-XXXXXXXX`` — the first 6 characters are unambiguous when
        # this is the only job submitted in the test.
        assert orch.get_job(job.id[:6]).id == job.id  # type: ignore[union-attr]

    def test_get_job_returns_none_for_unknown(self) -> None:
        assert orch.get_job("orc-deadbeef") is None

    def test_resume_marks_queued_if_paused(self) -> None:
        job = orch.submit_job("retry me")
        all_jobs = orch._load_jobs()
        all_jobs[-1].status = "paused"
        orch._save_jobs(all_jobs)
        resumed = orch.resume_job(job.id)
        assert resumed is not None
        assert resumed.status == "queued"
        assert resumed.resumed_count == 1

    def test_resume_keeps_succeeded_status(self) -> None:
        job = orch.submit_job("done")
        all_jobs = orch._load_jobs()
        all_jobs[-1].status = "succeeded"
        orch._save_jobs(all_jobs)
        resumed = orch.resume_job(job.id)
        assert resumed.status == "succeeded"  # type: ignore[union-attr]
        assert resumed.resumed_count == 1  # bump counter even if status stuck

    def test_publish_sets_status_and_timestamp(self) -> None:
        job = orch.submit_job("publish me")
        published = orch.publish_job(job.id)
        assert published.status == "published"  # type: ignore[union-attr]
        assert published.published_at  # type: ignore[union-attr]

    def test_publish_returns_none_for_unknown(self) -> None:
        assert orch.publish_job("orc-missing") is None

    def test_list_limit_is_respected(self) -> None:
        for n in range(3):
            orch.submit_job(f"task {n}")
        # ``limit`` clamps to at least 1.
        listed = orch.list_jobs(limit=1)
        assert len(listed) == 1


# ── volatile queue (orchestrator_api.JobStore) ────────────────────────

pytest.importorskip("fastapi")


def _run(coro):
    return asyncio.run(coro)


class TestVolatileQueue:
    def test_create_returns_unique_ids(self) -> None:
        async def _go():
            store = JobStore()
            a = await store.create("a", {})
            b = await store.create("b", {})
            assert a.id != b.id

        _run(_go())

    def test_list_returns_every_created_job(self) -> None:
        async def _go():
            store = JobStore()
            await store.create("a", {})
            await store.create("b", {})
            await store.create("c", {})
            jobs = await store.list()
            assert {j.name for j in jobs} == {"a", "b", "c"}

        _run(_go())

    def test_update_changes_status(self) -> None:
        async def _go():
            store = JobStore()
            job = await store.create("u", {})
            updated = await store.update(job.id, status="running")
            assert updated.status == "running"

        _run(_go())

    def test_update_unknown_job_raises_key_error(self) -> None:
        async def _go():
            store = JobStore()
            with pytest.raises(KeyError):
                await store.update("nope", status="x")

        _run(_go())

    def test_get_unknown_job_raises(self) -> None:
        async def _go():
            store = JobStore()
            with pytest.raises(KeyError):
                await store.get("missing")

        _run(_go())

    def test_replay_includes_creation_event(self) -> None:
        async def _go():
            store = JobStore()
            job = await store.create("x", {"k": "v"})
            events = await store.replay(job.id)
            assert any(e["event"] == "job.created" for e in events)

        _run(_go())
