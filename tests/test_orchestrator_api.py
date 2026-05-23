"""Tests for hermes_cli.orchestrator_api — local-only orchestrator backend."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hermes_cli import orchestrator_api  # noqa: E402
from hermes_cli.orchestrator_api import (  # noqa: E402
    ALL_EVENTS,
    EVENT_EVIDENCE_UPDATED,
    EVENT_JOB_CREATED,
    EVENT_PUBLISH_READY,
    EVENT_VALIDATION_COMPLETED,
    EVENT_WORKER_STARTED,
    JobStore,
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
        "evidence.updated",
        "worker.started",
        "worker.blocked",
        "worker.completed",
        "scoring.completed",
        "validation.completed",
        "publish.ready",
        "job.failed",
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
        for action in ("resume", "cancel", "validate", "publish-plan"):
            resp = client.post(f"/jobs/missing/{action}", json={})
            assert resp.status_code == 404, action


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
            # Trigger a fresh event via HTTP and expect to see it stream.
            client.post(f"/jobs/{job_id}/resume")
            envelope = ws.receive_json()
            assert envelope["event"] == EVENT_WORKER_STARTED

    def test_ws_validation_and_publish_events(self, client):
        job_id = client.post("/jobs", json={"name": "ws3"}).json()["id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as ws:
            ws.receive_json()  # job.created
            client.post(f"/jobs/{job_id}/validate", json={"x": 1})
            assert ws.receive_json()["event"] == EVENT_VALIDATION_COMPLETED
            client.post(f"/jobs/{job_id}/publish-plan", json={"channel": "beta"})
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
        "EVENT_EVIDENCE_UPDATED",
        "EVENT_JOB_CREATED",
        "EVENT_JOB_FAILED",
        "EVENT_PUBLISH_READY",
        "EVENT_SCORING_COMPLETED",
        "EVENT_VALIDATION_COMPLETED",
        "EVENT_WORKER_BLOCKED",
        "EVENT_WORKER_COMPLETED",
        "EVENT_WORKER_STARTED",
        "Job",
        "JobStore",
        "create_app",
        "run",
    }
    assert expected.issubset(set(orchestrator_api.__all__))
    assert orchestrator_api.DEFAULT_HOST == "127.0.0.1"
