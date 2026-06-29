"""Tests for per-device cockpit pairing (gateway/cockpit/device_pairing).

Two layers, both hermetic (tmp HERMES_HOME, no network, no third-party
deps beyond what the gateway suite already needs):

* Unit tests drive the durable store directly: start -> confirm -> verify
  -> revoke happy path, expired code, bad code, revoked token, and the
  hash-not-raw-at-rest invariant.
* HTTP tests drive the real stdlib cockpit server on a random loopback
  port, exercising the two new public-ish routes (gated like /v1/health).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import device_pairing as dp
from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _post(server, path: str, body: dict, token: str | None = None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read())


# ---------------------------------------------------------------------------
# store unit tests
# ---------------------------------------------------------------------------


def test_start_confirm_verify_revoke_happy_path(home: Path) -> None:
    start = dp.start_pairing("Jeremiah's Pixel")
    assert start is not None
    assert start.pairing_code and start.expires_at > 0

    confirm = dp.confirm_pairing(start.pairing_code)
    assert confirm is not None
    assert confirm.device_id.startswith("dev_")
    assert confirm.token  # the raw token, returned exactly once

    # The raw token authenticates as that device...
    assert dp.verify_device_token(confirm.token) == confirm.device_id

    # ...until it's revoked, after which it never authenticates again.
    assert dp.revoke_device(confirm.device_id) is True
    assert dp.verify_device_token(confirm.token) is None
    # Revoking again is a no-op (already revoked).
    assert dp.revoke_device(confirm.device_id) is False


def test_confirm_consumes_code_single_use(home: Path) -> None:
    start = dp.start_pairing("phone")
    assert start is not None
    first = dp.confirm_pairing(start.pairing_code)
    assert first is not None
    # The code is single-use: a replay returns None.
    assert dp.confirm_pairing(start.pairing_code) is None


def test_expired_code_is_rejected(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    start = dp.start_pairing("slow-device")
    assert start is not None
    # Jump past the TTL: the pending code is pruned and confirm fails.
    real_now = dp._now()
    monkeypatch.setattr(dp, "_now", lambda: real_now + dp.CODE_TTL_SECONDS + 1)
    assert dp.confirm_pairing(start.pairing_code) is None


def test_bad_code_is_rejected(home: Path) -> None:
    dp.start_pairing("device")
    assert dp.confirm_pairing("NOTACODE") is None
    # An empty/whitespace code is also rejected (never mints a token).
    assert dp.confirm_pairing("   ") is None


def test_revoked_token_does_not_authenticate(home: Path) -> None:
    start = dp.start_pairing("revoke-me")
    assert start is not None
    confirm = dp.confirm_pairing(start.pairing_code)
    assert confirm is not None
    assert dp.verify_device_token(confirm.token) == confirm.device_id
    dp.revoke_device(confirm.device_id)
    assert dp.verify_device_token(confirm.token) is None
    # list_devices reflects the tombstone, without exposing token material.
    devices = {d["device_id"]: d for d in dp.list_devices()}
    assert devices[confirm.device_id]["revoked"] is True
    blob = json.dumps(devices)
    assert confirm.token not in blob


def test_token_hashed_at_rest_never_raw(home: Path) -> None:
    start = dp.start_pairing("at-rest")
    assert start is not None
    confirm = dp.confirm_pairing(start.pairing_code)
    assert confirm is not None

    raw_store = dp._devices_path().read_text(encoding="utf-8")
    # The raw token is NEVER on disk; only its sha256 hash is.
    assert confirm.token not in raw_store
    assert "sha256:" in raw_store
    # The stored hash matches the documented hashing of the raw token.
    from hermes_cli import cockpit_token

    assert cockpit_token.hash_token(confirm.token) in raw_store


def test_rate_limit_blocks_rapid_start(home: Path) -> None:
    first = dp.start_pairing("a")
    assert first is not None
    # A second immediate start is rate-limited (None), not a second code.
    assert dp.start_pairing("b") is None


def test_lockout_after_repeated_bad_confirms(home: Path) -> None:
    # Seed a pending code so a valid code exists, then exhaust the failure
    # budget with bad guesses; once locked out even the good code is refused.
    start = dp.start_pairing("victim")
    assert start is not None
    for _ in range(dp.MAX_FAILED_CONFIRMS):
        assert dp.confirm_pairing("WRONGCDE") is None
    assert dp.confirm_pairing(start.pairing_code) is None  # locked out


def test_store_survives_corrupt_line(home: Path) -> None:
    start = dp.start_pairing("durable")
    assert start is not None
    confirm = dp.confirm_pairing(start.pairing_code)
    assert confirm is not None
    # A torn/garbage line must not crash the loader; the device still verifies.
    path = dp._devices_path()
    path.write_text(path.read_text(encoding="utf-8") + "{not json\n", encoding="utf-8")
    assert dp.verify_device_token(confirm.token) == confirm.device_id


# ---------------------------------------------------------------------------
# HTTP route tests (real stdlib server)
# ---------------------------------------------------------------------------


def test_pair_routes_need_no_shared_token(server) -> None:
    # Gated like /v1/health: a brand-new device with no shared token can pair.
    status, payload = _post(server, "/v1/cockpit/pair/start", {"device_name": "Pixel"})
    assert status == 201
    assert payload["pairing_code"]
    assert payload["expires_at"] > 0

    status, payload = _post(
        server,
        "/v1/cockpit/pair/confirm",
        {
            "pairing_code": payload["pairing_code"],
            "authorization": "Yes, with authorization.",
        },
    )
    assert status == 201
    assert payload["device_id"].startswith("dev_")
    token = payload["token"]
    assert token

    # The freshly-minted per-device token authenticates against the store.
    assert dp.verify_device_token(token) == payload["device_id"]


def test_pair_confirm_requires_code(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/pair/confirm", {})
    assert exc.value.code == 400


def test_pair_confirm_bad_code_is_401(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/pair/confirm",
            {"pairing_code": "NOPE2345", "authorization": "Yes, with authorization."},
        )
    assert exc.value.code == 401


def test_pair_confirm_skips_owner_phrase_on_loopback(server) -> None:
    # Loopback-only cockpit (default): the owner phrase is NOT required to mint a
    # device token — anything that can reach 127.0.0.1 is already on the device,
    # so the phrase was friction without security benefit. Enabling CORS for the
    # public cockpit does NOT add the phrase; a valid code with a wrong/absent
    # phrase still pairs. (Exposing the gateway off-device uses --allow-external,
    # which restores the phrase — see the next test.)
    status, payload = _post(server, "/v1/cockpit/pair/start", {"device_name": "Pixel"})
    assert status == 201
    status, payload = _post(
        server,
        "/v1/cockpit/pair/confirm",
        {"pairing_code": payload["pairing_code"], "authorization": "nope"},
    )
    assert status == 201
    assert payload["device_id"].startswith("dev_")
    assert payload["token"]


def test_pair_confirm_requires_owner_phrase_when_external(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Remote-reachable cockpit (--allow-external): the owner phrase IS enforced,
    # so a remote caller can never self-issue a credential. A valid code with the
    # wrong phrase is 403; the same code with the exact phrase then pairs (the
    # 403 short-circuits before the code is consumed, so it isn't burned).
    monkeypatch.setattr("gateway.cockpit.handlers._ALLOW_REMOTE_EXECUTE", True)
    status, start = _post(server, "/v1/cockpit/pair/start", {"device_name": "Pixel"})
    assert status == 201
    code = start["pairing_code"]

    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/pair/confirm",
            {"pairing_code": code, "authorization": "nope"},
        )
    assert exc.value.code == 403

    status, payload = _post(
        server,
        "/v1/cockpit/pair/confirm",
        {"pairing_code": code, "authorization": "Yes, with authorization."},
    )
    assert status == 201
    assert payload["token"]


def test_pair_start_rate_limited_is_429(server) -> None:
    status, _ = _post(server, "/v1/cockpit/pair/start", {"device_name": "first"})
    assert status == 201
    # The immediate second start is refused with an honest 429, not a code.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/pair/start", {"device_name": "second"})
    assert exc.value.code == 429


def test_existing_shared_token_route_still_guarded(server) -> None:
    # Regression guard: adding the public pairing routes must NOT loosen auth
    # on the rest of the API. A protected route still rejects a missing token.
    req = urllib.request.Request(
        _url(server, "/v1/cockpit/runtime/status"), method="GET"
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 401
