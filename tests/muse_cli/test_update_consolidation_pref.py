"""Tests for the `hermes update` consolidation opt-out resolution.

Covers the precedence: CLI --no-consolidate > HERMES_NO_CONSOLIDATE env >
update.consolidate config > default-on.
"""

from __future__ import annotations

import argparse

import muse_cli.main as main


def _args(no_consolidate=False):
    return argparse.Namespace(no_consolidate=no_consolidate)


def test_default_enabled(monkeypatch):
    monkeypatch.delenv("HERMES_NO_CONSOLIDATE", raising=False)
    monkeypatch.setattr("muse_cli.config.load_config", lambda: {})
    assert main._consolidation_enabled(_args()) is True


def test_cli_flag_disables(monkeypatch):
    monkeypatch.delenv("HERMES_NO_CONSOLIDATE", raising=False)
    monkeypatch.setattr("muse_cli.config.load_config", lambda: {})
    assert main._consolidation_enabled(_args(no_consolidate=True)) is False


def test_env_disables(monkeypatch):
    monkeypatch.setattr("muse_cli.config.load_config", lambda: {})
    for val in ("1", "true", "YES", "on"):
        monkeypatch.setenv("HERMES_NO_CONSOLIDATE", val)
        assert main._consolidation_enabled(_args()) is False


def test_env_falsey_keeps_enabled(monkeypatch):
    monkeypatch.setattr("muse_cli.config.load_config", lambda: {})
    monkeypatch.setenv("HERMES_NO_CONSOLIDATE", "0")
    assert main._consolidation_enabled(_args()) is True


def test_config_disables(monkeypatch):
    monkeypatch.delenv("HERMES_NO_CONSOLIDATE", raising=False)
    monkeypatch.setattr(
        "muse_cli.config.load_config",
        lambda: {"update": {"consolidate": False}},
    )
    assert main._consolidation_enabled(_args()) is False


def test_config_true_keeps_enabled(monkeypatch):
    monkeypatch.delenv("HERMES_NO_CONSOLIDATE", raising=False)
    monkeypatch.setattr(
        "muse_cli.config.load_config",
        lambda: {"update": {"consolidate": True}},
    )
    assert main._consolidation_enabled(_args()) is True


def test_cli_flag_wins_over_config_true(monkeypatch):
    monkeypatch.delenv("HERMES_NO_CONSOLIDATE", raising=False)
    monkeypatch.setattr(
        "muse_cli.config.load_config",
        lambda: {"update": {"consolidate": True}},
    )
    assert main._consolidation_enabled(_args(no_consolidate=True)) is False


def test_load_config_failure_defaults_enabled(monkeypatch):
    monkeypatch.delenv("HERMES_NO_CONSOLIDATE", raising=False)

    def _boom():
        raise RuntimeError("no config")

    monkeypatch.setattr("muse_cli.config.load_config", _boom)
    assert main._consolidation_enabled(_args()) is True
