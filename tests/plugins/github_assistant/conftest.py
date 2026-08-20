"""Per-suite fixtures for the github_assistant plugin tests.

Three things we need to control across these tests:

1. **Config view.** Most tests want a specific (enabled, allow_writes,
   allowed_repositories) combination. ``cfg_view`` patches
   ``plugins.github_assistant.config.load_config`` to return whatever
   the test asks for — no YAML on disk needed.
2. **Token presence.** A few tests assert the no-token path. The
   ``with_token`` fixture sets the env var; the ``without_token`` one
   guarantees it's unset (the parent conftest already strips
   credential-shaped env vars before every test, but we belt-and-brace).
3. **HTTP layer.** No test hits api.github.com. ``mock_session``
   yields a ``requests.Session`` whose ``request`` method we control
   via a deque of canned responses.
"""

from __future__ import annotations

import os
from collections import deque
from typing import Any, Callable, Iterator
from unittest.mock import MagicMock

import pytest
import requests

from plugins.github_assistant import config as github_config


@pytest.fixture
def cfg_view(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., github_config.GithubConfig]:
    """Return a setter that patches load_config to yield the given GithubConfig.

    Usage::
        def test_x(cfg_view):
            cfg = cfg_view(enabled=True, allow_writes=False,
                           allowed_repositories=("a/b",))
    """

    def _set(
        *,
        enabled: bool = False,
        allow_writes: bool = False,
        allowed_repositories: tuple[str, ...] = (),
    ) -> github_config.GithubConfig:
        cfg = github_config.GithubConfig(
            enabled=enabled,
            allow_writes=allow_writes,
            allowed_repositories=allowed_repositories,
        )
        monkeypatch.setattr(github_config, "load_config", lambda: cfg)
        # tools.py imports `github_config` and calls `github_config.load_config`,
        # so patching the module-level name reaches every handler.
        return cfg

    return _set


@pytest.fixture
def with_token(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set GITHUB_PERSONAL_ACCESS_TOKEN for the duration of the test."""
    value = "github_pat_TEST_FAKE_FAKE_FAKE_FAKE"
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", value)
    return value


@pytest.fixture
def without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)


@pytest.fixture
def mock_session() -> Iterator[Any]:
    """A requests.Session-shaped mock whose .request() pops canned responses."""
    responses: deque = deque()

    def _request(method, url, headers=None, params=None, json=None, timeout=None):
        if not responses:
            raise AssertionError(
                f"mock_session has no queued response for {method} {url}"
            )
        item = responses.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    session = MagicMock(spec=requests.Session)
    session.request.side_effect = _request
    session._queue = responses  # tests pop into this directly
    yield session


def make_response(
    status: int = 200,
    json_body: Any = None,
    text: str | None = None,
) -> Any:
    """Build a response-shaped object the client treats the way it would real ones."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.text = (
        text if text is not None else (str(json_body) if json_body is not None else "")
    )
    resp.json = MagicMock(return_value=json_body)
    return resp
