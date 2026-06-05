"""PublicApiClient: host allowlist, redaction, size caps, retry-once."""

from __future__ import annotations

from collections import deque
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from tools.http_client import HttpClientError, PublicApiClient, redact


def _make_response(
    status: int = 200,
    *,
    json_body: Any = None,
    text: str = "",
    headers: dict | None = None,
) -> Any:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    body = text if text else ("" if json_body is None else "json")
    resp.text = body
    resp.content = body.encode("utf-8")
    resp.json = MagicMock(return_value=json_body)
    resp.headers = headers or {}
    return resp


def _session_with(*items: Any):
    """A requests.Session mock whose .request() pops canned items in order.

    An item may be a response, or an Exception instance to raise. The mock
    accepts ``allow_redirects`` so it matches the real call signature.
    """
    queue: deque = deque(items)
    seen_urls: list = []

    seen_calls: list = []

    def _request(
        method,
        url,
        headers=None,
        params=None,
        timeout=None,
        allow_redirects=None,
        json=None,
    ):
        seen_urls.append(url)
        seen_calls.append({"method": method, "url": url, "json": json})
        if not queue:
            raise AssertionError(f"no queued response for {method} {url}")
        item = queue.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    session = MagicMock(spec=requests.Session)
    session.request.side_effect = _request
    session._queue = queue
    session._seen_urls = seen_urls
    session._seen_calls = seen_calls
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


def test_auto_redirects_are_disabled():
    session = _session_with(_make_response(200, json_body={"ok": True}))
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    client.get_json("https://api.example.com/v1")
    # The host-pinning guard depends on us, not requests, following 3xx.
    assert session.request.call_args.kwargs["allow_redirects"] is False


def test_redirect_to_off_allowlist_host_is_refused():
    # An allowlisted host 3xx-redirects to a foreign host; the guard must
    # re-check the hop and refuse rather than following it (SSRF / key-leak).
    session = _session_with(
        _make_response(302, headers={"Location": "https://evil.example.net/x"}),
    )
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    with pytest.raises(HttpClientError) as exc:
        client.get_json("https://api.example.com/v1")
    assert exc.value.error == "host_not_allowed"
    # We never issued a request to the evil host.
    assert all("evil.example.net" not in u for u in session._seen_urls)


def test_redirect_to_allowlisted_host_is_followed():
    session = _session_with(
        _make_response(302, headers={"Location": "https://api.example.com/v2"}),
        _make_response(200, json_body={"ok": True}),
    )
    client = PublicApiClient(allowed_hosts=("api.example.com",), session=session)
    assert client.get_json("https://api.example.com/v1") == {"ok": True}
    assert session._seen_urls == [
        "https://api.example.com/v1",
        "https://api.example.com/v2",
    ]


def test_redirect_loop_is_bounded():
    # Always redirects back to an allowlisted URL → must stop, not spin.
    loop = [
        _make_response(302, headers={"Location": "https://api.example.com/loop"})
        for _ in range(10)
    ]
    session = _session_with(*loop)
    client = PublicApiClient(
        allowed_hosts=("api.example.com",), session=session, max_redirects=3
    )
    with pytest.raises(HttpClientError) as exc:
        client.get_json("https://api.example.com/start")
    assert exc.value.error == "too_many_redirects"


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


# ── post_json ───────────────────────────────────────────────────────────────


def test_post_json_sends_body_and_parses_response():
    session = _session_with(_make_response(200, json_body={"vulns": []}))
    client = PublicApiClient(allowed_hosts=("api.osv.dev",), session=session)
    out = client.post_json(
        "https://api.osv.dev/v1/query",
        json_body={"package": {"name": "flask", "ecosystem": "PyPI"}},
    )
    assert out == {"vulns": []}
    call = session._seen_calls[-1]
    assert call["method"] == "POST"
    assert call["json"] == {"package": {"name": "flask", "ecosystem": "PyPI"}}


def test_post_json_enforces_allowlist():
    session = _session_with()
    client = PublicApiClient(allowed_hosts=("api.osv.dev",), session=session)
    with pytest.raises(HttpClientError) as exc:
        client.post_json("https://evil.example.net/run", json_body={"x": 1})
    assert exc.value.error == "host_not_allowed"
    session.request.assert_not_called()


def test_post_json_redacts_secret_in_error():
    secret = "piston-token-LEAK-7777"
    session = _session_with(_make_response(403, text=f"denied key={secret}"))
    client = PublicApiClient(
        allowed_hosts=("emkc.org",), session=session, secrets=[secret]
    )
    with pytest.raises(HttpClientError) as exc:
        client.post_json("https://emkc.org/api/v2/piston/execute", json_body={})
    assert exc.value.error == "http_error"
    assert secret not in exc.value.message


def test_post_json_refuses_oversized_body():
    big = {"out": "Z" * 5000}
    session = _session_with(
        _make_response(200, json_body=big, text='{"out":"' + "Z" * 5000 + '"}')
    )
    client = PublicApiClient(
        allowed_hosts=("emkc.org",), session=session, max_bytes=1000
    )
    with pytest.raises(HttpClientError) as exc:
        client.post_json("https://emkc.org/api/v2/piston/execute", json_body={})
    assert exc.value.error == "response_too_large"
