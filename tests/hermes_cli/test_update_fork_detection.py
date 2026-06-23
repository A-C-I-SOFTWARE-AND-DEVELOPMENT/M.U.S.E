"""Regression tests for `muse update` fork detection + upstream wiring.

The canonical upstream for this project is
``A-C-I-SOFTWARE-AND-DEVELOPMENT/muse`` (see ``scripts/install.sh``). A stale
``NousResearch/hermes-agent`` constant previously made ``_is_fork()``
misclassify the official repo and wired the ``upstream`` remote to an unrelated
ancestral project — which broke ``muse update`` for forks. These tests pin the
correct identity so the regression can't silently return.
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

_ACI = "A-C-I-SOFTWARE-AND-DEVELOPMENT/muse"


def test_official_constants_point_at_aci_muse():
    assert _ACI in OFFICIAL_REPO_URL
    assert "NousResearch" not in OFFICIAL_REPO_URL
    assert OFFICIAL_REPO_URLS, "expected a non-empty official URL set"
    for url in OFFICIAL_REPO_URLS:
        assert _ACI in url
        assert "NousResearch" not in url


@pytest.mark.parametrize(
    "origin",
    [
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
        "https://github.com/echerd27/musegit",
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
    """`upstream` must be wired to the A-C-I/muse repo, not the old Nous one."""
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        return MagicMock(returncode=0)

    with patch("hermes_cli.main.subprocess.run", side_effect=fake_run):
        ok = _add_upstream_remote(["git"], Path("/tmp"))

    assert ok is True
    assert captured["argv"][:4] == ["git", "remote", "add", "upstream"]
    assert captured["argv"][4] == OFFICIAL_REPO_URL
    assert _ACI in captured["argv"][4]
