"""Tool handlers — happy path + gate behaviour.

We don't exercise the real GitHub here; the GithubClient class is
swapped for a mock so we can assert exactly which API calls happen
under which configurations.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.github_assistant.tools as tools


@pytest.fixture
def mock_client(monkeypatch):
    """Replace tools.GithubClient with a MagicMock that always reports has_token=True."""
    m = MagicMock()
    instance = MagicMock()
    instance.has_token.return_value = True
    m.return_value = instance
    monkeypatch.setattr(tools, "GithubClient", m)
    return instance


def _parse(result: str):
    return json.loads(result)


# ── plugin_disabled gate ─────────────────────────────────────────────────────


def test_audit_repo_refuses_when_plugin_disabled(cfg_view, mock_client):
    cfg_view(enabled=False)
    out = _parse(tools.handle_audit_repo({"owner": "a", "name": "b"}))
    assert out == {
        "success": False,
        "error": "plugin_disabled",
        "message": "github.enabled is false",
    }
    mock_client.repo.assert_not_called()


# ── bad args ────────────────────────────────────────────────────────────────


def test_audit_repo_rejects_missing_owner(cfg_view, mock_client):
    cfg_view(enabled=True)
    out = _parse(tools.handle_audit_repo({"name": "b"}))
    assert out["success"] is False
    assert out["error"] == "bad_args"
    mock_client.repo.assert_not_called()


def test_audit_repo_rejects_path_traversal(cfg_view, mock_client):
    cfg_view(enabled=True)
    out = _parse(tools.handle_audit_repo({"owner": "../etc", "name": "passwd"}))
    assert out["error"] == "bad_args"


def test_get_repo_file_rejects_dot_dot_in_path(cfg_view, mock_client):
    cfg_view(enabled=True)
    out = _parse(
        tools.handle_get_repo_file({
            "owner": "a",
            "name": "b",
            "path": "src/../../etc/passwd",
        })
    )
    assert out["error"] == "bad_args"
    mock_client.file_contents.assert_not_called()


# ── allowlist gate ──────────────────────────────────────────────────────────


def test_audit_repo_blocked_when_repo_not_on_allowlist(cfg_view, mock_client):
    cfg_view(enabled=True, allowed_repositories=("other/repo",))
    out = _parse(tools.handle_audit_repo({"owner": "a", "name": "b"}))
    assert out["error"] == "repo_not_allowed"
    mock_client.repo.assert_not_called()


def test_audit_repo_passes_when_repo_on_allowlist(cfg_view, mock_client):
    cfg_view(enabled=True, allowed_repositories=("a/b",))
    mock_client.repo.return_value = {
        "success": True,
        "payload": {"full_name": "a/b", "default_branch": "main"},
    }
    out = _parse(tools.handle_audit_repo({"owner": "a", "name": "b"}))
    assert out["success"] is True
    assert out["repo"]["full_name"] == "a/b"


# ── writes gate ─────────────────────────────────────────────────────────────


def test_create_issue_refused_when_allow_writes_false(cfg_view, mock_client):
    cfg_view(enabled=True, allow_writes=False)
    out = _parse(
        tools.handle_create_issue({
            "owner": "a",
            "name": "b",
            "title": "bug",
            "body": "broken",
        })
    )
    assert out["error"] == "writes_disabled"
    mock_client.create_issue.assert_not_called()


def test_create_issue_runs_when_allow_writes_true(cfg_view, mock_client):
    cfg_view(enabled=True, allow_writes=True)
    mock_client.create_issue.return_value = {
        "success": True,
        "payload": {"number": 7, "title": "bug", "state": "open"},
    }
    out = _parse(
        tools.handle_create_issue({
            "owner": "a",
            "name": "b",
            "title": "bug",
            "body": "broken",
        })
    )
    assert out["success"] is True
    assert out["issue"]["number"] == 7
    mock_client.create_issue.assert_called_once()


def test_comment_refused_when_allow_writes_false(cfg_view, mock_client):
    cfg_view(enabled=True, allow_writes=False)
    out = _parse(
        tools.handle_comment_on_issue_or_pr({
            "owner": "a",
            "name": "b",
            "number": 1,
            "body": "ping",
        })
    )
    assert out["error"] == "writes_disabled"


def test_comment_runs_when_allow_writes_true(cfg_view, mock_client):
    cfg_view(enabled=True, allow_writes=True)
    mock_client.comment_on_issue.return_value = {
        "success": True,
        "payload": {
            "id": 99,
            "html_url": "https://github.com/a/b/issues/1#c99",
            "user": {"login": "u"},
        },
    }
    out = _parse(
        tools.handle_comment_on_issue_or_pr({
            "owner": "a",
            "name": "b",
            "number": 1,
            "body": "ping",
        })
    )
    assert out["success"] is True
    assert out["comment"]["id"] == 99


# ── read tools ──────────────────────────────────────────────────────────────


def test_list_branches_slims_payload(cfg_view, mock_client):
    cfg_view(enabled=True)
    mock_client.branches.return_value = {
        "success": True,
        "payload": [
            {"name": "main", "commit": {"sha": "abc"}, "protected": True, "_links": {}},
            {"name": "dev", "commit": {"sha": "def"}, "protected": False, "_links": {}},
        ],
    }
    out = _parse(tools.handle_list_branches({"owner": "a", "name": "b"}))
    assert out["success"] is True
    assert out["branches"] == [
        {"name": "main", "sha": "abc", "protected": True},
        {"name": "dev", "sha": "def", "protected": False},
    ]


def test_list_issues_excludes_pull_requests(cfg_view, mock_client):
    cfg_view(enabled=True)
    mock_client.issues.return_value = {
        "success": True,
        "payload": [
            {"number": 1, "title": "real issue"},
            {"number": 2, "title": "actually a PR", "pull_request": {"url": "..."}},
            {"number": 3, "title": "real issue 2"},
        ],
    }
    out = _parse(tools.handle_list_issues({"owner": "a", "name": "b"}))
    titles = [i["title"] for i in out["issues"]]
    assert titles == ["real issue", "real issue 2"]


def test_list_issues_rejects_unknown_state(cfg_view, mock_client):
    cfg_view(enabled=True)
    out = _parse(
        tools.handle_list_issues({"owner": "a", "name": "b", "state": "mystery"})
    )
    assert out["error"] == "bad_args"


def test_get_pull_request_requires_positive_int(cfg_view, mock_client):
    cfg_view(enabled=True)
    out = _parse(
        tools.handle_get_pull_request({"owner": "a", "name": "b", "number": -1})
    )
    assert out["error"] == "bad_args"
    out = _parse(
        tools.handle_get_pull_request({"owner": "a", "name": "b", "number": "five"})
    )
    assert out["error"] == "bad_args"


def test_get_repo_file_decodes_base64_text(cfg_view, mock_client):
    import base64

    cfg_view(enabled=True)
    raw = "hello, world\n"
    mock_client.file_contents.return_value = {
        "success": True,
        "payload": {
            "path": "README.md",
            "sha": "abc",
            "size": len(raw),
            "encoding": "base64",
            "content": base64.b64encode(raw.encode()).decode(),
        },
    }
    out = _parse(
        tools.handle_get_repo_file({"owner": "a", "name": "b", "path": "README.md"})
    )
    assert out["success"] is True
    assert out["file"]["content_utf8"] == raw
    assert out["file"]["content_binary"] is False


def test_get_repo_file_directory_listing(cfg_view, mock_client):
    cfg_view(enabled=True)
    mock_client.file_contents.return_value = {
        "success": True,
        "payload": [
            {"name": "a.py", "type": "file", "size": 100},
            {"name": "subdir", "type": "dir", "size": 0},
        ],
    }
    out = _parse(tools.handle_get_repo_file({"owner": "a", "name": "b", "path": "src"}))
    assert out["file"]["kind"] == "directory"
    assert len(out["file"]["entries"]) == 2


# ── check_fn ────────────────────────────────────────────────────────────────


def test_check_fn_false_when_disabled(cfg_view, with_token):
    cfg_view(enabled=False)
    assert tools.check_github_requirements() is False


def test_check_fn_false_without_token(cfg_view, without_token):
    cfg_view(enabled=True)
    assert tools.check_github_requirements() is False


def test_check_fn_true_when_enabled_and_token_present(cfg_view, with_token):
    cfg_view(enabled=True)
    assert tools.check_github_requirements() is True
