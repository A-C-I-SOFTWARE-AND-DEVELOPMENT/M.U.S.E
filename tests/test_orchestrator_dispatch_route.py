"""Tests for the owner-gated POST /jobs/{id}/dispatch route (Lane E).

This route is the live caller of the cost producer→consumer seam. The runner is
not actually run here: ``ParallelRunner`` and ``iter_worker_usage`` (as bound in
``orchestrator_dispatch``) are monkeypatched so a synthetic per-worker usage
block is drained into the real ``JobStore``, proving that a subsequent
``GET /status`` stops reading ``cost: 0``. The default-off gate is asserted too.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hermes_cli import orchestrator_api, orchestrator_dispatch  # noqa: E402
from hermes_cli.orchestrator_api import JobStore, create_app  # noqa: E402
from hermes_cli.orchestrator_parallel import WorkerState, WorkerStatus  # noqa: E402

_SPEC = {"workers": [{"worker_id": "w1", "profile": "default", "command": ["true"]}]}


def _patch_runner(monkeypatch, *, usage_block):
    """Replace the runner + usage drain so no real subprocess is spawned."""

    class _FakeRunner:
        def __init__(self, repo, plan, *, runtime_adapter=None, adapter_factory=None):
            self.plan = plan

        def run(self):
            return {
                "w1": WorkerStatus(
                    worker_id="w1",
                    profile="default",
                    mode="local-run",
                    state=WorkerState.COMPLETED,
                    return_code=0,
                )
            }

    monkeypatch.setattr(orchestrator_dispatch, "ParallelRunner", _FakeRunner)
    monkeypatch.setattr(
        orchestrator_dispatch,
        "iter_worker_usage",
        lambda repo, job_id: [("w1", usage_block)] if usage_block else [],
    )


def _make_job(client) -> str:
    resp = client.post("/jobs", json={"name": "cost job", "spec": _SPEC})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_dispatch_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HERMES_ORCHESTRATOR_DISPATCH", raising=False)
    store = JobStore()
    app = create_app(store=store)
    with TestClient(app) as client:
        job_id = _make_job(client)
        resp = client.post(f"/jobs/{job_id}/dispatch")
        assert resp.status_code == 403
        # cost meter untouched — still zero.
        status = client.get(f"/jobs/{job_id}/status").json()
        assert status["cost"]["cost_usd"] == 0


def test_dispatch_drains_cost_into_status(monkeypatch):
    monkeypatch.setenv("HERMES_ORCHESTRATOR_DISPATCH", "1")
    _patch_runner(
        monkeypatch,
        usage_block={
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "cost_usd": 0.25,
            "model": "claude-x",
            "provider": "anthropic",
        },
    )
    store = JobStore()
    app = create_app(store=store)
    with TestClient(app) as client:
        job_id = _make_job(client)
        resp = client.post(f"/jobs/{job_id}/dispatch")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["cost"]["cost_usd"] == pytest.approx(0.25)
        assert "w1" in body["workers"]

        # The drained cost is visible via the canonical /status route too.
        status = client.get(f"/jobs/{job_id}/status").json()
        assert status["cost"]["cost_usd"] == pytest.approx(0.25)
        assert status["cost"]["input_tokens"] == 100
        assert status["cost"]["call_count"] == 1


def test_dispatch_rejects_bad_spec(monkeypatch):
    monkeypatch.setenv("HERMES_ORCHESTRATOR_DISPATCH", "1")
    _patch_runner(monkeypatch, usage_block=None)
    store = JobStore()
    app = create_app(store=store)
    with TestClient(app) as client:
        # A job whose spec has no workers → 400 from the plan builder.
        resp = client.post("/jobs", json={"name": "empty", "spec": {"workers": []}})
        job_id = resp.json()["id"]
        bad = client.post(f"/jobs/{job_id}/dispatch")
        assert bad.status_code == 400


def test_dispatch_unknown_job_404(monkeypatch):
    monkeypatch.setenv("HERMES_ORCHESTRATOR_DISPATCH", "1")
    store = JobStore()
    app = create_app(store=store)
    with TestClient(app) as client:
        resp = client.post("/jobs/does-not-exist/dispatch")
        assert resp.status_code == 404
