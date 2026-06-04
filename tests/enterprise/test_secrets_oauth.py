"""OAuth2 refresh-token minting path for ``enterprise.secrets``.

Covers the ``grant_type=refresh_token`` exchange wired into
``fetch_secret``: a successful mint, expiry-triggered re-mint, error
responses (4xx/5xx and malformed bodies), and — most importantly — the
safe fallback to the long-lived API key path when no refresh config is
present.

No real network calls: every test injects a fake ``http_post`` and a
fixed ``now`` clock through ``fetch_secret``'s injection points.
"""

from __future__ import annotations

import logging

import pytest

from enterprise.secrets import (
    OAuthRefreshError,
    fetch_secret,
    reset_oauth_token_cache,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


class FakeResponse:
    """Minimal stand-in for an ``httpx.Response`` (status_code + .json())."""

    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class RecordingPost:
    """Callable that records calls and returns a queued response.

    Lets a test both assert on the request (url, form body) and control
    the response, while counting how many times the token endpoint was hit
    (so expiry/caching behaviour is observable).
    """

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, *, data, timeout):
        self.calls.append({"url": url, "data": dict(data), "timeout": timeout})
        if not self._responses:
            raise AssertionError("RecordingPost called more times than queued responses")
        return self._responses.pop(0)

    @property
    def call_count(self) -> int:
        return len(self.calls)


@pytest.fixture
def oauth_env(monkeypatch):
    """Seed a full OAuth refresh config for ``salesforce`` (sales domain).

    Returns a helper to tweak/clear individual keys so tests can exercise
    the "partial config → fall back" branch.
    """
    keys = {
        "SALESFORCE_OAUTH_TOKEN_URL": "https://idp.example.test/oauth2/token",
        "SALESFORCE_OAUTH_CLIENT_ID": "client-abc",
        "SALESFORCE_OAUTH_CLIENT_SECRET": "shh-secret",
        "SALESFORCE_OAUTH_REFRESH_TOKEN": "rt-FAKE-REFRESH-TOKEN",
        "SALESFORCE_OAUTH_SCOPE": "api refresh_token",
    }
    for k, v in keys.items():
        monkeypatch.setenv(k, v)
    return monkeypatch


@pytest.fixture(autouse=True)
def _clear_token_cache():
    """The minted-token cache is process-wide; reset around every test."""
    reset_oauth_token_cache()
    yield
    reset_oauth_token_cache()


# --------------------------------------------------------------------------- #
# Successful refresh
# --------------------------------------------------------------------------- #


def test_successful_refresh_mints_ephemeral_token(oauth_env):
    post = RecordingPost(
        FakeResponse(200, {"access_token": "at-SHORTLIVED-XYZ", "expires_in": 3600})
    )
    bundle = fetch_secret(
        "salesforce",
        caller_role="sales",
        http_post=post,
        now=1_000.0,
    )

    assert bundle.value == "at-SHORTLIVED-XYZ"
    assert bundle.ephemeral is True
    # expires_at = now + expires_in.
    assert bundle.expires_at == 1_000.0 + 3600
    assert not bundle.is_expired(now=1_000.0)

    # The exchange used the standard refresh-token grant with our config.
    assert post.call_count == 1
    body = post.calls[0]["data"]
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == "rt-FAKE-REFRESH-TOKEN"
    assert body["client_id"] == "client-abc"
    assert body["client_secret"] == "shh-secret"
    assert body["scope"] == "api refresh_token"
    assert post.calls[0]["url"] == "https://idp.example.test/oauth2/token"


def test_refresh_without_client_secret_omits_it(monkeypatch):
    # Public / PKCE clients have no secret — the body must not carry one.
    monkeypatch.setenv("SALESFORCE_OAUTH_TOKEN_URL", "https://idp.example.test/token")
    monkeypatch.setenv("SALESFORCE_OAUTH_CLIENT_ID", "public-client")
    monkeypatch.setenv("SALESFORCE_OAUTH_REFRESH_TOKEN", "rt-public")

    post = RecordingPost(FakeResponse(200, {"access_token": "at-1", "expires_in": 600}))
    fetch_secret("salesforce", caller_role="sales", http_post=post, now=0.0)

    body = post.calls[0]["data"]
    assert "client_secret" not in body
    assert "scope" not in body


def test_missing_expires_in_falls_back_to_default_ttl(oauth_env):
    from enterprise.secrets import DEFAULT_TTL_SECONDS

    post = RecordingPost(FakeResponse(200, {"access_token": "at-no-expiry"}))
    bundle = fetch_secret("salesforce", caller_role="sales", http_post=post, now=500.0)
    assert bundle.expires_at == 500.0 + DEFAULT_TTL_SECONDS


# --------------------------------------------------------------------------- #
# Caching + expiry-triggered refresh
# --------------------------------------------------------------------------- #


def test_token_is_cached_and_reused_until_near_expiry(oauth_env):
    post = RecordingPost(
        FakeResponse(200, {"access_token": "at-first", "expires_in": 3600}),
        FakeResponse(200, {"access_token": "at-second", "expires_in": 3600}),
    )

    first = fetch_secret("salesforce", caller_role="sales", http_post=post, now=1_000.0)
    # Well inside the validity window → served from cache, no second POST.
    second = fetch_secret("salesforce", caller_role="sales", http_post=post, now=2_000.0)

    assert first.value == "at-first"
    assert second.value == "at-first"
    assert post.call_count == 1


