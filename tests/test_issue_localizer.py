"""Tests for the deterministic issue localizer."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.navigation.issue_localizer import IssueLocalizer
from hermes_cli.jarvis_prime.navigation.repo_index import RepoIndex
from hermes_cli.jarvis_prime.navigation.symbol_graph import SymbolGraph


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "auth_login.py").write_text(
        "def authenticate(user, password):\n    return bool(user)\n\n"
        "def reset_password(user):\n    return True\n"
    )
    (tmp_path / "app" / "billing.py").write_text(
        "def charge_card(amount):\n    return amount\n"
    )
    (tmp_path / "app" / "search.py").write_text(
        "def run_search(query):\n    return []\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_auth_login.py").write_text(
        "from app.auth_login import authenticate\n\ndef test_x():\n    assert authenticate('a','b')\n"
    )
    return tmp_path


def _localizer(repo: Path) -> IssueLocalizer:
    index = RepoIndex.build(repo)
    graph = SymbolGraph.build(index)
    # Disable git so the test is hermetic (tmp_path is not a git repo anyway).
    return IssueLocalizer.build(index, graph, use_git=False)


def test_path_mention_dominates(repo: Path):
    loc = _localizer(repo)
    results = loc.localize("the login is broken in auth_login.py")
    assert results[0].path == "app/auth_login.py"
    assert results[0].signals["path"] > 0


def test_symbol_match_ranks_file(repo: Path):
    loc = _localizer(repo)
    results = loc.localize("authenticate keeps rejecting valid users")
    top_paths = [r.path for r in results]
    assert top_paths[0] == "app/auth_login.py"
    assert results[0].signals["symbol"] > 0


def test_unrelated_terms_dont_match_everything(repo: Path):
    loc = _localizer(repo)
    results = loc.localize("charge_card overcharges customers")
    assert results[0].path == "app/billing.py"
    # billing should clearly outrank search/auth here.
    assert results[0].score > (results[1].score if len(results) > 1 else 0)


def test_signals_are_explainable(repo: Path):
    loc = _localizer(repo)
    results = loc.localize("reset_password flow in auth_login.py")
    top = results[0]
    assert top.path == "app/auth_login.py"
    d = top.to_dict()
    assert set(d["signals"]) == {"lexical", "path", "symbol", "test", "git"}
    assert d["matched_terms"]


def test_empty_for_no_signal(repo: Path):
    loc = _localizer(repo)
    results = loc.localize("zzzzqqqq nonexistent topic")
    assert results == []
