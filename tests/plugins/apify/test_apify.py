"""apify plugin — registration, gating, config, handlers, redaction (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.apify as plugin_pkg
import plugins.apify.client as apify_client
import plugins.apify.config as apify_config
import plugins.apify.tools as tools


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        apify_config,
        "load_config",
        lambda: apify_config.ApifyConfig(enabled=True),
    )


@pytest.fixture
def enabled_with_runs(monkeypatch):
    monkeypatch.setattr(
        apify_config,
        "load_config",
        lambda: apify_config.ApifyConfig(enabled=True, allow_runs=True),
    )


@pytest.fixture
def with_token(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "apify_api_test123456789")


# ── registration ─────────────────────────────────────────────────────────────


def test_register_emits_four_tools_under_apify_toolset():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    names = [c["name"] for c in captured]
    assert names == [
        "apify_list_actors",
        "apify_get_dataset_items",
        "apify_get_run",
        "apify_run_actor",
    ]
    assert all(c["toolset"] == "apify" for c in captured)
    assert all(c["requires_env"] == ["APIFY_TOKEN"] for c in captured)
    by_name = {c["name"]: c for c in captured}
    # The run tool must carry a STRICTER gate than the read tools.
    assert by_name["apify_list_actors"]["check_fn"] is tools.check_apify_read
    assert by_name["apify_run_actor"]["check_fn"] is tools.check_apify_runs


def test_schemas_have_required_fields():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    for c in captured:
        s = c["schema"]
        assert s["name"] == c["name"]
        assert s["description"]
        assert s["parameters"]["type"] == "object"
        assert "properties" in s["parameters"]


# ── per-tool gating ──────────────────────────────────────────────────────────


def test_read_tools_hidden_without_token(enabled, monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert tools.check_apify_read() is False


def test_read_tools_visible_with_token(enabled, with_token):
    assert tools.check_apify_read() is True


def test_run_tool_hidden_unless_allow_runs(enabled, with_token):
    # enabled + token, but allow_runs defaults False → run tool stays hidden.
    assert tools.check_apify_read() is True
    assert tools.check_apify_runs() is False


def test_run_tool_visible_when_allowed(enabled_with_runs, with_token):
    assert tools.check_apify_runs() is True


# ── run refusal path ─────────────────────────────────────────────────────────


def test_run_actor_refuses_when_runs_disabled(enabled, with_token):
    out = _parse(tools.handle_run_actor({"actor_id": "apify/web-scraper"}))
    assert out["success"] is False
    assert out["error"] == "runs_disabled"


def test_run_actor_enforces_allowlist(monkeypatch, with_token):
    monkeypatch.setattr(
        apify_config,
        "load_config",
        lambda: apify_config.ApifyConfig(
            enabled=True,
            allow_runs=True,
            allowed_actors=("apify~website-content-crawler",),
        ),
    )
    out = _parse(tools.handle_run_actor({"actor_id": "evil/scraper"}))
    assert out["error"] == "actor_not_allowed"


def test_run_actor_rejects_bad_actor_id(enabled_with_runs, with_token):
    out = _parse(tools.handle_run_actor({"actor_id": "../../etc/passwd"}))
    assert out["error"] == "bad_request"


def test_disabled_plugin_short_circuits(monkeypatch):
    monkeypatch.setattr(
        apify_config, "load_config", lambda: apify_config.ApifyConfig(enabled=False)
    )
    out = _parse(tools.handle_list_actors({}))
    assert out["error"] == "plugin_disabled"


# ── happy paths (client mocked, no network) ──────────────────────────────────


def test_list_actors_slims_user_actors(enabled, with_token, monkeypatch):
    fake = MagicMock()
    fake.has_token.return_value = True
    fake.list_actors.return_value = {
        "success": True,
        "payload": {
            "data": {
                "total": 1,
                "items": [
                    {
                        "id": "abc123",
                        "username": "me",
                        "name": "my-scraper",
                        "title": "My Scraper",
                        "description": "scrapes",
                        "stats": {"totalRuns": 7},
                        "heavyInternalField": "ignored",
                    }
                ],
            }
        },
    }
    monkeypatch.setattr(tools, "ApifyClient", lambda: fake)
    out = _parse(tools.handle_list_actors({}))
    assert out["success"] is True
    assert out["source"] == "user"
    actor = out["actors"][0]
    assert actor["slug"] == "me/my-scraper"
    assert actor["total_runs"] == 7
    assert "heavyInternalField" not in actor


def test_list_actors_search_hits_store(enabled, with_token, monkeypatch):
    fake = MagicMock()
    fake.has_token.return_value = True
    fake.search_store.return_value = {
        "success": True,
        "payload": {"data": {"total": 1, "items": [{"id": "x", "name": "n"}]}},
    }
    monkeypatch.setattr(tools, "ApifyClient", lambda: fake)
    out = _parse(tools.handle_list_actors({"search": "instagram"}))
    assert out["source"] == "store"
    fake.search_store.assert_called_once()
    fake.list_actors.assert_not_called()


def test_get_dataset_items_returns_list(enabled, with_token, monkeypatch):
    fake = MagicMock()
    fake.has_token.return_value = True
    fake.dataset_items.return_value = {
        "success": True,
        "payload": [{"url": "http://a"}, {"url": "http://b"}],
    }
    monkeypatch.setattr(tools, "ApifyClient", lambda: fake)
    out = _parse(tools.handle_get_dataset_items({"dataset_id": "ds123"}))
    assert out["success"] is True
    assert out["count"] == 2
    assert out["truncated"] is False


def test_run_actor_happy_path(enabled_with_runs, with_token, monkeypatch):
    fake = MagicMock()
    fake.has_token.return_value = True
    fake.run_actor_sync.return_value = {
        "success": True,
        "payload": [{"title": "page"}],
    }
    monkeypatch.setattr(tools, "ApifyClient", lambda: fake)
    out = _parse(
        tools.handle_run_actor(
            {"actor_id": "apify/web-scraper", "input": {"startUrls": []}}
        )
    )
    assert out["success"] is True
    assert out["actor_id"] == "apify~web-scraper"
    assert out["items"] == [{"title": "page"}]


def test_http_error_is_propagated(enabled, with_token, monkeypatch):
    fake = MagicMock()
    fake.has_token.return_value = True
    fake.run.return_value = {
        "success": False,
        "error": "http_error",
        "status": 404,
        "message": "Apify returned 404: not found",
    }
    monkeypatch.setattr(tools, "ApifyClient", lambda: fake)
    out = _parse(tools.handle_get_run({"run_id": "missing"}))
    assert out["error"] == "http_error"
    assert out["status"] == 404


# ── config parsing ───────────────────────────────────────────────────────────


def test_config_defaults_are_safe():
    cfg = apify_config.from_mapping(None)
    assert cfg.enabled is False
    assert cfg.allow_runs is False
    assert cfg.allowed_actors == ()


def test_config_normalises_allowlist_separator():
    cfg = apify_config.from_mapping(
        {"enabled": True, "allow_runs": True, "allowed_actors": ["apify/web-scraper"]}
    )
    # slash form is stored canonically as tilde, and matches either input form.
    assert cfg.is_actor_allowed("apify~web-scraper") is True
    assert cfg.is_actor_allowed("apify/web-scraper") is True
    assert cfg.is_actor_allowed("other/actor") is False


def test_config_rejects_bad_bool():
    with pytest.raises(apify_config.ConfigError):
        apify_config.from_mapping({"enabled": "maybe"})


def test_validate_actor_id_blocks_traversal():
    with pytest.raises(apify_config.ConfigError):
        apify_config.validate_actor_id("../secrets")


def test_validate_store_id_blocks_slash():
    with pytest.raises(apify_config.ConfigError):
        apify_config.validate_store_id("a/b", label="dataset_id")


# ── redaction ────────────────────────────────────────────────────────────────


def test_sanitize_error_strips_token_shapes():
    msg = "boom apify_api_ABCDEF0123456789 Authorization: Bearer xyz"
    cleaned = apify_client.sanitize_error(msg)
    assert "apify_api_ABCDEF0123456789" not in cleaned
    assert "Bearer xyz" not in cleaned


def test_client_redacts_token_literal_in_transport_error(monkeypatch):
    token = "apify_api_LEAK999999999999"
    monkeypatch.setenv("APIFY_TOKEN", token)
    session = MagicMock()
    import requests

    session.request.side_effect = requests.RequestException(f"failed for {token}")
    client = apify_client.ApifyClient(session=session)
    result = client.list_actors(limit=5)
    assert result["success"] is False
    assert result["error"] == "transport"
    assert token not in result["message"]


def test_client_refuses_without_token(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    client = apify_client.ApifyClient()
    assert client.has_token() is False
    result = client.list_actors(limit=5)
    assert result["error"] == "no_token"
