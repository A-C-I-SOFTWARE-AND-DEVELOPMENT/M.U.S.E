"""PublicApiClient: host allowlist, redaction, size caps, retry-once."""

from __future__ import annotations

from collections import deque
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from tools.http_client import HttpClientError, PublicApiClient, redact


def _make_response(status: int = 200, *, json_body: Any = None, text: str = "") -> Any:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    body = text if text else ("" if json_body is None else "json")
    resp.text = body
    resp.content = body.encode("utf-8")
    resp.json = MagicMock(return_value=json_body)
    return resp


def _session_with(*items: Any):
    """A requests.Session mock whose .request() pops canned items in order.

    An item may be a response, or an Exception instance to raise.
    """
    queue: deque = deque(items)

    def _request(method, url, headers=None, params=None, timeout=None):
        if not queue:
            raise AssertionError(f"no queued response for {method} {url}")
        item = queue.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    session = MagicMock(spec=requests.Session)
    session.request.side_effect = _request
    session._queue = queue
    return session


# ── host allowlist ──────────────────────────────────────────────────────────


def test_off_allowlist_host_is_refused_before_any_request():
    session = _session_with()
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    with pytest.raises(HttpClientError) as exc:
        client.get_json("https://evil.example.net/steal")
    assert exc.value.error == "host_not_allowed"
    session.request.assert_not_called()


def test_allowed_host_passes():
    session = _session_with(_make_response(200, json_body={"ok": True}))
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    assert client.get_json("https://api.example.com/v1") == {"ok": True}


# ── redaction ───────────────────────────────────────────────────────────────


def test_redact_strips_known_secret_value():
    secret = "sk-LEAKED-VALUE-12345"
    out = redact(f"failed with apikey={secret} and Authorization: Bearer abc", [secret])
    assert secret not in out
    assert "***REDACTED***" in out


def test_http_error_message_carries_no_secret():
    secret = "newsapi-key-DEADBEEF99"
    session = _session_with(_make_response(401, text=f"unauthorized: key={secret}"))
    client = PublicApiClient(
        allowed_hosts=("api.example.com",), session=session, secrets=[secret]
    )
    with pytest.raises(HttpClientError) as exc:
        client.get_json("https://api.example.com/v1")
    assert exc.value.error == "http_error"
    assert exc.value.status == 401
    assert secret not in exc.value.message


# ── size caps ───────────────────────────────────────────────────────────────


def test_get_text_truncates_to_max_bytes():
    big = "A" * 5000
    session = _session_with(_make_response(200, text=big))
    client = PublicApiClient(
        allowed_hosts=("api.example.com",), session=session, max_bytes=1000
    )
    out = client.get_text("https://api.example.com/feed")
    assert len(out.encode("utf-8")) <= 1000


def test_get_json_refuses_oversized_body():
    payload_text = '{"x":"' + "B" * 5000 + '"}'
    resp = _make_response(200, json_body={"x": "B" * 5000}, text=payload_text)
    session = _session_with(resp)
    client = PublicApiClient(
        allowed_hosts=("api.example.com",), session=session, max_bytes=1000
    )
    with pytest.raises(HttpClientError) as exc:
        client.get_json("https://api.example.com/feed")
    assert exc.value.error == "response_too_large"


# ── retry-once ──────────────────────────────────────────────────────────────


def test_retry_once_on_timeout_then_succeeds():
    session = _session_with(
        requests.Timeout("slow"),
        _make_response(200, json_body={"recovered": True}),
    )
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    assert client.get_json("https://api.example.com/v1") == {"recovered": True}
    assert session.request.call_count == 2


def test_retry_once_on_5xx_then_succeeds():
    session = _session_with(
        _make_response(503, text="unavailable"),
        _make_response(200, json_body={"ok": 1}),
    )
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    assert client.get_json("https://api.example.com/v1") == {"ok": 1}
    assert session.request.call_count == 2


def test_timeout_twice_raises_clean_timeout():
    session = _session_with(requests.Timeout("a"), requests.Timeout("b"))
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    with pytest.raises(HttpClientError) as exc:
        client.get_json("https://api.example.com/v1")
    assert exc.value.error == "timeout"
    assert session.request.call_count == 2