def test_expiry_triggers_remint(oauth_env):
    post = RecordingPost(
        FakeResponse(200, {"access_token": "at-first", "expires_in": 3600}),
        FakeResponse(200, {"access_token": "at-second", "expires_in": 3600}),
    )

    first = fetch_secret("salesforce", caller_role="sales", http_post=post, now=1_000.0)
    # now is past (expiry - skew): 1000 + 3600 = 4600 expiry; jump beyond it.
    second = fetch_secret("salesforce", caller_role="sales", http_post=post, now=4_600.0)

    assert first.value == "at-first"
    assert second.value == "at-second"
    assert post.call_count == 2


# --------------------------------------------------------------------------- #
# Error responses
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
def test_http_error_status_raises_oauth_error(oauth_env, status):
    post = RecordingPost(FakeResponse(status, {"error": "invalid_grant"}))
    with pytest.raises(OAuthRefreshError):
        fetch_secret("salesforce", caller_role="sales", http_post=post, now=0.0)


def test_transport_exception_raises_oauth_error(oauth_env):
    def boom(url, *, data, timeout):
        raise ConnectionError("dns blew up")

    with pytest.raises(OAuthRefreshError):
        fetch_secret("salesforce", caller_role="sales", http_post=boom, now=0.0)


def test_non_json_body_raises_oauth_error(oauth_env):
    post = RecordingPost(FakeResponse(200, ValueError("not json")))
    with pytest.raises(OAuthRefreshError):
        fetch_secret("salesforce", caller_role="sales", http_post=post, now=0.0)


def test_missing_access_token_raises_oauth_error(oauth_env):
    post = RecordingPost(FakeResponse(200, {"token_type": "Bearer", "expires_in": 60}))
    with pytest.raises(OAuthRefreshError):
        fetch_secret("salesforce", caller_role="sales", http_post=post, now=0.0)


def test_malformed_token_with_newline_is_rejected_and_not_cached(oauth_env):
    # A token with an embedded newline is malformed. It must be rejected at
    # mint time, *before* caching — otherwise the bad value would be reused for
    # every fetch until expiry, blocking the service. After the bad response, a
    # good response on the next call must succeed (proving the cache was not
    # poisoned) and a fresh POST must be made.
    post = RecordingPost(
        FakeResponse(200, {"access_token": "bad\ntoken", "expires_in": 3600}),
        FakeResponse(200, {"access_token": "good-token", "expires_in": 3600}),
    )

    with pytest.raises(OAuthRefreshError):
        fetch_secret("salesforce", caller_role="sales", http_post=post, now=1_000.0)

    second = fetch_secret(
        "salesforce", caller_role="sales", http_post=post, now=1_010.0
    )
    assert second.value == "good-token"
    assert post.call_count == 2


def test_error_body_is_not_leaked_to_logs(oauth_env, caplog):
    post = RecordingPost(FakeResponse(401, {"error_description": "LEAKY-SECRET-DETAIL"}))
    with caplog.at_level(logging.INFO, logger="enterprise.secrets"):
        with pytest.raises(OAuthRefreshError) as exc_info:
            fetch_secret("salesforce", caller_role="sales", http_post=post, now=0.0)
    # The raised message and the logs must not echo the response body.
    assert "LEAKY-SECRET-DETAIL" not in str(exc_info.value)
    rendered = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "LEAKY-SECRET-DETAIL" not in rendered


# --------------------------------------------------------------------------- #
# Safe fallback when no refresh config present
# --------------------------------------------------------------------------- #


def test_no_oauth_config_falls_back_to_longlived_key(seed_secret):
    # No *_OAUTH_* vars set → long-lived API key path, ephemeral=False.
    seed_secret("stripe", "sk-test-LONGLIVED_AAAA")
    sentinel_called = {"hit": False}

    def should_not_be_called(*a, **k):
        sentinel_called["hit"] = True
        raise AssertionError("OAuth path must not run without refresh config")

    bundle = fetch_secret("stripe", caller_role="finance", http_post=should_not_be_called)
    assert bundle.value == "sk-test-LONGLIVED_AAAA"
    assert bundle.ephemeral is False
    assert bundle.expires_at is None
    assert sentinel_called["hit"] is False


def test_partial_oauth_config_falls_back_safely(monkeypatch, seed_secret):
    # Token URL + client id present but NO refresh token → not a usable
    # refresh source → must fall back, not error.
    monkeypatch.setenv("STRIPE_OAUTH_TOKEN_URL", "https://idp.example.test/token")
    monkeypatch.setenv("STRIPE_OAUTH_CLIENT_ID", "client-abc")
    seed_secret("stripe", "sk-test-FALLBACK_BBBB")

    bundle = fetch_secret("stripe", caller_role="finance")
    assert bundle.value == "sk-test-FALLBACK_BBBB"
    assert bundle.ephemeral is False


def test_minted_token_value_does_not_leak_in_repr_or_logs(oauth_env, caplog):
    post = RecordingPost(
        FakeResponse(200, {"access_token": "at-REPR-LEAK-PROBE", "expires_in": 60})
    )
    with caplog.at_level(logging.INFO, logger="enterprise.secrets"):
        bundle = fetch_secret(
            "salesforce", caller_role="sales", http_post=post, now=0.0
        )
    assert "at-REPR-LEAK-PROBE" not in repr(bundle)
    rendered = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "at-REPR-LEAK-PROBE" not in rendered
    # The audit-style line still records that an ephemeral token was minted.
    assert "ephemeral=True" in rendered
