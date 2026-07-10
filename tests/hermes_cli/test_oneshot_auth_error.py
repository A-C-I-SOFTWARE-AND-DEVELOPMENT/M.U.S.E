"""``hermes -z`` must fail friendly, not with a traceback, when no
provider is configured (the first thing a fresh Termux install hits)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.auth import AuthError
from hermes_cli.oneshot import run_oneshot


@pytest.fixture
def fresh_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return home


def test_auth_error_prints_message_and_exits_2(fresh_home, monkeypatch, capsys):
    def _boom(*args, **kwargs):
        raise AuthError(
            "No inference provider configured. Run 'hermes model' …"
        )

    monkeypatch.setattr("hermes_cli.oneshot._run_agent", _boom)

    rc = run_oneshot("say hi")

    captured = capsys.readouterr()
    assert rc == 2
    assert "No inference provider configured" in captured.err
    assert "Traceback" not in captured.err


def test_non_auth_errors_still_propagate(fresh_home, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("genuine bug")

    monkeypatch.setattr("hermes_cli.oneshot._run_agent", _boom)

    with pytest.raises(RuntimeError, match="genuine bug"):
        run_oneshot("say hi")
