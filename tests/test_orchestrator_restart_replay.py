"""Restart-replay durability for the orchestrator JobStore (Sprint 14).

These tests exercise the seam added in ``hermes_cli.job_event_store`` plus the
``JobStore.restore_from_disk`` / ``create_app`` wiring: emitting events tees
them to a durable per-job ``events.jsonl``, and a freshly built store folds
those envelopes back into live ``Job`` state after a "restart".

The contract under test:

* round-trip — events emitted into store A are replayed into a *new* store B
  over the same ``HERMES_HOME`` dir, and ``snapshot`` / status / workers /
  approvals match;
* terminal jobs (reject / cancel) restore to their terminal phase;
* a **bare** ``JobStore()`` never auto-restores (the 100s of in-memory tests
  must stay pure) — restore happens only via ``restore_from_disk`` /
  ``create_app``;
* ``HERMES_JOB_PERSIST=0`` disables the durable tee entirely;
* the durable reader tolerates a truncated trailing line (crash mid-write).

Every test pins ``HERMES_HOME`` to a ``tmp_path`` so the on-disk log is
isolated and deterministic.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from hermes_cli import job_event_store
from hermes_cli.job_replay import JobSnapshot
from hermes_cli.orchestrator_api import (
    EVENT_APPROVAL_GRANTED,
    EVENT_APPROVAL_REJECTED,
    EVENT_APPROVAL_REQUESTED,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_PHASE_CHANGED,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_WORKER_STARTED,
    JobStore,
)
from hermes_cli.orchestrator_events import (
    PHASE_CANCELLED,
    PHASE_EXECUTING,
    PHASE_FAILED,
)


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    """Point HERMES_HOME at an isolated tempdir and ensure persistence is on."""
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv(job_event_store.PERSIST_ENV, raising=False)
    return home


# ---------------------------------------------------------------------------
# Helpers — drive a JobStore through emit_event (which tees to disk)
# ---------------------------------------------------------------------------
async def _seed_running_job(store: JobStore) -> str:
    """A mid-flight job: created → executing, one worker running, one blocked,
    plus a pending approval. Returns the job id."""
    job = await store.create("restart-me", {"goal": "survive a reboot"})
    job_id = job.id
    await store.emit_event(
        job_id, EVENT_PHASE_CHANGED, {"from": "intake", "to": PHASE_EXECUTING}
    )
    await store.emit_event(job_id, EVENT_WORKER_STARTED, {"worker": "claude-code"})
    await store.emit_event(
        job_id, EVENT_WORKER_BLOCKED, {"worker": "reviewer", "reason": "needs input"}
    )
    await store.emit_event(
        job_id, EVENT_APPROVAL_REQUESTED, {"approval_id": "appr_1"}
    )
    return job_id


async def _seed_rejected_job(store: JobStore) -> str:
    job = await store.create("reject-me", {"goal": "x"})
    job_id = job.id
    await store.emit_event(
        job_id, EVENT_APPROVAL_REQUESTED, {"approval_id": "appr_r"}
    )
    await store.emit_event(
        job_id, EVENT_APPROVAL_REJECTED, {"approval_id": "appr_r"}
    )
    await store.emit_event(
        job_id, EVENT_JOB_FAILED, {"reason": "approval rejected"}
    )
    return job_id


async def _seed_cancelled_job(store: JobStore) -> str:
    job = await store.create("cancel-me", {"goal": "x"})
    job_id = job.id
    await store.emit_event(
        job_id, EVENT_PHASE_CHANGED, {"from": "intake", "to": PHASE_CANCELLED}
    )
    await store.emit_event(job_id, EVENT_JOB_FAILED, {"reason": "cancelled"})
    return job_id


# ---------------------------------------------------------------------------
# job_event_store unit-level behavior
# ---------------------------------------------------------------------------
class TestJobEventStore:
    def test_append_read_round_trip(self, hermes_home):
        env = {"event": "x", "job_id": "j1", "ts": 1.0, "data": {"k": "v"}}
        job_event_store.append("j1", env)
        job_event_store.append("j1", {"event": "y", "job_id": "j1", "ts": 2.0, "data": {}})
        records = job_event_store.read("j1")
        assert [r["event"] for r in records] == ["x", "y"]
        assert records[0]["data"] == {"k": "v"}

    def test_iter_job_ids_lists_only_jobs_with_logs(self, hermes_home):
        job_event_store.append("alpha", {"event": "a", "job_id": "alpha"})
        job_event_store.append("beta", {"event": "b", "job_id": "beta"})
        # A stray empty dir must not be reported as a job.
        (hermes_home / "jobs" / "ghost").mkdir(parents=True)
        assert sorted(job_event_store.iter_job_ids()) == ["alpha", "beta"]

    def test_read_tolerates_truncated_last_line(self, hermes_home):
        # Simulate a crash mid-write: a final line with no trailing newline.
        path = hermes_home / "jobs" / "trunc" / "events.jsonl"
        path.parent.mkdir(parents=True)
        good = json.dumps({"event": "ok", "job_id": "trunc", "ts": 1.0, "data": {}})
        partial = '{"event": "broken", "job_id": "trun'  # truncated, no newline
        path.write_text(good + "\n" + partial, encoding="utf-8")
        records = job_event_store.read("trunc")
        assert len(records) == 1
        assert records[0]["event"] == "ok"

    def test_read_skips_corrupt_complete_line(self, hermes_home):
        path = hermes_home / "jobs" / "corrupt" / "events.jsonl"
        path.parent.mkdir(parents=True)
        good = json.dumps({"event": "ok", "job_id": "corrupt", "ts": 1.0, "data": {}})
        path.write_text(good + "\n" + "not json at all\n", encoding="utf-8")
        records = job_event_store.read("corrupt")
        assert [r["event"] for r in records] == ["ok"]

    def test_missing_job_reads_empty(self, hermes_home):
        assert job_event_store.read("nope") == []
        assert job_event_store.iter_job_ids() == []

    def test_unsafe_job_id_cannot_escape_jobs_root(self, hermes_home):
        # job_id is caller-supplied and used to build a path, so a traversal
        # attempt must be neutralized to a single safe segment — never writing
        # outside jobs/ (CodeQL: uncontrolled data in path expression).
        escape = "../../etc/evil"
        job_event_store.append(escape, {"event": "x", "job_id": escape})
        jobs_root = hermes_home / "jobs"
        # Nothing landed outside the jobs root.
        assert not (jobs_root.parent / "etc" / "evil" / "events.jsonl").exists()
        # Whatever the sanitizer produced stays strictly under jobs/.
        for p in jobs_root.rglob("events.jsonl"):
            assert jobs_root.resolve() in p.resolve().parents
        # A read with the same crafted id is consistent (same sanitizer) and safe.
        assert isinstance(job_event_store.read(escape), list)

    def test_blank_job_id_is_noop(self, hermes_home):
        # sanitize_segment rejects empty/blank → _safe_events_path returns None
        # → append/read no-op without raising.
        job_event_store.append("", {"event": "x"})
        job_event_store.append("   ", {"event": "y"})
        assert job_event_store.read("") == []
        assert job_event_store.iter_job_ids() == []

    def test_persist_disabled_makes_ops_noop(self, hermes_home, monkeypatch):
        monkeypatch.setenv(job_event_store.PERSIST_ENV, "0")
        assert job_event_store.persistence_enabled() is False
        job_event_store.append("j", {"event": "x", "job_id": "j"})
        # Nothing written, nothing read, nothing iterated.
        assert job_event_store.read("j") == []
        assert job_event_store.iter_job_ids() == []
        assert not (hermes_home / "jobs" / "j").exists()

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", ""])
    def test_falsey_values_disable(self, hermes_home, monkeypatch, value):
        monkeypatch.setenv(job_event_store.PERSIST_ENV, value)
        assert job_event_store.persistence_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "anything"])
    def test_truthy_values_enable(self, hermes_home, monkeypatch, value):
        monkeypatch.setenv(job_event_store.PERSIST_ENV, value)
        assert job_event_store.persistence_enabled() is True


# ---------------------------------------------------------------------------
# Restart-replay: store A → disk → store B
# ---------------------------------------------------------------------------
class TestRestartReplay:
    def test_emit_tees_envelopes_to_disk(self, hermes_home):
        async def _run():
            store = JobStore()
            job_id = await _seed_running_job(store)
            return job_id, list(store._jobs[job_id].events)

        job_id, in_memory = asyncio.run(_run())
        on_disk = job_event_store.read(job_id)
        # Every in-memory envelope is durably persisted, in order.
        assert [e["event"] for e in on_disk] == [e["event"] for e in in_memory]
        assert job_event_store.iter_job_ids() == [job_id]

    def test_round_trip_restores_running_job(self, hermes_home):
        # Store A emits a mid-flight job and tees it to disk.
        async def _emit():
            store_a = JobStore()
            return await _seed_running_job(store_a)

        job_id = asyncio.run(_emit())

        # Store B (a fresh "process") replays from the same dir.
        store_b = JobStore()
        restored = store_b.restore_from_disk()
        assert restored == 1

        async def _check():
            snap = await store_b.snapshot(job_id)
            job = await store_b.get(job_id)
            status = job.status
            return snap, job, status

        snap, job, status = asyncio.run(_check())

        assert isinstance(snap, JobSnapshot)
        assert snap.job_id == job_id
        assert snap.name == "restart-me"
        assert snap.spec == {"goal": "survive a reboot"}
        assert snap.phase == PHASE_EXECUTING
        assert snap.status == "running"
        assert snap.workers == {"claude-code": "running", "reviewer": "blocked"}
        assert snap.approvals == {"appr_1": "pending"}

        # The reconstructed live Job mirrors the snapshot.
        assert job.status == "running"
        assert job.phase == PHASE_EXECUTING
        assert job.workers["claude-code"]["state"] == "running"
        assert job.workers["reviewer"]["state"] == "blocked"
        assert job.approvals == [{"id": "appr_1", "state": "pending"}]

    def test_restore_reseeds_events_so_snapshot_route_works(self, hermes_home):
        async def _emit():
            store_a = JobStore()
            return await _seed_running_job(store_a)

        job_id = asyncio.run(_emit())

        store_b = JobStore()
        store_b.restore_from_disk()

        # snapshot() re-folds job.events; it only works post-restart if
        # restore re-seeded the loaded envelopes onto the Job.
        async def _events_and_snapshot():
            replay = await store_b.replay(job_id)
            snap = await store_b.snapshot(job_id)
            return replay, snap

        replay, snap = asyncio.run(_events_and_snapshot())
        assert len(replay) >= 5  # created + phase + 2 workers + approval
        assert snap.phase == PHASE_EXECUTING
        assert snap.workers == {"claude-code": "running", "reviewer": "blocked"}

    def test_restore_terminal_reject_job(self, hermes_home):
        job_id = asyncio.run(_with_store(_seed_rejected_job))

        store_b = JobStore()
        assert store_b.restore_from_disk() == 1

        async def _check():
            snap = await store_b.snapshot(job_id)
            job = await store_b.get(job_id)
            return snap, job

        snap, job = asyncio.run(_check())
        assert snap.phase == PHASE_FAILED
        assert snap.status == "failed"
        assert snap.failed is True
        assert snap.error == "approval rejected"
        assert snap.approvals == {"appr_r": "rejected"}
        assert job.status == "failed"
        assert job.phase == PHASE_FAILED
        assert job.error == "approval rejected"

    def test_restore_terminal_cancel_job(self, hermes_home):
        job_id = asyncio.run(_with_store(_seed_cancelled_job))

        store_b = JobStore()
        assert store_b.restore_from_disk() == 1

        async def _check():
            snap = await store_b.snapshot(job_id)
            job = await store_b.get(job_id)
            return snap, job

        snap, job = asyncio.run(_check())
        assert snap.phase == PHASE_CANCELLED
        assert snap.status == "cancelled"
        assert snap.is_terminal
        assert job.status == "cancelled"
        assert job.phase == PHASE_CANCELLED

    def test_restore_multiple_jobs(self, hermes_home):
        async def _emit_all():
            store_a = JobStore()
            running = await _seed_running_job(store_a)
            rejected = await _seed_rejected_job(store_a)
            cancelled = await _seed_cancelled_job(store_a)
            return running, rejected, cancelled

        running, rejected, cancelled = asyncio.run(_emit_all())

        store_b = JobStore()
        assert store_b.restore_from_disk() == 3

        async def _list():
            return {j.id: j for j in await store_b.list()}

        jobs = asyncio.run(_list())
        assert set(jobs) == {running, rejected, cancelled}
        assert jobs[running].phase == PHASE_EXECUTING
        assert jobs[rejected].phase == PHASE_FAILED
        assert jobs[cancelled].phase == PHASE_CANCELLED

    def test_restore_is_idempotent_and_keeps_live_copy(self, hermes_home):
        job_id = asyncio.run(_with_store(_seed_running_job))

        store_b = JobStore()
        assert store_b.restore_from_disk() == 1
        # A second restore finds the job already present and restores nothing.
        assert store_b.restore_from_disk() == 0

        async def _mutate_then_restore():
            await store_b.update(job_id, status="running", phase="custom-live")
            # Restore must NOT clobber the live (mutated) copy.
            again = store_b.restore_from_disk()
            job = await store_b.get(job_id)
            return again, job.phase

        again, phase = asyncio.run(_mutate_then_restore())
        assert again == 0
        assert phase == "custom-live"

    def test_cost_restored_from_event_sourced_deltas(self, hermes_home):
        # Cost is event-sourced (cost.accumulated, FU-3 residual closeout):
        # a restored job's cost meter rebuilds to the pre-restart aggregate,
        # including token buckets and the by-model breakdown.
        class _Usage:
            input_tokens = 100
            output_tokens = 40
            cache_read_tokens = 7
            cache_write_tokens = 0
            reasoning_tokens = 3

        async def _emit_with_cost():
            store_a = JobStore()
            job_id = await _seed_running_job(store_a)
            await store_a.accumulate_cost(job_id, cost_usd=4.2, model="m")
            await store_a.accumulate_cost(
                job_id, usage=_Usage(), cost_usd="0.8", model="m2", provider="p"
            )
            assert store_a._jobs[job_id].cost.totals()["cost_usd"] == pytest.approx(5.0)
            return job_id

        job_id = asyncio.run(_emit_with_cost())

        store_b = JobStore()
        store_b.restore_from_disk()

        async def _cost():
            job = await store_b.get(job_id)
            return job.cost.totals()

        totals = asyncio.run(_cost())
        assert totals["cost_usd"] == pytest.approx(5.0)
        assert totals["input_tokens"] == 100
        assert totals["output_tokens"] == 40
        assert totals["cache_read_tokens"] == 7
        assert totals["reasoning_tokens"] == 3
        assert totals["call_count"] == 2
        assert totals["by_model"] == {
            "m": pytest.approx(4.2),
            "p/m2": pytest.approx(0.8),
        }

    def test_pre_cost_event_logs_restore_with_zero_meter(self, hermes_home):
        # Logs that predate cost event-sourcing carry no cost.accumulated
        # deltas — they must still restore cleanly, with the old zero meter.
        job_id = asyncio.run(_with_store(_seed_running_job))

        store_b = JobStore()
        store_b.restore_from_disk()

        async def _cost():
            job = await store_b.get(job_id)
            return job.cost.totals()

        totals = asyncio.run(_cost())
        assert totals["cost_usd"] == pytest.approx(0.0)
        assert totals["call_count"] == 0


# ---------------------------------------------------------------------------
# The no-accidental-auto-restore guarantee + disable switch
# ---------------------------------------------------------------------------
class TestNoAccidentalRestore:
    def test_bare_jobstore_does_not_auto_restore(self, hermes_home):
        # Persist a job to disk...
        job_id = asyncio.run(_with_store(_seed_running_job))
        assert job_event_store.iter_job_ids() == [job_id]

        # ...then a *bare* JobStore (no restore call) must be empty. This is the
        # guarantee that keeps the 100s of in-memory tests pure.
        async def _empty():
            return await JobStore().list()

        assert asyncio.run(_empty()) == []

    def test_persist_disabled_disables_the_tee(self, hermes_home, monkeypatch):
        monkeypatch.setenv(job_event_store.PERSIST_ENV, "0")

        job_id = asyncio.run(_with_store(_seed_running_job))

        # Nothing was teed to disk.
        assert job_event_store.read(job_id) == []
        assert job_event_store.iter_job_ids() == []
        # And a restore over the (empty) dir finds nothing.
        store_b = JobStore()
        assert store_b.restore_from_disk() == 0


# ---------------------------------------------------------------------------
# create_app wiring: restores only a store it created
# ---------------------------------------------------------------------------
class TestCreateAppRestore:
    def test_create_app_restores_self_created_store(self, hermes_home):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from hermes_cli.orchestrator_api import create_app

        job_id = asyncio.run(_with_store(_seed_running_job))

        app = create_app()  # no injected store → should restore from disk
        with TestClient(app) as client:
            resp = client.get(f"/jobs/{job_id}/status")
            assert resp.status_code == 200
            assert resp.json()["status"] == "running"
            snap = client.get(f"/jobs/{job_id}/snapshot")
            assert snap.status_code == 200
            assert snap.json()["phase"] == PHASE_EXECUTING

    def test_create_app_does_not_restore_injected_store(self, hermes_home):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from hermes_cli.orchestrator_api import create_app

        job_id = asyncio.run(_with_store(_seed_running_job))

        injected = JobStore()  # caller-owned store: create_app must NOT restore it
        app = create_app(store=injected)
        with TestClient(app) as client:
            resp = client.get("/jobs")
            assert resp.status_code == 200
            assert resp.json() == {"jobs": []}
            missing = client.get(f"/jobs/{job_id}/status")
            assert missing.status_code == 404

    def test_create_app_skips_restore_when_persist_disabled(self, hermes_home, monkeypatch):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from hermes_cli.orchestrator_api import create_app

        # Seed disk while persistence is ON.
        job_id = asyncio.run(_with_store(_seed_running_job))
        assert job_event_store.iter_job_ids() == [job_id]

        # Now boot with persistence OFF: no replay even though the log exists.
        monkeypatch.setenv(job_event_store.PERSIST_ENV, "0")
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/jobs")
            assert resp.json() == {"jobs": []}


# ---------------------------------------------------------------------------
# small async harness
# ---------------------------------------------------------------------------
async def _with_store(seed):
    """Run ``seed(store)`` on a fresh JobStore and return its result."""
    return await seed(JobStore())
