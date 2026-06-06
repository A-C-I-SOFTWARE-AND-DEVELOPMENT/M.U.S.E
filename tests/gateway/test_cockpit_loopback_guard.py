"""Loopback-guard coverage for the ``job_approve`` owner-approval route.

``job_approve`` is double-gated exactly like ``job_run``: the owner phrase
*and* a loopback-only guard (refused when the cockpit is bound beyond loopback
via ``--allow-external``). ``test_cockpit_job_run`` covers the guard on the
*execute* lane, but the equally sensitive *approval* route — the one that
grants a gated phase — had no non-loopback coverage. These tests pin that
behavior, including the security-critical ordering: the loopback guard is
checked *before* the owner phrase, so a network-reachable cockpit is refused
even when it presents the correct phrase.
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
    h.configure_runtime(allow_remote_execute=False)  # loopback by default
    return tmp_path


def _approve(job_id: str, **body) -> h.Request:
    return h.Request(method="POST", path="x", body=body, path_params={"id": job_id})


def _orc_job_id() -> str:
    resp = h.orchestrate_submit(
        h.Request(method="POST", path="x", body={"prompt": "edit the uploader"})
    )
    assert resp.status == 201
    return resp.payload["id"]


def test_unknown_job_404_precedes_loopback_guard(home) -> None:
    """``_resolve_job`` runs first: an unknown id is 404 even on non-loopback."""
    h.configure_runtime(allow_remote_execute=True)
    resp = h.job_approve(_approve("nope", authorization=AUTHORIZATION_PHRASE))
    assert resp.status == 404


def test_approve_blocked_on_non_loopback_even_with_phrase(home) -> None:
    """Defense in depth: a non-loopback cockpit is refused *before* the phrase
    check, so the correct phrase cannot grant a gated phase remotely."""
    job_id = _orc_job_id()
    h.configure_runtime(allow_remote_execute=True)  # simulate --allow-external
    resp = h.job_approve(_approve(job_id, authorization=AUTHORIZATION_PHRASE))
    assert resp.status == 403
    assert "non-loopback" in resp.payload["error"]


def test_approve_on_loopback_requires_owner_phrase(home) -> None:
    """On loopback the route still demands the exact owner phrase."""
    job_id = _orc_job_id()
    resp = h.job_approve(_approve(job_id, authorization="please"))
    assert resp.status == 403
    assert "owner approval required" in resp.payload["error"]
    assert AUTHORIZATION_PHRASE in resp.payload["hint"]


def test_approve_succeeds_on_loopback_with_phrase(home, monkeypatch) -> None:
    """Positive control: loopback + exact phrase reaches ``approve_phase`` and
    the guard does not over-block the legitimate path."""
    job_id = _orc_job_id()
    granted: list[str] = []

    def fake_approve(jid, phase):
        granted.append(phase)
        return orch.get_job(jid)

    monkeypatch.setattr(orch, "approve_phase", fake_approve)
    resp = h.job_approve(
        _approve(job_id, phase="execute", authorization=AUTHORIZATION_PHRASE)
    )
    assert resp.status == 200
    assert granted == ["execute"]
