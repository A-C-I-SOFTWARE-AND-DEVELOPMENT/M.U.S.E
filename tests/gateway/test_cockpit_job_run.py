"""Tests for the gated execute-dispatch endpoint (job_run).

This is the bridge that lets the app run agentic worker lanes (Codex/Claude
execute). The security-critical behavior is the double gate: owner phrase +
loopback-only. We exercise the gates at the handler level and stub the actual
dispatch so tests never shell out to a real CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from hermes_cli import orchestrator as orch
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    # default guard state (loopback → execute allowed behind the phrase)
    h.configure_runtime(allow_remote_execute=False)
    return tmp_path


def _req(job_id: str, **body) -> h.Request:
    return h.Request(method="POST", path="x", body=body, path_params={"id": job_id})


def test_run_unknown_job_404(home) -> None:
    resp = h.job_run(_req("nope", worker_id="hermes-local-planner"))
    assert resp.status == 404


def test_run_unknown_worker_400(home) -> None:
    job = orch.submit_job("do a thing")
    resp = h.job_run(_req(job.id, worker_id="not-a-worker"))
    assert resp.status == 400


def test_execute_lane_blocked_without_owner_phrase(home) -> None:
    job = orch.submit_job("edit the uploader")
    resp = h.job_run(_req(job.id, worker_id="codex-execute"))  # no authorization
    assert resp.status == 403
    assert "owner approval" in resp.payload["error"]
    assert AUTHORIZATION_PHRASE in resp.payload["hint"]


def test_execute_lane_blocked_on_non_loopback(home, monkeypatch) -> None:
    h.configure_runtime(allow_remote_execute=True)  # simulate --allow-external
    job = orch.submit_job("edit the uploader")
    # Even WITH the correct phrase, a non-loopback cockpit refuses execute.
    resp = h.job_run(
        _req(job.id, worker_id="claude-execute", authorization=AUTHORIZATION_PHRASE)
    )
    assert resp.status == 403
    assert "non-loopback" in resp.payload["error"]


def test_execute_lane_runs_with_phrase_and_grants_phase(home, monkeypatch) -> None:
    job = orch.submit_job("edit the uploader")
    approved: list[str] = []
    dispatched: list[str] = []

    def fake_approve(job_id, phase):
        approved.append(phase)
        return orch.get_job(job_id)

    def fake_dispatch(job_id, *, worker_id, repo_root=None):
        dispatched.append(worker_id)
        return orch.get_job(job_id)

    monkeypatch.setattr(orch, "approve_phase", fake_approve)
    monkeypatch.setattr(orch, "dispatch_job", fake_dispatch)

    resp = h.job_run(
        _req(job.id, worker_id="codex-execute", authorization=AUTHORIZATION_PHRASE)
    )
    assert resp.status == 200
    assert approved == ["execute"]  # owner phrase granted the execute phase
    assert dispatched == ["codex-execute"]  # then dispatched the lane
    assert "job" in resp.payload and "worker_trail" in resp.payload


def test_ungated_lane_runs_without_phrase(home, monkeypatch) -> None:
    job = orch.submit_job("look around")
    dispatched: list[str] = []

    def fake_dispatch(job_id, *, worker_id, repo_root=None):
        dispatched.append(worker_id)
        return orch.get_job(job_id)

    monkeypatch.setattr(orch, "dispatch_job", fake_dispatch)
    # local planner is non-destructive (requires_approval=False) → no phrase needed
    resp = h.job_run(_req(job.id, worker_id="hermes-local-planner"))
    assert resp.status == 200
    assert dispatched == ["hermes-local-planner"]
