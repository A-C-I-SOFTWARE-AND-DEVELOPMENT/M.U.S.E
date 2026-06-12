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
from muse_cli import orchestrator as orch
from muse_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


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


def test_job_lanes_lists_runnable_lanes_job_run_accepts(home) -> None:
    """The lanes endpoint advertises the ids ``job_run`` validates against."""
    resp = h.job_lanes(h.Request(method="GET", path="x"))
    assert resp.status == 200
    lanes = {lane["id"]: lane for lane in resp.payload["lanes"]}
    # Ids here must be the builtin worker ids (not the detection-lane ids).
    assert "hermes-local-planner" in lanes
    assert "codex-execute" in lanes
    # requires_approval drives the owner-phrase prompt in the app.
    assert lanes["codex-execute"]["requires_approval"] is True
    assert lanes["hermes-local-planner"]["requires_approval"] is False


def test_orchestrate_then_run_roundtrip(home, monkeypatch) -> None:
    """A job created via /orchestrate is immediately runnable by job_run
    (the dispatch→run store split that previously 404'd)."""
    create = h.orchestrate_submit(h.Request(method="POST", path="x", body={"prompt": "edit the uploader"}))
    assert create.status == 201
    job_id = create.payload["id"]
    assert job_id.startswith("orc-")  # orchestrator store, not JobQueue

    dispatched: list[str] = []

    def fake_dispatch(jid, *, worker_id, repo_root=None):
        dispatched.append(worker_id)
        return orch.get_job(jid)

    monkeypatch.setattr(orch, "dispatch_job", fake_dispatch)
    resp = h.job_run(_req(job_id, worker_id="hermes-local-planner"))
    assert resp.status == 200
    assert dispatched == ["hermes-local-planner"]


def test_orchestrate_requires_prompt(home) -> None:
    resp = h.orchestrate_submit(h.Request(method="POST", path="x", body={"prompt": "  "}))
    assert resp.status == 400


def test_navigation_job_filter_survives_recency_cap(home, monkeypatch) -> None:
    """?job= filters before the limit truncation, so an older job's decision
    isn't dropped by the global recency cap (the job-detail bug Codex flagged)."""
    fake_ledger = {
        "orc-old": [{"kind": "navigation_decision", "objective": "old", "created_at": "2026-01-01", "ranked_files": []}],
        "orc-new": [{"kind": "navigation_decision", "objective": "new", "created_at": "2026-02-01", "ranked_files": []}],
    }
    monkeypatch.setattr(orch, "get_ledger", lambda: fake_ledger)

    def _nav(**q):
        return h.navigation_list(h.Request(method="GET", path="x", query=q))

    # Unfiltered surfaces both.
    assert {n["job_id"] for n in _nav().payload["navigations"]} == {"orc-old", "orc-new"}
    # Filtered to the older job returns it even with limit=1 (would be cut otherwise).
    one = _nav(job="orc-old", limit="1")
    assert [n["job_id"] for n in one.payload["navigations"]] == ["orc-old"]
