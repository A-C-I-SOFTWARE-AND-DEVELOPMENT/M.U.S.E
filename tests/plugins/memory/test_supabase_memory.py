"""Tests for the Supabase memory provider (recency recall over PostgREST).

HTTP is served by an ``httpx.MockTransport`` injected into the provider, so
nothing touches the network.
"""

from __future__ import annotations

import importlib
import json

import httpx
import pytest

provider_mod = importlib.import_module("plugins.memory.supabase")
SupabaseMemoryProvider = provider_mod.SupabaseMemoryProvider


def _env(monkeypatch, *, url="https://proj.supabase.co", key="anon", table=None):
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_ANON_KEY", key)
    if table is not None:
        monkeypatch.setenv("SUPABASE_MEMORY_TABLE", table)
    else:
        monkeypatch.delenv("SUPABASE_MEMORY_TABLE", raising=False)


def _ready_provider(monkeypatch, handler, **env):
    _env(monkeypatch, **env)
    p = SupabaseMemoryProvider()
    p.initialize("sess-1", platform="cli", hermes_home="/tmp")
    p._client = httpx.Client(transport=httpx.MockTransport(handler))
    return p


def test_name_and_no_tools():
    p = SupabaseMemoryProvider()
    assert p.name == "supabase"
    assert p.get_tool_schemas() == []


def test_is_available(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    assert SupabaseMemoryProvider().is_available() is False
    _env(monkeypatch)
    assert SupabaseMemoryProvider().is_available() is True


def test_initialize_skips_non_primary_context(monkeypatch):
    _env(monkeypatch)
    p = SupabaseMemoryProvider()
    p.initialize("sess-1", platform="cron", agent_context="cron")
    assert p._ready is False
    # primary context activates
    p.initialize("sess-1", platform="cli", agent_context="primary")
    assert p._ready is True


def test_prefetch_formats_recent_turns(monkeypatch):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/rest/v1/hermes_memory"
        assert req.headers["apikey"] == "anon"
        # session filter + ordering applied
        assert req.url.params["session_id"] == "eq.sess-1"
        assert req.url.params["order"] == "created_at.desc"
        return httpx.Response(
            200,
            json=[
                {"user_content": "two", "assistant_content": "B", "created_at": 2},
                {"user_content": "one", "assistant_content": "A", "created_at": 1},
            ],
        )

    p = _ready_provider(monkeypatch, handler)
    out = p.prefetch("anything")
    # oldest-first reconstruction
    assert "User: one" in out
    assert out.index("User: one") < out.index("User: two")
    assert "Supabase memory" in out


def test_prefetch_empty_when_no_rows(monkeypatch):
    p = _ready_provider(monkeypatch, lambda r: httpx.Response(200, json=[]))
    assert p.prefetch("q") == ""


def test_prefetch_silent_on_http_error(monkeypatch):
    p = _ready_provider(monkeypatch, lambda r: httpx.Response(500, text="boom"))
    assert p.prefetch("q") == ""


def test_prefetch_noop_when_not_ready(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    p = SupabaseMemoryProvider()
    p.initialize("s")
    assert p.prefetch("q") == ""


def test_sync_turn_posts_row(monkeypatch):
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return httpx.Response(201, text="")

    p = _ready_provider(monkeypatch, handler)
    p.sync_turn("hi", "hello", session_id="sess-9")
    assert seen["method"] == "POST"
    assert seen["path"] == "/rest/v1/hermes_memory"
    assert seen["body"] == {
        "session_id": "sess-9",
        "user_content": "hi",
        "assistant_content": "hello",
    }


def test_custom_table_name(monkeypatch):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/rest/v1/memories"
        return httpx.Response(200, json=[])

    p = _ready_provider(monkeypatch, handler, table="memories")
    p.prefetch("q")


def test_config_schema_has_env_vars():
    keys = {f["env_var"] for f in SupabaseMemoryProvider().get_config_schema()}
    assert {"SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_MEMORY_TABLE"} <= keys


def test_register_registers_provider():
    captured = {}

    class _Ctx:
        def register_memory_provider(self, provider):
            captured["p"] = provider

    provider_mod.register(_Ctx())
    assert isinstance(captured["p"], SupabaseMemoryProvider)
