"""Regression tests for `muse update` fork detection + upstream wiring.

The canonical upstream for this project is the live GitHub repo
``A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E`` (see ``scripts/install.sh``). The
``muse``/``musegit`` slugs 404, so a fresh official clone uses the ``M.U.S.E``
origin — which must be recognized as official, not a fork, and must be the URL
wired as ``upstream``. A stale ``NousResearch/hermes-agent`` constant previously
made ``_is_fork()`` misclassify the official repo. These tests pin the correct
identity so the regression can't silently return.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli.main import (
    OFFICIAL_REPO_URL,
    OFFICIAL_REPO_URLS,
    _add_upstream_remote,
    _is_fork,
)

_ORG = "A-C-I-SOFTWARE-AND-DEVELOPMENT/"
# The canonical, working slug the update flow must wire upstream to.
_CANONICAL = "A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E"


def test_official_constants_point_at_the_live_repo():
    assert OFFICIAL_REPO_URL.endswith(_CANONICAL)
    assert "NousResearch" not in OFFICIAL_REPO_URL
    assert OFFICIAL_REPO_URLS, "expected a non-empty official URL set"
    for url in OFFICIAL_REPO_URLS:
        assert _ORG in url
        assert "NousResearch" not in url


@pytest.mark.parametrize(
    "origin",
    [
        # The live, working slug (with/without .git and trailing slash).
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E",
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E.git",
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/",
        "git@github.com:A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E",
        # Legacy slugs older clones may still use.
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/musegit",
        "git@github.com:A-C-I-SOFTWARE-AND-DEVELOPMENT/musegit",
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse",
        "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/",
    ],
)
def test_official_origin_is_not_a_fork(origin):
    assert _is_fork(origin) is False


@pytest.mark.parametrize(
    "origin",
    [
        "https://github.com/echerd27/M.U.S.E",
        "git@github.com:echerd27/musegit",
        # The ancestral project is now correctly NOT treated as our upstream.
        "https://github.com/NousResearch/hermes-agent.git",
    ],
)
def test_other_origins_are_forks(origin):
    assert _is_fork(origin) is True


def test_none_origin_is_not_a_fork():
    assert _is_fork(None) is False


def test_add_upstream_remote_uses_official_url():
    """`upstream` must be wired to the live A-C-I/M.U.S.E repo."""
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        return MagicMock(returncode=0)

    with patch("hermes_cli.main.subprocess.run", side_effect=fake_run):
        ok = _add_upstream_remote(["git"], Path("/tmp"))

    assert ok is True
    assert captured["argv"][:4] == ["git", "remote", "add", "upstream"]
    assert captured["argv"][4] == OFFICIAL_REPO_URL
    assert _CANONICAL in captured["argv"][4]
