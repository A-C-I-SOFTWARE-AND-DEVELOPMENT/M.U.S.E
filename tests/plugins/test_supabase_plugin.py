"""Tests for the supabase plugin — PostgREST reads + the owner-gated write ladder.

HTTP is served by an ``httpx.MockTransport``; writes only ever author a local
migration file (verified under ``tmp_path``), never a live DB mutation.
"""

from __future__ import annotations

import json

import httpx
import pytest

from plugins.supabase import config as scfg
from plugins.supabase import tools as stools
from plugins.supabase.client import SupabaseClient, sanitize_error

PHRASE = "Yes, with authorization."


def _client(handler) -> SupabaseClient:
    return SupabaseClient(
        url="https://proj.supabase.co",
        anon_key="anon",
        service_role_key="service",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _set_cfg(monkeypatch, **kw) -> scfg.SupabaseConfig:
    cfg = scfg.SupabaseConfig(**kw)
    monkeypatch.setattr(stools.supabase_config, "load_config", lambda: cfg)
    return cfg


# -- redaction --------------------------------------------------------------


def test_sanitize_error_redacts_jwt_and_apikey():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.s1gnatur3value0000"
    assert jwt not in sanitize_error(f"apikey: {jwt}")
    assert "REDACTED" in sanitize_error(f"failed with {jwt}")


# -- read -------------------------------------------------------------------


def test_query_parses_rows(monkeypatch):
    _set_cfg(monkeypatch, enabled=True)

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/rest/v1/profiles"
        assert req.headers["apikey"] == "anon"
        return httpx.Response(200, json=[{"id": 1}, {"id": 2}])

    monkeypatch.setattr(stools, "_require_client", lambda: _client(handler))
    out = json.loads(stools.handle_query({"table": "profiles"}))
    assert out["success"] is True
    assert out["row_count"] == 2


def test_query_disabled(monkeypatch):
    _set_cfg(monkeypatch, enabled=False)
    out = json.loads(stools.handle_query({"table": "profiles"}))
    assert out["error"] == "plugin_disabled"


def test_query_table_not_allowed(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allowed_tables=("posts",))
    monkeypatch.setattr(
        stools,
        "_require_client",
        lambda: _client(lambda r: httpx.Response(200, json=[])),
    )
    out = json.loads(stools.handle_query({"table": "profiles"}))
    assert out["error"] == "table_not_allowed"


def test_query_service_role_disabled(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_service_role=False)
    monkeypatch.setattr(
        stools,
        "_require_client",
        lambda: _client(lambda r: httpx.Response(200, json=[])),
    )
    out = json.loads(
        stools.handle_query({"table": "profiles", "use_service_role": True})
    )
    assert out["error"] == "service_role_disabled"


def test_query_service_role_used_when_allowed(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_service_role=True)

    def handler(req: httpx.Request) -> httpx.Response:
        # service-role key must be used, never the anon key
        assert req.headers["apikey"] == "service"
        return httpx.Response(200, json=[{"id": 1}])

    monkeypatch.setattr(stools, "_require_client", lambda: _client(handler))
    out = json.loads(
        stools.handle_query({"table": "profiles", "use_service_role": True})
    )
    assert out["success"] is True


def test_list_tables(monkeypatch):
    _set_cfg(monkeypatch, enabled=True)

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/rest/v1/"
        return httpx.Response(200, json={"definitions": {"profiles": {}, "posts": {}}})

    monkeypatch.setattr(stools, "_require_client", lambda: _client(handler))
    out = json.loads(stools.handle_list_tables({}))
    assert out["success"] is True
    assert out["tables"] == ["posts", "profiles"]


# -- write ladder (authors local migration files only) ----------------------


def test_execute_sql_writes_disabled(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=False)
    out = json.loads(stools.handle_execute_sql({"sql": "create table x();"}))
    assert out["error"] == "writes_disabled"
    assert out["executed"] is False
    assert "verdict" in out


def test_execute_sql_approval_required(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(stools, "_scan_secrets", lambda _t: [])
    out = json.loads(stools.handle_execute_sql({"sql": "create table x();"}))
    assert out["executed"] is False
    assert out["approval_required"] is True
    assert out["verdict"]["required_owner_phrase"] == PHRASE


def test_execute_sql_propose_only_writes_nothing(monkeypatch, tmp_path):
    # Even with allow_writes and a phrase supplied, nothing is authored on disk.
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(stools, "_scan_secrets", lambda _t: [])
    monkeypatch.chdir(tmp_path)
    out = json.loads(
        stools.handle_execute_sql({
            "sql": "create table x();",
            "name": "make x",
            "authorization": PHRASE,  # ignored — not a real gate
        })
    )
    assert out["success"] is True
    assert out["executed"] is False
    assert out["approval_required"] is True
    assert out["proposed"]["sql"] == "create table x();"
    # nothing was written to disk
    assert not (tmp_path / "supabase").exists()


def test_execute_sql_secret_refused_even_when_authorized(monkeypatch, tmp_path):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(stools, "_scan_secrets", lambda _t: ["embedded credential"])
    monkeypatch.chdir(tmp_path)
    out = json.loads(
        stools.handle_execute_sql({
            "sql": "insert into k values('AKIA...')",
            "authorization": PHRASE,
        })
    )
    assert out["success"] is False
    assert out["error"] == "refused"
    assert out["executed"] is False
    assert out["verdict"]["tier"] == "refuse"
    # nothing was written
    assert not (tmp_path / "supabase" / "migrations").exists()


def test_apply_migration_propose_only_writes_nothing(monkeypatch, tmp_path):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(stools, "_scan_secrets", lambda _t: [])
    monkeypatch.chdir(tmp_path)
    out = json.loads(
        stools.handle_apply_migration({
            "name": "add_profiles",
            "sql": "create table profiles();",
            "authorization": PHRASE,
        })
    )
    assert out["executed"] is False
    assert out["approval_required"] is True
    assert not (tmp_path / "supabase").exists()


def test_check_requirements(monkeypatch):
    _set_cfg(monkeypatch, enabled=True)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    assert stools.check_supabase_requirements() is False
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    assert stools.check_supabase_requirements() is True
