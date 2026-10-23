"""Scoped service credentials and the secret-free model catalog."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import auth
from gateway.cockpit.server import serve
from hermes_cli.inventory import ConfigContext, build_catalog_payload


OWNER_TOKEN = "owner-test-token"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    auth._SEEN_REQUESTS.clear()
    return tmp_path


@pytest.fixture()
def server(home: Path):
    instance = serve(host="127.0.0.1", port=0, token=OWNER_TOKEN)
    yield instance
    instance.shutdown()


def _request(
    server,
    method: str,
    path: str,
    *,
    token: str,
    body: dict | None = None,
    request_id: str = "",
) -> tuple[int, dict]:
    host, port = server.server_address
    data = json.dumps(body or {}).encode() if method == "POST" else None
    req = urllib.request.Request(
        f"http://{host}:{port}{path}", data=data, method=method
    )
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if request_id:
        req.add_header("X-Muse-Request-Id", request_id)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_service_scope_allow_and_default_deny(server) -> None:
    issued = auth.issue_service_token("block-buzz", ["status"])
    assert _request(
        server, "GET", "/v1/cockpit/runtime/status", token=issued.token
    )[0] == 200
    assert _request(
        server, "GET", "/v1/cockpit/models/catalog", token=issued.token
    )[0] == 403
    assert _request(
        server, "GET", "/v1/cockpit/secrets/import", token=issued.token
    )[0] == 403
    assert _request(
        server, "POST", "/v1/agent/chat", token=issued.token, body={"prompt": "x"}
    )[0] == 403


def test_owner_can_issue_but_service_cannot_issue_credentials(server) -> None:
    status, payload = _request(
        server,
        "POST",
        "/v1/cockpit/service-tokens",
        token=OWNER_TOKEN,
        body={"identity": "block-buzz", "scopes": ["catalog"], "ttl_seconds": 60},
    )
    assert status == 201
    assert payload["identity"] == "block-buzz"
    assert payload["scopes"] == ["catalog"]
    assert payload["token"].startswith("muse_svc_")

    status, _ = _request(
        server,
        "POST",
        "/v1/cockpit/service-tokens",
        token=payload["token"],
        body={"identity": "nested", "scopes": ["status"]},
        request_id="buzz-request-0000000001",
    )
    assert status == 403


def test_mutating_service_request_ids_are_single_use(home: Path) -> None:
    principal = auth.verify_service_token(
        auth.issue_service_token("block-buzz", ["jobs"]).token
    )
    assert principal is not None
    request_id = "buzz-request-0000000002"
    assert auth.claim_request_id(principal, request_id) is True
    assert auth.claim_request_id(principal, request_id) is False
    assert auth.claim_request_id(principal, "short") is False


def test_catalog_projection_has_provenance_without_secret_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = ConfigContext("openrouter", "model-a", "", {}, [])
    rows = {
        "provider": "openrouter",
        "model": "model-a",
        "providers": [
            {
                "slug": "openrouter",
                "name": "OpenRouter",
                "models": ["model-a"],
                "total_models": 1,
                "is_current": True,
                "source": "built-in",
                "api_key": "must-not-leak",
                "key_env": "SECRET_ENV",
                "base_url": "https://private.invalid",
            },
            {
                "slug": "anthropic",
                "name": "Anthropic",
                "models": [],
                "total_models": 0,
                "source": "canonical",
            },
        ],
    }
    monkeypatch.setattr("hermes_cli.inventory.build_models_payload", lambda *a, **k: rows)
    payload = build_catalog_payload(ctx)
    encoded = json.dumps(payload)
    assert "must-not-leak" not in encoded
    assert "SECRET_ENV" not in encoded
    assert "private.invalid" not in encoded
    assert payload["source"]["model_catalog"] == "hermes_cli.models"
    assert payload["refresh"]["network_requested"] is False
    assert payload["providers"][0]["entitlement"]["state"] == "configured"
    assert payload["providers"][1]["entitlement"]["state"] == "not_configured"


def test_catalog_endpoint_uses_catalog_scope(server, monkeypatch) -> None:
    monkeypatch.setattr(
        "hermes_cli.inventory.load_picker_context",
        lambda: ConfigContext("", "", "", {}, []),
    )
    monkeypatch.setattr(
        "hermes_cli.inventory.build_catalog_payload",
        lambda _ctx: {
            "providers": [],
            "provider": "",
            "model": "",
            "source": {"module": "hermes_cli.inventory"},
            "refresh": {"network_requested": False},
        },
    )
    token = auth.issue_service_token("block-buzz", ["catalog"]).token
    status, payload = _request(
        server, "GET", "/v1/cockpit/models/catalog", token=token
    )
    assert status == 200
    assert payload["source"]["module"] == "hermes_cli.inventory"


def test_service_token_cannot_run_execute_lane_with_public_phrase(server) -> None:
    """The owner phrase is a public constant, never a factor for services."""
    from hermes_cli import orchestrator as orch
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    job = orch.submit_job("touch nothing")
    issued = auth.issue_service_token("block-buzz", ["jobs"])
    status, payload = _request(
        server,
        "POST",
        f"/v1/cockpit/jobs/{job.id}/run",
        token=issued.token,
        body={"worker_id": "claude-execute", "authorization": AUTHORIZATION_PHRASE},
        request_id="req-execute-0001",
    )
    assert status == 403
    assert "owner credential" in payload["error"]


@pytest.fixture()
def hosted_server(home: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_COCKPIT_HOSTED", "1")
    instance = serve(host="127.0.0.1", port=0, token=OWNER_TOKEN)
    yield instance
    instance.shutdown()


def test_hosted_pairing_requires_owner_credential(hosted_server) -> None:
    # Anonymous callers reach a hosted cockpit over loopback (Caddy + socat),
    # so loopback must not be treated as "already on the device".
    status, _ = _request(
        hosted_server, "POST", "/v1/cockpit/pair/start", token="", body={}
    )
    assert status == 401
    status, _ = _request(
        hosted_server,
        "POST",
        "/v1/cockpit/pair/confirm",
        token="",
        body={"pairing_id": "x", "pairing_code": "ABCD2345"},
    )
    assert status == 401
    status, payload = _request(
        hosted_server,
        "POST",
        "/v1/cockpit/pair/start",
        token=OWNER_TOKEN,
        body={"device_name": "owner phone"},
    )
    assert status == 201
    assert payload["pairing_code"]


def test_local_pairing_stays_open_on_loopback(server) -> None:
    """Default (non-hosted) loopback behavior is unchanged."""
    status, payload = _request(
        server, "POST", "/v1/cockpit/pair/start", token="", body={}
    )
    assert status == 201
    assert payload["pairing_id"]


def test_service_token_cannot_pair_a_device(hosted_server) -> None:
    issued = auth.issue_service_token("block-buzz", ["status", "jobs", "agents"])
    status, _ = _request(
        hosted_server,
        "POST",
        "/v1/cockpit/pair/start",
        token=issued.token,
        body={"device_name": "intruder"},
        request_id="req-pair-0001",
    )
    assert status == 403
