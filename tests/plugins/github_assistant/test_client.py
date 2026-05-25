"""GithubClient: token handling, redaction, error sanitisation, timeouts."""

from __future__ import annotations

import requests

from plugins.github_assistant.client import (
    GithubClient,
    sanitize_error,
)
from tests.plugins.github_assistant.conftest import make_response


def test_no_token_means_no_request_attempted(without_token, mock_session):
    client = GithubClient(session=mock_session)
    res = client.repo("anyone", "any")
    assert res["success"] is False
    assert res["error"] == "no_token"
    # Critically: the session must NOT have been touched.
    mock_session.request.assert_not_called()


def test_repr_does_not_leak_token(with_token):
    client = GithubClient()
    text = repr(client)
    assert with_token not in text


def test_has_token_reflects_env(without_token, monkeypatch):
    assert GithubClient().has_token() is False
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_x")
    assert GithubClient().has_token() is True


def test_authorization_header_uses_bearer(with_token, mock_session):
    mock_session._queue.append(make_response(200, json_body={"full_name": "a/b"}))
    client = GithubClient(session=mock_session)
    client.repo("a", "b")
    method, url = mock_session.request.call_args.args[:2]
    headers = mock_session.request.call_args.kwargs["headers"]
    assert method == "GET"
    assert url.endswith("/repos/a/b")
    assert headers["Authorization"] == f"Bearer {with_token}"
    # Belt-and-braces: Accept header pins the GitHub schema version.
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_timeout_returns_clean_error(with_token, mock_session):
    mock_session._queue.append(requests.Timeout("connection timed out"))
    client = GithubClient(session=mock_session)
    res = client.repo("a", "b")
    assert res == {
        "success": False,
        "error": "timeout",
        "message": "GitHub API timed out",
    }


def test_transport_error_sanitised(with_token, mock_session):
    # Real GitHub tokens are base62 (no underscores in the body) — use that
    # shape so the regex matches the way it would in production.
    leaked = "ghp_LEAKTHISVALUEFAILAAAA"
    mock_session._queue.append(
        requests.RequestException(f"boom: Authorization: Bearer {leaked}")
    )
    client = GithubClient(session=mock_session)
    res = client.repo("a", "b")
    assert res["success"] is False
    assert res["error"] == "transport"
    assert leaked not in res["message"]
    assert "***REDACTED***" in res["message"]


def test_http_4xx_returns_status_and_sanitised_body(with_token, mock_session):
    leaked = "ghp_LEAKEDKEYINSIDERESPONSEAAAA"
    mock_session._queue.append(
        make_response(403, text=f"forbidden — used token {leaked}")
    )
    client = GithubClient(session=mock_session)
    res = client.repo("a", "b")
    assert res["success"] is False
    assert res["error"] == "http_error"
    assert res["status"] == 403
    assert leaked not in res["message"]


def test_success_returns_payload(with_token, mock_session):
    mock_session._queue.append(
        make_response(200, json_body={"full_name": "a/b", "default_branch": "main"})
    )
    client = GithubClient(session=mock_session)
    res = client.repo("a", "b")
    assert res["success"] is True
    assert res["payload"]["full_name"] == "a/b"
    assert res["payload"]["default_branch"] == "main"


def test_per_page_capped(with_token, mock_session):
    mock_session._queue.append(make_response(200, json_body=[]))
    client = GithubClient(session=mock_session)
    client.branches("a", "b", limit=10_000)
    params = mock_session.request.call_args.kwargs["params"]
    # HARD_LIST_CAP = 250
    assert params["per_page"] == 250


def test_create_issue_sends_body_payload(with_token, mock_session):
    mock_session._queue.append(make_response(201, json_body={"number": 7}))
    client = GithubClient(session=mock_session)
    client.create_issue("a", "b", title="hello", body="world", labels=["bug"])
    json_body = mock_session.request.call_args.kwargs["json"]
    assert json_body == {"title": "hello", "body": "world", "labels": ["bug"]}


def test_sanitize_error_strips_all_known_token_prefixes():
    s = (
        "got ghp_AAAAAAAAAAAAAAAAAAAA + github_pat_BBBBBBBBBBBBBBBB "
        "+ gho_CCCCCCCCCCCCCCCC; Authorization: Bearer ghs_DDDDDDDDDDDDDDDD"
    )
    out = sanitize_error(s)
    assert "ghp_AAAAAAAAAAAA" not in out
    assert "github_pat_BBBB" not in out
    assert "gho_CCCCCCCCCCCC" not in out
    assert "ghs_DDDDDDDDDDDD" not in out
    assert "Authorization: ***REDACTED***" in out
