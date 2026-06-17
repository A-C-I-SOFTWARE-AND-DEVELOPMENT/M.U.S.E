"""Cockpit Second Brain routes — status + retrieve (read-only).

Exercises the handlers directly with a constructed Request and a fake bridge, so
no database is needed. Confirms the read-only retrieval surface degrades honestly
(disabled / unavailable / no-hits) and never leaks the backend password.
"""

from __future__ import annotations

import json

from gateway.cockpit.handlers import (
    Request,
    second_brain_retrieve,
    second_brain_status,
)
from hermes_cli.jarvis_prime import second_brain_bridge as sbb
from hermes_cli.jarvis_prime.second_brain_bridge import RetrievedContext


def _req(**query) -> Request:
    return Request(method="GET", path="/v1/cockpit/second-brain", query=dict(query))


def test_status_reports_enabled_available_and_backend(monkeypatch):
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    resp = second_brain_status(_req())
    assert resp.status == 200
    assert resp.payload["enabled"] is True
    assert resp.payload["available"] is True  # module importable in-repo
    assert resp.payload["settings"]["backend"] in {"postgres", "memory"}
    assert "password" not in json.dumps(resp.payload)  # never leak it


def test_retrieve_requires_query():
    assert second_brain_retrieve(_req()).status == 400


def test_retrieve_disabled_is_honest(monkeypatch):
    monkeypatch.delenv("MUSE_SECOND_BRAIN", raising=False)
    resp = second_brain_retrieve(_req(q="hi"))
    assert resp.status == 200
    assert resp.payload["enabled"] is False
    assert resp.payload["blocks"] == 0


def test_retrieve_returns_fused_context(monkeypatch):
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(
        sbb, "retrieve_optional", lambda q, **k: RetrievedContext(text="FUSED", block_count=3)
    )
    resp = second_brain_retrieve(_req(q="who"))
    assert resp.status == 200
    assert resp.payload == {
        "enabled": True,
        "available": True,
        "backend_ready": True,
        "blocks": 3,
        "text": "FUSED",
        "source": "second_brain",
    }


def test_retrieve_backend_unavailable_is_honest(monkeypatch):
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(sbb, "retrieve_optional", lambda q, **k: None)
    resp = second_brain_retrieve(_req(q="who"))
    assert resp.status == 200
    assert resp.payload["backend_ready"] is False
    assert resp.payload["blocks"] == 0
