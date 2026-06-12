"""Tests for muse_cli.orchestrator_api — local-only orchestrator backend."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from muse_cli import orchestrator_api  # noqa: E402
from muse_cli.orchestrator_api import (  # noqa: E402
    ALL_EVENTS,
    EVENT_EVIDENCE_UPDATED,
    EVENT_JOB_CREATED,
    EVENT_PUBLISH_READY,
    EVENT_VALIDATION_COMPLETED,
    EVENT_WORKER_STARTED,
    JobStore,
    _extract_usage_report,
    create_app,
    run,
)


# ---------------------------------------------------------------------------
# JobStore unit tests
# ---------------------------------------------------------------------------


class TestJobStore:
    def test_create_and_get(self):
        async def _run():
            store = JobStore()
            job = await store.create("hello", {"k": "v"})
            assert job.id
            assert job.name == "hello"
            assert job.spec == {"k": "v"}
            assert job.status == "pending"
            same = await store.get(job.id)
            assert same is job
        asyncio.run(_run())

    def test_get_missing_raises(self):
        async def _run():
            store = JobStore()
            with pytest.raises(KeyError):
                await store.get("nope")
        asyncio.run(_run())

    def test_list_returns_all(self):
        async def _run():
            store = JobStore()
            await store.create("a", {})
            await store.create("b", {})
            jobs = await store.list()
            assert {j.name for j in jobs} == {"a", "b"}
        asyncio.run(_run())

    def test_update_changes_fields_and_bumps_timestamp(self):
        async def _run():
            store = JobStore()
            job = await store.create("u", {})
            original_updated = job.updated_at
            await asyncio.sleep(0.001)
            updated = await store.update(job.id, status="running")
            assert updated.status == "running"
            assert updated.updated_at >= original_updated
        asyncio.run(_run())

    def test_emit_event_appends_to_history_and_wakes_subscriber(self):
        async def _run():
            store = JobStore()
            job = await store.create("h", {})
            queue = await store.subscribe(job.id)
            # create() emits job.created — drain history first
            history = await store.replay(job.id)
            assert any(e["event"] == EVENT_JOB_CREATED for e in history)

            await store.emit_event(job.id, EVENT_EVIDENCE_UPDATED, {"kind": "test"})
            envelope = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert envelope["event"] == EVENT_EVIDENCE_UPDATED
            assert envelope["job_id"] == job.id
            assert envelope["data"] == {"kind": "test"}
        asyncio.run(_run())

    def test_snapshot_reconstructs_state_from_events(self):
        async def _run():
            store = JobStore()
            job = await store.create("snap", {"goal": "x"})
            await store.emit_event(
                job.id, EVENT_WORKER_STARTED, {"worker": "claude-code"}
            )
            await store.emit_event(
                job.id, EVENT_VALIDATION_COMPLETED, {"result": {"ok": True}}
            )
            await store.emit_event(
                job.id, EVENT_PUBLISH_READY, {"plan": {"pr_url": "https://x/pr/1"}}
            )
            snap = await store.snapshot(job.id)
            assert snap.job_id == job.id
            assert snap.name == "snap"
            assert snap.spec == {"goal": "x"}
            assert snap.workers == {"claude-code": "running"}
            assert snap.validation == {"ok": True}
            assert snap.pr_url == "https://x/pr/1"
        asyncio.run(_run())

    def test_snapshot_unknown_job_is_empty(self):
        async def _run():
            store = JobStore()
            snap = await store.snapshot("nope")
            assert snap.job_id == "nope"
            assert snap.event_count == 0
        asyncio.run(_run())

    def test_emit_unknown_event_raises(self):
        async def _run():
            store = JobStore()
            job = await store.create("e", {})
            with pytest.raises(ValueError):
                await store.emit_event(job.id, "totally.fake", {})
        asyncio.run(_run())

    def test_unsubscribe_drops_subscriber(self):
        async def _run():
            store = JobStore()
            job = await store.create("d", {})
            queue = await store.subscribe(job.id)
            await store.unsubscribe(job.id, queue)
            # Emitting now must not put anything on the unsubscribed queue.
            await store.emit_event(job.id, EVENT_WORKER_STARTED, {})
            assert queue.empty()
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Event-name registry
# ---------------------------------------------------------------------------


def test_all_events_match_spec():
    assert set(ALL_EVENTS) == {
        "job.created",
        "job.failed",
        "phase.changed",
        "error",
        "approval.requested",
        "approval.granted",
        "approval.rejected",
        "worker.started",
        "worker.heartbeat",
        "worker.blocked",
        "worker.completed",
        "evidence.updated",
        "scoring.completed",
        "validation.completed",
        "publish.ready",
    }


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def token_client():
    app = create_app(token="secret-abc")
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "hermes-orchestrator-api"
        assert body["auth_required"] is False
        assert body["public_bind"] is False

    def test_health_open_without_token_even_when_auth_required(self, token_client):
        # /health is allowed unauthenticated so supervisors can probe it.
        resp = token_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["auth_required"] is True


class TestJobCRUD:
    def test_list_jobs_empty(self, client):
        resp = client.get("/jobs")
        assert resp.status_code == 200
        assert resp.json() == {"jobs": []}

    def test_create_and_fetch_job(self, client):
        resp = client.post("/jobs", json={"name": "build-docs", "spec": {"k": 1}})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "build-docs"
        assert body["spec"] == {"k": 1}
        assert body["status"] == "pending"

        job_id = body["id"]
        got = client.get(f"/jobs/{job_id}")
        assert got.status_code == 200
        assert got.json()["id"] == job_id

    def test_create_requires_name(self, client):
        resp = client.post("/jobs", json={"name": "", "spec": {}})
        assert resp.status_code == 400

    def test_create_rejects_non_object_spec(self, client):
        resp = client.post("/jobs", json={"name": "x", "spec": "not-a-dict"})
        assert resp.status_code == 400

    def test_create_accepts_missing_spec(self, client):
        resp = client.post("/jobs", json={"name": "x"})
        assert resp.status_code == 201
        assert resp.json()["spec"] == {}

    def test_get_missing_returns_404(self, client):
        resp = client.get("/jobs/does-not-exist")
        assert resp.status_code == 404

    def test_list_jobs_after_create(self, client):
        client.post("/jobs", json={"name": "a"})
        client.post("/jobs", json={"name": "b"})
        resp = client.get("/jobs")
        assert resp.status_code == 200
        names = sorted(j["name"] for j in resp.json()["jobs"])
        assert names == ["a", "b"]


class TestStatusAndArtifacts:
    def test_status_endpoint(self, client):
        job_id = client.post("/jobs", json={"name": "s"}).json()["id"]
        resp = client.get(f"/jobs/{job_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == job_id
        assert body["status"] == "pending"
        assert body["error"] is None

    def test_artifacts_endpoint_empty(self, client):
        job_id = client.post("/jobs", json={"name": "a"}).json()["id"]
        resp = client.get(f"/jobs/{job_id}/artifacts")
        assert resp.status_code == 200
        assert resp.json() == {"id": job_id, "artifacts": []}


class TestSnapshotEndpoint:
    """GET /jobs/{id}/snapshot — state rebuilt from the recorded event stream.

    The route is the live entry point for ``JobStore.snapshot`` (folds
    ``job.events`` through ``rebuild_snapshot``). It derives state solely from
    the event log, not from the mutated in-memory ``Job``.
    """

    def test_snapshot_fresh_job_is_intake(self, client):
        job_id = client.post("/jobs", json={"name": "snap", "spec": {"goal": "x"}}).json()["id"]
        resp = client.get(f"/jobs/{job_id}/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        # Reconstructed from the single job.created event.
        assert body["job_id"] == job_id
        assert body["name"] == "snap"
        assert body["spec"] == {"goal": "x"}
        assert body["phase"] == "intake"
        assert body["status"] == "pending"
        assert body["event_count"] == 1

    def test_snapshot_reflects_lifecycle_actions(self, client):
        # Drive real HTTP lifecycle actions, then confirm the snapshot route
        # rebuilds matching state purely from the emitted events.
        job_id = client.post("/jobs", json={"name": "life"}).json()["id"]
        client.post(f"/jobs/{job_id}/validate", json={"checks": ["lint"]})
        client.post(
            f"/jobs/{job_id}/publish-plan", json={"pr_url": "https://x/pr/7"}
        )
        body = client.get(f"/jobs/{job_id}/snapshot").json()
        assert body["phase"] == "publish_ready"
        assert body["status"] == "publish_ready"
        # /validate stamps a requested_at; the reducer carries the whole result.
        assert body["validation"]["checks"] == ["lint"]
        assert body["publish_plan"]["pr_url"] == "https://x/pr/7"
        assert body["pr_url"] == "https://x/pr/7"

    def test_snapshot_reconstructs_workers(self, client):
        # Seed worker events via the shared store, then read them back through
        # the route to confirm the workers map is rebuilt from the stream.
        app = create_app()
        store = app.state.store
        with TestClient(app) as c:
            job_id = c.post("/jobs", json={"name": "wk"}).json()["id"]

            async def _seed():
                await store.emit_event(
                    job_id, EVENT_WORKER_STARTED, {"worker": "claude-code"}
                )
                await store.emit_event(
                    job_id, EVENT_VALIDATION_COMPLETED, {"result": {"ok": True}}
                )

            asyncio.run(_seed())

            body = c.get(f"/jobs/{job_id}/snapshot").json()
            assert body["workers"] == {"claude-code": "running"}
            assert body["validation"] == {"ok": True}

    def test_snapshot_missing_job_returns_404(self, client):
        resp = client.get("/jobs/does-not-exist/snapshot")
        assert resp.status_code == 404


class TestCostAndBudget:
    """Per-job cost aggregate + budget evaluation (Sprint 10, additive)."""

    def test_status_includes_zero_cost_and_no_budget_by_default(self, client):
        job_id = client.post("/jobs", json={"name": "c"}).json()["id"]
        body = client.get(f"/jobs/{job_id}/status").json()
        assert body["cost"]["cost_usd"] == 0.0
        assert body["cost"]["total_tokens"] == 0
        # No budget configured in the spec -> additive default is None.
        assert body["budget"] is None

    def test_job_dict_includes_cost(self, client):
        job_id = client.post("/jobs", json={"name": "c2"}).json()["id"]
        body = client.get(f"/jobs/{job_id}").json()
        assert body["cost"]["cost_usd"] == 0.0
        assert body["cost"]["call_count"] == 0

    def test_accumulate_cost_surfaces_in_status(self):
        async def _run():
            store = JobStore()
            job = await store.create("acc", {})
            await store.accumulate_cost(
                job.id, cost_usd=0.03, provider="anthropic", model="claude-opus-4-7"
            )
            await store.accumulate_cost(job.id, cost_usd=0.02)
            refreshed = await store.get(job.id)
            totals = refreshed.cost.totals()
            assert totals["cost_usd"] == 0.05
            assert totals["call_count"] == 2
            assert totals["by_model"] == {"anthropic/claude-opus-4-7": 0.03}
        asyncio.run(_run())

    def test_accumulate_cost_unknown_job_raises(self):
        async def _run():
            store = JobStore()
            with pytest.raises(KeyError):
                await store.accumulate_cost("nope", cost_usd=0.01)
        asyncio.run(_run())

    def test_budget_within_when_under_limits(self):
        async def _run():
            store = JobStore()
            job = await store.create(
                "b", {"budget": {"soft_limit": 1.0, "hard_limit": 2.0}}
            )
            await store.accumulate_cost(job.id, cost_usd=0.5)
            budget = (await store.get(job.id)).budget_status()
            assert budget is not None
            assert budget["outcome"] == "within"
            assert budget["tier"] == "auto"
            assert budget["should_stop"] is False
            assert budget["spent"] == 0.5
        asyncio.run(_run())

    def test_budget_soft_exceeded_needs_approval(self):
        async def _run():
            store = JobStore()
            job = await store.create(
                "b", {"budget": {"soft_limit": 1.0, "hard_limit": 2.0}}
            )
            await store.accumulate_cost(job.id, cost_usd=1.5)
            budget = (await store.get(job.id)).budget_status()
            assert budget["outcome"] == "soft_exceeded"  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture
            assert budget["tier"] == "ask"  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture
            assert budget["needs_approval"] is True  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture
        asyncio.run(_run())

    def test_budget_hard_exceeded_should_stop(self):
        async def _run():
            store = JobStore()
            job = await store.create("b", {"budget": {"hard_limit": 2.0}})
            await store.accumulate_cost(job.id, cost_usd=2.0)
            budget = (await store.get(job.id)).budget_status()
            assert budget["outcome"] == "hard_exceeded"  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture
            assert budget["tier"] == "refuse"  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture
            assert budget["should_stop"] is True  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture
        asyncio.run(_run())

    def test_malformed_budget_spec_degrades_to_none(self):
        async def _run():
            store = JobStore()
            # soft > hard is invalid; status must not raise, just no budget.
            job = await store.create(
                "b", {"budget": {"soft_limit": 5.0, "hard_limit": 1.0}}
            )
            await store.accumulate_cost(job.id, cost_usd=3.0)
            assert (await store.get(job.id)).budget_status() is None
        asyncio.run(_run())

    def test_budget_appears_in_status_endpoint(self, client):
        job_id = client.post(
            "/jobs",
            json={"name": "be", "spec": {"budget": {"hard_limit": 0.10}}},
        ).json()["id"]
        body = client.get(f"/jobs/{job_id}/status").json()
        assert body["budget"] is not None
        assert body["budget"]["outcome"] == "within"
        assert body["budget"]["hard_limit"] == 0.10


class TestLifecycleActions:
    def test_resume_sets_running_and_emits_event(self, client):
        job_id = client.post("/jobs", json={"name": "r"}).json()["id"]
        resp = client.post(f"/jobs/{job_id}/resume")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"

    def test_cancel_marks_cancelled(self, client):
        job_id = client.post("/jobs", json={"name": "c"}).json()["id"]
        resp = client.post(f"/jobs/{job_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_is_idempotent(self, client):
        job_id = client.post("/jobs", json={"name": "c2"}).json()["id"]
        client.post(f"/jobs/{job_id}/cancel")
        # Second cancel returns the (still cancelled) job without erroring.
        resp = client.post(f"/jobs/{job_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_resume_rejects_terminal_job(self, client):
        job_id = client.post("/jobs", json={"name": "t"}).json()["id"]
        client.post(f"/jobs/{job_id}/cancel")
        resp = client.post(f"/jobs/{job_id}/resume")
        assert resp.status_code == 409

    def test_validate_stores_payload(self, client):
        job_id = client.post("/jobs", json={"name": "v"}).json()["id"]
        resp = client.post(
            f"/jobs/{job_id}/validate", json={"checks": ["lint", "types"]}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "validating"
        assert body["validation"]["checks"] == ["lint", "types"]

    def test_publish_plan_stores_payload(self, client):
        job_id = client.post("/jobs", json={"name": "p"}).json()["id"]
        resp = client.post(
            f"/jobs/{job_id}/publish-plan", json={"channel": "stable"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "publish_ready"
        assert body["publish_plan"]["channel"] == "stable"

    def test_action_on_missing_job(self, client):
        for action in ("resume", "cancel", "validate", "publish-plan", "approve", "reject"):
            resp = client.post(f"/jobs/missing/{action}", json={})
            assert resp.status_code == 404, action


# ---------------------------------------------------------------------------
# Phase 18 — logs, approvals, voice intake, workers
# ---------------------------------------------------------------------------


class TestLogsEndpoint:
    def test_logs_include_creation_event(self, client):
        job_id = client.post("/jobs", json={"name": "lg"}).json()["id"]
        resp = client.get(f"/jobs/{job_id}/logs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == job_id
        events = [e["event"] for e in body["logs"]]
        assert events == ["job.created"]

    def test_logs_grow_after_actions(self, client):
        job_id = client.post("/jobs", json={"name": "lg2"}).json()["id"]
        client.post(f"/jobs/{job_id}/resume")
        resp = client.get(f"/jobs/{job_id}/logs")
        events = [e["event"] for e in resp.json()["logs"]]
        # job.created, phase.changed, worker.started — order preserved.
        assert events == ["job.created", "phase.changed", "worker.started"]

    def test_logs_since_filters_history(self, client):
        job_id = client.post("/jobs", json={"name": "lg3"}).json()["id"]
        initial = client.get(f"/jobs/{job_id}/logs").json()["logs"]
        watermark = initial[-1]["ts"]
        client.post(f"/jobs/{job_id}/resume")
        resp = client.get(f"/jobs/{job_id}/logs", params={"since": watermark})
        # Only events strictly after the watermark are returned.
        events = [e["event"] for e in resp.json()["logs"]]
        assert "job.created" not in events
        assert "worker.started" in events

    def test_logs_limit_returns_tail(self, client):
        job_id = client.post("/jobs", json={"name": "lg4"}).json()["id"]
        client.post(f"/jobs/{job_id}/resume")
        client.post(f"/jobs/{job_id}/validate", json={"x": 1})
        resp = client.get(f"/jobs/{job_id}/logs", params={"limit": 2})
        assert len(resp.json()["logs"]) == 2

    def test_logs_missing_job(self, client):
        resp = client.get("/jobs/missing/logs")
        assert resp.status_code == 404


class TestApprovalEndpoints:
    def test_approve_grants_pending(self, client):
        # Seed an approval by reaching into the store directly via the
        # API's update path: list_jobs returns the job, but tests don't
        # have a store handle; use the store on app.state.
        app = create_app()
        store = app.state.store
        # Drive via TestClient so the middleware runs.
        with TestClient(app) as c:
            job_id = c.post("/jobs", json={"name": "appr"}).json()["id"]

            async def _seed():
                await store.update(
                    job_id,
                    status="awaiting_approval",
                    approvals=[{"id": "a1", "state": "pending", "summary": "ship"}],
                )
                await store.emit_event(
                    job_id,
                    "approval.requested",
                    {"id": "a1", "summary": "ship"},
                )
            asyncio.run(_seed())

            resp = c.post(
                f"/jobs/{job_id}/approve",
                json={"approval_id": "a1", "comment": "lgtm"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "running"
            assert body["approvals"][0]["state"] == "granted"
            assert body["approvals"][0]["comment"] == "lgtm"

    def test_approve_without_id_picks_oldest_pending(self, client):
        app = create_app()
        store = app.state.store
        with TestClient(app) as c:
            job_id = c.post("/jobs", json={"name": "appr2"}).json()["id"]

            async def _seed():
                await store.update(
                    job_id,
                    approvals=[
                        {"id": "a1", "state": "pending"},
                        {"id": "a2", "state": "pending"},
                    ],
                )
            asyncio.run(_seed())

            body = c.post(f"/jobs/{job_id}/approve", json={}).json()
            states = {a["id"]: a["state"] for a in body["approvals"]}
            assert states == {"a1": "granted", "a2": "pending"}

    def test_approve_with_no_pending_is_409(self, client):
        job_id = client.post("/jobs", json={"name": "appr3"}).json()["id"]
        resp = client.post(f"/jobs/{job_id}/approve", json={})
        assert resp.status_code == 409

    def test_reject_marks_failed(self, client):
        app = create_app()
        store = app.state.store
        with TestClient(app) as c:
            job_id = c.post("/jobs", json={"name": "rej"}).json()["id"]

            async def _seed():
                await store.update(
                    job_id,
                    approvals=[{"id": "a1", "state": "pending"}],
                )
            asyncio.run(_seed())

            resp = c.post(
                f"/jobs/{job_id}/reject",
                json={"approval_id": "a1", "comment": "nope"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "failed"
            assert body["error"] == "nope"
            assert body["approvals"][0]["state"] == "rejected"


class TestVoiceIntake:
    def test_voice_intake_creates_job(self, client):
        resp = client.post(
            "/voice/intake",
            json={
                "transcript": "Build the release notes for v1.4 and ship it",
                "context": {"locale": "en-US"},
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["source"] == "voice"
        assert body["spec"]["transcript"].startswith("Build the release")
        assert body["spec"]["context"] == {"locale": "en-US"}
        assert body["name"]  # auto-summary, non-empty

    def test_voice_intake_uses_explicit_name(self, client):
        resp = client.post(
            "/voice/intake",
            json={"transcript": "hi", "name": "Voice job 42"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Voice job 42"

    def test_voice_intake_rejects_empty_transcript(self, client):
        resp = client.post("/voice/intake", json={"transcript": "   "})
        assert resp.status_code == 400

    def test_voice_intake_rejects_non_object(self, client):
        # FastAPI enforces the Dict body shape before our handler runs,
        # so a top-level non-object lands a 422 from the framework.
        resp = client.post("/voice/intake", json="not-an-object")
        assert resp.status_code in (400, 422)

    def test_voice_intake_merges_spec_override(self, client):
        resp = client.post(
            "/voice/intake",
            json={
                "transcript": "deploy",
                "spec": {"priority": "high"},
            },
        )
        body = resp.json()
        assert body["spec"]["priority"] == "high"
        assert body["spec"]["transcript"] == "deploy"


class TestWorkers:
    def test_global_workers_empty(self, client):
        resp = client.get("/workers")
        assert resp.status_code == 200
        assert resp.json() == {"workers": []}

    def test_post_worker_heartbeat_and_listing(self, client):
        job_id = client.post("/jobs", json={"name": "wk"}).json()["id"]
        resp = client.post(
            f"/jobs/{job_id}/workers/builder",
            json={"state": "running", "progress": 0.4, "note": "compiling"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["worker"] == "builder"
        assert body["info"]["progress"] == 0.4
        assert body["info"]["state"] == "running"

        listing = client.get("/workers").json()["workers"]
        assert len(listing) == 1
        assert listing[0]["job_id"] == job_id
        assert listing[0]["worker"] == "builder"

    def test_worker_heartbeat_emits_event(self, client):
        job_id = client.post("/jobs", json={"name": "wkh"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            ws.receive_json()  # job.created
            client.post(
                f"/jobs/{job_id}/workers/runner",
                json={"state": "running", "progress": 0.1},
            )
            envelope = ws.receive_json()
            assert envelope["event"] == "worker.heartbeat"
            assert envelope["data"]["worker"] == "runner"

    def test_worker_blocked_event(self, client):
        job_id = client.post("/jobs", json={"name": "wkb"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            ws.receive_json()
            client.post(
                f"/jobs/{job_id}/workers/runner",
                json={"state": "blocked", "reason": "auth"},
            )
            envelope = ws.receive_json()
            assert envelope["event"] == "worker.blocked"
            assert envelope["data"]["reason"] == "auth"

    def test_worker_completion_event(self, client):
        job_id = client.post("/jobs", json={"name": "wkc"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            ws.receive_json()
            client.post(
                f"/jobs/{job_id}/workers/runner",
                json={"state": "done", "result": {"ok": True}},
            )
            envelope = ws.receive_json()
            assert envelope["event"] == "worker.completed"
            assert envelope["data"]["result"] == {"ok": True}

    def test_worker_path_param_mismatch_rejected(self, client):
        job_id = client.post("/jobs", json={"name": "mm"}).json()["id"]
        resp = client.post(
            f"/jobs/{job_id}/workers/alice",
            json={"worker": "bob", "state": "running"},
        )
        assert resp.status_code == 400

    def test_job_specific_worker_list(self, client):
        job_id = client.post("/jobs", json={"name": "wkl"}).json()["id"]
        client.post(
            f"/jobs/{job_id}/workers/a", json={"state": "running"}
        )
        client.post(
            f"/jobs/{job_id}/workers/b", json={"state": "blocked", "reason": "x"}
        )
        body = client.get(f"/jobs/{job_id}/workers").json()
        assert set(body["workers"]) == {"a", "b"}


class TestWorkerUsageReporting:
    """A worker report carrying usage/cost folds into the job cost aggregate.

    This is the producer seam documented in ``muse_cli.job_cost``: the
    ``POST /jobs/{id}/workers/{worker}`` endpoint already accepts a free-form
    report body; when that body carries token usage / cost, it accumulates onto
    the job's :class:`~muse_cli.job_cost.JobCost`.
    """

    def test_extract_usage_report_none_for_plain_heartbeat(self):
        # A liveness-only heartbeat carries no cost signal -> no accumulation.
        assert _extract_usage_report({"state": "running", "progress": 0.5}) is None

    def test_extract_usage_report_tokens_and_cost(self):
        report = _extract_usage_report(
            {
                "state": "done",
                "usage": {"input_tokens": 100, "output_tokens": 40},
                "cost_usd": 0.012,
                "model": "claude-opus-4-7",
                "provider": "anthropic",
            }
        )
        assert report is not None
        assert report["cost_usd"] == 0.012
        assert report["model"] == "claude-opus-4-7"
        assert report["provider"] == "anthropic"
        usage = report["usage"]
        assert usage.input_tokens == 100
        assert usage.output_tokens == 40

    def test_extract_usage_report_cost_only(self):
        report = _extract_usage_report({"cost_usd": 0.5})
        assert report == {"usage": None, "cost_usd": 0.5}

    def test_extract_usage_report_rejects_bool_cost_and_junk_tokens(self):
        # bool cost and non-numeric / negative token values are dropped; an
        # empty usage block with no usable signal degrades to None.
        assert _extract_usage_report({"cost_usd": True}) is None
        assert (
            _extract_usage_report({"usage": {"input_tokens": "lots", "output_tokens": -5}})
            is None
        )

    def test_worker_report_accumulates_job_cost(self, client):
        job_id = client.post("/jobs", json={"name": "ucost"}).json()["id"]
        # Plain heartbeat first — must not move the meter.
        client.post(
            f"/jobs/{job_id}/workers/builder",
            json={"state": "running", "progress": 0.2},
        )
        assert client.get(f"/jobs/{job_id}/status").json()["cost"]["cost_usd"] == 0.0

        # Completion report with usage + cost — folds into the aggregate.
        resp = client.post(
            f"/jobs/{job_id}/workers/builder",
            json={
                "state": "done",
                "usage": {"input_tokens": 200, "output_tokens": 80},
                "cost_usd": 0.03,
                "model": "claude-opus-4-7",
                "provider": "anthropic",
                "result": {"ok": True},
            },
        )
        assert resp.status_code == 200
        cost = client.get(f"/jobs/{job_id}/status").json()["cost"]
        assert cost["cost_usd"] == 0.03
        assert cost["input_tokens"] == 200
        assert cost["output_tokens"] == 80
        assert cost["call_count"] == 1
        assert cost["by_model"] == {"anthropic/claude-opus-4-7": 0.03}

    def test_worker_reports_accumulate_across_calls(self, client):
        job_id = client.post("/jobs", json={"name": "uacc"}).json()["id"]
        for amount in (0.01, 0.02, 0.04):
            client.post(
                f"/jobs/{job_id}/workers/runner",
                json={"state": "running", "cost_usd": amount},
            )
        cost = client.get(f"/jobs/{job_id}/status").json()["cost"]
        assert cost["cost_usd"] == pytest.approx(0.07)
        assert cost["call_count"] == 3

    def test_worker_report_drives_budget_decision(self, client):
        # Usage reporting + a configured budget => the status endpoint reflects
        # the breach. This is the end-to-end value: cost now actually moves the
        # budget meter instead of staying pinned at zero.
        job_id = client.post(
            "/jobs",
            json={"name": "ubudget", "spec": {"budget": {"hard_limit": 0.05}}},
        ).json()["id"]
        client.post(
            f"/jobs/{job_id}/workers/runner",
            json={"state": "done", "cost_usd": 0.10},
        )
        budget = client.get(f"/jobs/{job_id}/status").json()["budget"]
        assert budget["spent"] == pytest.approx(0.10)
        assert budget["outcome"] == "hard_exceeded"
        assert budget["should_stop"] is True


# ---------------------------------------------------------------------------
# Auth & local-only
# ---------------------------------------------------------------------------


class TestAuth:
    def test_missing_token_rejected(self, token_client):
        resp = token_client.get("/jobs")
        assert resp.status_code == 401

    def test_wrong_token_rejected(self, token_client):
        resp = token_client.get("/jobs", headers={"Authorization": "Bearer nope"})
        assert resp.status_code == 401

    def test_correct_token_allowed(self, token_client):
        resp = token_client.get(
            "/jobs", headers={"Authorization": "Bearer secret-abc"}
        )
        assert resp.status_code == 200

    def test_bearer_prefix_required(self, token_client):
        resp = token_client.get(
            "/jobs", headers={"Authorization": "secret-abc"}
        )
        assert resp.status_code == 401


class TestLocalOnly:
    def test_loopback_default_allows_testclient(self, client):
        # TestClient reports peer as "testclient" — explicitly whitelisted.
        assert client.get("/health").status_code == 200

    def test_run_refuses_public_bind_without_opt_in(self, monkeypatch):
        monkeypatch.delenv("HERMES_ORCHESTRATOR_API_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="allow_public_bind"):
            run(host="0.0.0.0", port=12345)

    def test_run_refuses_public_bind_without_token(self, monkeypatch):
        monkeypatch.delenv("HERMES_ORCHESTRATOR_API_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="non-loopback"):
            run(host="0.0.0.0", port=12345, allow_public_bind=True)


# ---------------------------------------------------------------------------
# WebSocket /jobs/{job_id}/events
# ---------------------------------------------------------------------------


class TestWebSocketEvents:
    def test_ws_replays_history_on_connect(self, client):
        job_id = client.post("/jobs", json={"name": "ws"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            envelope = ws.receive_json()
            assert envelope["event"] == EVENT_JOB_CREATED
            assert envelope["job_id"] == job_id

    def test_ws_streams_live_events(self, client):
        job_id = client.post("/jobs", json={"name": "ws2"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            # drain history
            ws.receive_json()
            # Resume emits phase.changed then worker.started.
            client.post(f"/jobs/{job_id}/resume")
            phase_envelope = ws.receive_json()
            assert phase_envelope["event"] == "phase.changed"
            worker_envelope = ws.receive_json()
            assert worker_envelope["event"] == EVENT_WORKER_STARTED

    def test_ws_validation_and_publish_events(self, client):
        job_id = client.post("/jobs", json={"name": "ws3"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            ws.receive_json()  # job.created
            client.post(f"/jobs/{job_id}/validate", json={"x": 1})
            assert ws.receive_json()["event"] == "phase.changed"
            assert ws.receive_json()["event"] == EVENT_VALIDATION_COMPLETED
            client.post(f"/jobs/{job_id}/publish-plan", json={"channel": "beta"})
            assert ws.receive_json()["event"] == "phase.changed"
            assert ws.receive_json()["event"] == EVENT_PUBLISH_READY

    def test_ws_rejects_missing_token(self):
        app = create_app(token="secret")
        with TestClient(app) as c:
            # Create a job using the right token.
            resp = c.post(
                "/jobs",
                json={"name": "secured"},
                headers={"Authorization": "Bearer secret"},
            )
            job_id = resp.json()["id"]
            # Connect without ?token=
            import websockets  # noqa: F401  (transitively used by starlette)
            from starlette.websockets import WebSocketDisconnect as WSD
            with pytest.raises(WSD):
                with c.websocket_connect(f"/jobs/{job_id}/events"):
                    pass

    def test_ws_unknown_job_closes(self, client):
        from starlette.websockets import WebSocketDisconnect as WSD
        with pytest.raises(WSD):
            with client.websocket_connect("/jobs/missing-id/events"):
                pass


# ---------------------------------------------------------------------------
# Sanity check: the module exposes the expected public surface.
# ---------------------------------------------------------------------------


def test_module_public_api():
    expected = {
        "ALL_EVENTS",
        "DEFAULT_HOST",
        "DEFAULT_PORT",
        "EVENT_APPROVAL_REQUESTED",
        "EVENT_ERROR",
        "EVENT_EVIDENCE_UPDATED",
        "EVENT_JOB_CREATED",
        "EVENT_JOB_FAILED",
        "EVENT_PHASE_CHANGED",
        "EVENT_PUBLISH_READY",
        "EVENT_SCORING_COMPLETED",
        "EVENT_VALIDATION_COMPLETED",
        "EVENT_WORKER_BLOCKED",
        "EVENT_WORKER_COMPLETED",
        "EVENT_WORKER_HEARTBEAT",
        "EVENT_WORKER_STARTED",
        "EventBroker",
        "Job",
        "JobStore",
        "create_app",
        "run",
    }
    assert expected.issubset(set(orchestrator_api.__all__))
    assert orchestrator_api.DEFAULT_HOST == "127.0.0.1"
