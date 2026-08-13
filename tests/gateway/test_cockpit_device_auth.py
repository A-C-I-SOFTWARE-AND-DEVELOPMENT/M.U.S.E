"""The cockpit bearer gate accepts EITHER credential path.

Regression + coverage for the additive per-device auth path: the shared
cockpit token keeps working exactly as before, a freshly paired device
token authenticates a protected route, a revoked device token is refused,
and a missing/garbage token still 401s. Hermetic: the real stdlib server
on a random loopback port with a tmp HERMES_HOME and a known shared token.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import auth as cockpit_auth
from gateway.cockpit import device_pairing as dp
from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-123"

# A protected (auth-required) GET route to probe the gate with.
PROTECTED = "/v1/cockpit/runtime/status"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get_status(server, path: str, token: str | None) -> int:
    """GET *path* with an optional bearer token; return the HTTP status.

    Raised HTTPErrors (401/4xx) are unwrapped to their status code so each
    test can assert on the number directly.
    """
    req = urllib.request.Request(_url(server, path), method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _pair_device(server) -> str:
    """Pair a new device through the public routes; return its raw token."""
    host, port = server.server_address

    def _post(path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"http://{host}:{port}{path}", data=data, method="POST"
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())

    start = _post("/v1/cockpit/pair/start", {"device_name": "Pixel"})
    confirm = _post(
        "/v1/cockpit/pair/confirm",
        {
            "pairing_id": start["pairing_id"],
            "pairing_code": start["pairing_code"],
            "authorization": "Yes, with authorization.",
        },
    )
    return confirm["token"]


# ---------------------------------------------------------------------------
# the gate accepts BOTH paths (HTTP, end to end)
# ---------------------------------------------------------------------------


def test_shared_token_still_authenticates(server) -> None:
    # The original path is unchanged: the shared token opens a protected route.
    assert _get_status(server, PROTECTED, token=TOKEN) == 200


def test_paired_device_token_authenticates(server) -> None:
    device_token = _pair_device(server)
    # A per-device token (not the shared token) now opens the same route.
    assert device_token != TOKEN
    assert _get_status(server, PROTECTED, token=device_token) == 200


def test_revoked_device_token_is_401(server) -> None:
    device_token = _pair_device(server)
    device_id = dp.verify_device_token(device_token)
    assert device_id is not None
    assert dp.revoke_device(device_id) is True
    # A revoked device's token must NOT authenticate.
    assert _get_status(server, PROTECTED, token=device_token) == 401


def test_no_token_is_401(server) -> None:
    assert _get_status(server, PROTECTED, token=None) == 401


def test_garbage_token_is_401(server) -> None:
    # Neither the shared token nor any paired device.
    assert _get_status(server, PROTECTED, token="not-a-real-token") == 401


def test_revoking_one_device_is_scoped_mid_flight(server, monkeypatch) -> None:
    """Revocation cuts off exactly one device, mid-session, and nothing else.

    Two devices are paired and both authenticate (the "in-flight" state).
    Revoking device A must 401 A's very next request while device B and the
    shared token keep working — proving revocation is per-device, not global.
    """
    # Pair two devices back-to-back: relax only the inter-pairing rate limit
    # (a separate concern from the scoping behavior under test).
    monkeypatch.setattr(dp, "RATE_LIMIT_SECONDS", 0)
    token_a = _pair_device(server)
    token_b = _pair_device(server)
    assert token_a != token_b

    # Both devices + the shared token are live.
    assert _get_status(server, PROTECTED, token=token_a) == 200
    assert _get_status(server, PROTECTED, token=token_b) == 200
    assert _get_status(server, PROTECTED, token=TOKEN) == 200

    device_a = dp.verify_device_token(token_a)
    assert device_a is not None
    assert dp.revoke_device(device_a) is True

    # A is cut off immediately; B and the shared token are unaffected.
    assert _get_status(server, PROTECTED, token=token_a) == 401
    assert _get_status(server, PROTECTED, token=token_b) == 200
    assert _get_status(server, PROTECTED, token=TOKEN) == 200


# ---------------------------------------------------------------------------
# authorize_bearer unit behavior (no server, no header parsing)
# ---------------------------------------------------------------------------


def test_authorize_bearer_shared_token(home: Path) -> None:
    assert cockpit_auth.authorize_bearer(TOKEN, TOKEN) is True


def test_authorize_bearer_none_and_empty(home: Path) -> None:
    assert cockpit_auth.authorize_bearer(None, TOKEN) is False
    assert cockpit_auth.authorize_bearer("", TOKEN) is False
    # Wrong token, with no devices paired, is refused.
    assert cockpit_auth.authorize_bearer("wrong", TOKEN) is False


def test_authorize_bearer_device_token_without_shared(home: Path) -> None:
    # Even when there is NO shared token configured (expected=None), a valid
    # per-device token still authorizes — the two paths are independent.
    start = dp.start_pairing("phone")
    assert start is not None
    confirm = dp.confirm_pairing(start.pairing_code, start.pairing_id)
    assert confirm is not None
    assert cockpit_auth.authorize_bearer(confirm.token, None) is True
    # ...and a revoked device's token does not.
    assert dp.revoke_device(confirm.device_id) is True
    assert cockpit_auth.authorize_bearer(confirm.token, None) is False
