"""Tests for the owner-approved action-executor registry and plugin executors.

Covers the registry contract (register / dispatch / idempotency / unknown), the
exact-owner-phrase gate on :func:`apply_owner_approved`, and the Vercel +
Supabase executors driven through that gate (mock HTTP / tmp filesystem).
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx
import pytest

from hermes_cli import action_executors as ax

PHRASE = "Yes, with authorization."


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Snapshot and restore the global registry around each test."""
    saved = dict(ax._REGISTRY)
    try:
        yield
    finally:
        ax._REGISTRY.clear()
        ax._REGISTRY.update(saved)


def test_register_and_dispatch():
    ax.register("t.act", lambda p: {"success": True, "got": p["x"]})
    assert ax.has("t.act")
    assert "t.act" in ax.registered()
    assert ax.dispatch("t.act", {"x": 5}) == {"success": True, "got": 5}


def test_register_idempotent_unless_overwrite():
    ax.register("t.act", lambda p: {"success": True, "v": 1})
    ax.register("t.act", lambda p: {"success": True, "v": 2})  # ignored
    assert ax.dispatch("t.act", {})["v"] == 1
    ax.register("t.act", lambda p: {"success": True, "v": 3}, overwrite=True)
    assert ax.dispatch("t.act", {})["v"] == 3


def test_register_rejects_bad_input():
    with pytest.raises(ValueError):
        ax.register("", lambda p: {})
    with pytest.raises(ValueError):
        ax.register("x", cast(Any, "not-callable"))


def test_dispatch_unknown_raises():
    with pytest.raises(ax.UnknownAction):
        ax.dispatch("nope", {})


def test_apply_owner_approved_requires_exact_phrase():
    ax.register("t.act", lambda p: {"success": True})
    with pytest.raises(ax.NotAuthorized):
        ax.apply_owner_approved("t.act", {}, owner_phrase="yes please")
    with pytest.raises(ax.NotAuthorized):
        ax.apply_owner_approved("t.act", {}, owner_phrase="")
    assert ax.apply_owner_approved("t.act", {}, owner_phrase=PHRASE)["success"] is True


def test_apply_owner_approved_attaches_decision_verdict():
    # Sprint 2 breadth: the out-of-band mutation seam records one canonical
    # verdict (ask tier, owner-gated) into the result envelope, recorded-not-
    # gating. An executor that already set a verdict is left untouched.
    ax.register("t.act", lambda p: {"success": True})
    out = ax.apply_owner_approved("t.act", {}, owner_phrase=PHRASE)
    verdict = out["decision_verdict"]
    assert verdict["tier"] == "ask"
    assert verdict["action_type"] == "executor.t.act"
    assert verdict["required_owner_phrase"] == PHRASE

    ax.register(
        "t.pre",
        lambda p: {"success": True, "decision_verdict": {"tier": "auto"}},
        overwrite=True,
    )
    pre = ax.apply_owner_approved("t.pre", {}, owner_phrase=PHRASE)
    assert pre["decision_verdict"] == {"tier": "auto"}  # not clobbered


def test_vercel_executor_applies_via_owner_approval(monkeypatch):
    from plugins.vercel import executor as vexec
    from plugins.vercel.client import VercelClient

    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"key": "K"})

    def fake_client():
        return VercelClient(
            token="tok",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr(vexec, "_client", fake_client)
    vexec.register_executors()
    out = ax.apply_owner_approved(
        "vercel.set_env",
        {"project": "app", "key": "K", "value": "S3cretVal", "target": ["preview"]},
        owner_phrase=PHRASE,
    )
    assert out["success"] is True
    assert out["executed"] is True
    assert seen["path"] == "/v10/projects/app/env"
    assert seen["body"]["value"] == "S3cretVal"  # sent to the API
    assert "S3cretVal" not in json.dumps(out)  # never echoed back


def test_vercel_executor_no_token_degrades(monkeypatch):
    from plugins.vercel import executor as vexec
    from plugins.vercel.client import VercelClient

    monkeypatch.setattr(vexec, "_client", lambda: VercelClient(token=""))
    vexec.register_executors()
    out = ax.apply_owner_approved(
        "vercel.set_env",
        {"project": "a", "key": "k", "value": "v"},
        owner_phrase=PHRASE,
    )
    assert out["success"] is False
    assert out["error"] == "no_token"


def test_supabase_executor_authors_file(monkeypatch, tmp_path):
    from plugins.supabase import executor as sexec

    monkeypatch.chdir(tmp_path)
    sexec.register_executors()
    out = ax.apply_owner_approved(
        "supabase.apply_migration",
        {"name": "add_profiles", "sql": "create table profiles();"},
        owner_phrase=PHRASE,
    )
    assert out["executed"] is True
    assert out["applied"] is False  # authored only; operator runs `supabase db push`
    files = list((tmp_path / "supabase" / "migrations").glob("*_add_profiles.sql"))
    assert len(files) == 1
    assert "create table profiles();" in files[0].read_text()
