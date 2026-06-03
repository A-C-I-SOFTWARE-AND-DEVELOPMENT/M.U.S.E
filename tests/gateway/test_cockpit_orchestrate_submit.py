"""Tests for the /v1/cockpit/orchestrate handler (orchestrate_submit).

This is the in-app "give JARVIS a job" entry point. It records an
orchestration job (no workers spawned) and projects it through the canonical
contract so the Jobs surface can render and then run it on a worker lane.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from hermes_cli import orchestrator as orch


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


def _req(**body) -> h.Request:
    return h.Request(method="POST", path="/v1/cockpit/orchestrate", body=body, path_params={})


def test_submit_requires_prompt(home) -> None:
    resp = h.orchestrate_submit(_req())
    assert resp.status == 400
    assert "prompt" in resp.payload["error"]

    resp = h.orchestrate_submit(_req(prompt="   "))
    assert resp.status == 400


def test_submit_records_job_and_projects_contract(home) -> None:
    resp = h.orchestrate_submit(_req(prompt="add a worker-runs view to the cockpit"))
    assert resp.status == 201

    payload = resp.payload
    # Canonical contract shape (orchestrator_job projection).
    assert payload["id"]
    assert payload["title"] == "add a worker-runs view to the cockpit"
    # Contract uppercases status to the canonical CockpitJob enum.
    assert payload["status"] == "QUEUED"
    assert "created_at" in payload and "updated_at" in payload

    # The job is durably recorded — it shows up in the orchestrator store.
    jobs = orch.list_jobs()
    assert any(j.id == payload["id"] for j in jobs)
    assert any(j.prompt == "add a worker-runs view to the cockpit" for j in jobs)


def test_submit_does_not_spawn_workers(home) -> None:
    resp = h.orchestrate_submit(_req(prompt="ship the release"))
    assert resp.status == 201
    job = orch.get_job(resp.payload["id"])
    assert job is not None
    # submit_job never advances past "queued" — workers require explicit dispatch.
    assert job.status == "queued"
