"""Tests for the vercel plugin — read tools + the owner-gated write ladder.

All HTTP is served by an ``httpx.MockTransport`` so nothing touches the network.
"""

from __future__ import annotations

import json

import httpx
import pytest

from plugins.vercel import config as vcfg
from plugins.vercel import tools as vtools
from plugins.vercel.client import VercelClient, sanitize_error

PHRASE = "Yes, with authorization."


def _client(handler) -> VercelClient:
    return VercelClient(
        token="tok", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def _set_cfg(monkeypatch, **kw) -> vcfg.VercelConfig:
    cfg = vcfg.VercelConfig(**kw)
    monkeypatch.setattr(vtools.vercel_config, "load_config", lambda: cfg)
    return cfg


# -- redaction --------------------------------------------------------------


def test_sanitize_error_redacts_bearer_and_header():
    assert "secrettoken12345678" not in sanitize_error("Bearer secrettoken12345678")
    assert "REDACTED" in sanitize_error("Authorization: Bearer abc123def456ghi789")


# -- read -------------------------------------------------------------------


def test_list_projects_parses(monkeypatch):
    _set_cfg(monkeypatch, enabled=True)

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v9/projects"
        assert req.headers["authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={
                "projects": [
                    {"id": "prj_1", "name": "app", "framework": "next", "updatedAt": 1}
                ]
            },
        )

    monkeypatch.setattr(vtools, "_require_client", lambda: _client(handler))
    out = json.loads(vtools.handle_list_projects({}))
    assert out["success"] is True
    assert out["projects"][0]["name"] == "app"


def test_read_disabled_by_default(monkeypatch):
    _set_cfg(monkeypatch, enabled=False)
    out = json.loads(vtools.handle_list_projects({}))
    assert out["success"] is False
    assert out["error"] == "plugin_disabled"


def test_preview_url_allowlist_blocks(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allowed_projects=("other",))
    out = json.loads(vtools.handle_get_preview_url({"project": "app"}))
    assert out["error"] == "project_not_allowed"


def test_read_no_token(monkeypatch):
    _set_cfg(monkeypatch, enabled=True)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    out = json.loads(vtools.handle_list_projects({}))
    assert out["success"] is False
    assert out["error"] == "no_token"


# -- write ladder -----------------------------------------------------------


def test_set_env_writes_disabled(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=False)
    out = json.loads(
        vtools.handle_set_env({"project": "app", "key": "K", "value": "SuperSecretVal"})
    )
    assert out["success"] is False
    assert out["error"] == "writes_disabled"
    assert out["executed"] is False
    assert "verdict" in out
    # The value must never appear anywhere in the response.
    assert "SuperSecretVal" not in json.dumps(out)


def test_set_env_approval_required(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    out = json.loads(
        vtools.handle_set_env({"project": "app", "key": "K", "value": "SuperSecretVal"})
    )
    assert out["success"] is True
    assert out["executed"] is False
    assert out["approval_required"] is True
    assert out["verdict"]["tier"] == "ask"
    assert out["verdict"]["required_owner_phrase"] == PHRASE
    assert "SuperSecretVal" not in json.dumps(out)


def _boom():
    raise RuntimeError("_require_client must not be called for a propose-only write")


def test_set_env_propose_only_never_executes(monkeypatch):
    # Even with allow_writes and a phrase supplied, the tool never mutates and
    # never reaches the client — the model cannot self-authorize a write.
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(vtools, "_require_client", _boom)
    out = json.loads(
        vtools.handle_set_env({
            "project": "app",
            "key": "K",
            "value": "SuperSecretVal",
            "target": ["preview"],
            "authorization": PHRASE,  # ignored — not a real gate
        })
    )
    assert out["success"] is True
    assert out["executed"] is False
    assert out["approval_required"] is True
    assert out["verdict"]["tier"] == "ask"
    assert out["verdict"]["required_owner_phrase"] == PHRASE
    # value never echoed anywhere
    assert "SuperSecretVal" not in json.dumps(out)


def test_deploy_bad_hook_url(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    out = json.loads(
        vtools.handle_deploy({
            "project": "app",
            "deploy_hook_url": "https://evil.example/hook",
        })
    )
    assert out["success"] is False
    assert out["error"] == "bad_args"


def test_deploy_propose_only(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(vtools, "_require_client", _boom)
    hook = "https://api.vercel.com/v1/integrations/deploy/prj_abc/secrettoken"
    out = json.loads(vtools.handle_deploy({"project": "app", "deploy_hook_url": hook}))
    assert out["executed"] is False
    assert out["approval_required"] is True
    # the deploy-hook URL is a capability token — never echoed back
    assert "secrettoken" not in json.dumps(out)


def test_cancel_deployment_propose_only(monkeypatch):
    _set_cfg(monkeypatch, enabled=True, allow_writes=True)
    monkeypatch.setattr(vtools, "_require_client", _boom)
    out = json.loads(
        vtools.handle_cancel_deployment({"project": "app", "deployment_id": "dpl_1"})
    )
    assert out["executed"] is False
    assert out["approval_required"] is True
    assert out["proposed"]["deployment_id"] == "dpl_1"


# -- requirements gate ------------------------------------------------------


def test_check_requirements(monkeypatch):
    _set_cfg(monkeypatch, enabled=True)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    assert vtools.check_vercel_requirements() is False
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    assert vtools.check_vercel_requirements() is True


def test_check_requirements_disabled(monkeypatch):
    _set_cfg(monkeypatch, enabled=False)
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    assert vtools.check_vercel_requirements() is False
