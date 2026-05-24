"""Tests for the ``hermes checkpoints`` CLI surface.

The CLI thin-wraps ``tools.checkpoint_manager``; these tests cover the
formatting helpers, argparse wiring, and the confirmation prompt.
External effects (delete, prune) are stubbed so no real checkpoints are
touched.
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from hermes_cli import checkpoints as cp


# ── pure formatting helpers ───────────────────────────────────────────


class TestFormatBytes:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "0 B"),
            (None, "0 B"),
            (512, "512 B"),
            (2048, "2.0 KB"),
            (5 * 1024 * 1024, "5.0 MB"),
            (3 * 1024 ** 3, "3.0 GB"),
        ],
    )
    def test_renders_units(self, value: Any, expected: str) -> None:
        assert cp._fmt_bytes(value) == expected


class TestFormatTimestamp:
    def test_dash_on_none(self) -> None:
        assert cp._fmt_ts(None) == "—"

    def test_dash_on_bad_value(self) -> None:
        assert cp._fmt_ts("nope") == "—"

    def test_real_timestamp_renders(self) -> None:
        # Just check shape — exact value depends on local timezone.
        rendered = cp._fmt_ts(0)
        assert ":" in rendered


class TestFormatAge:
    def test_now_for_negative(self) -> None:
        assert cp._fmt_age(1e18) == "now"

    def test_seconds(self, monkeypatch) -> None:
        import time as _time
        monkeypatch.setattr(_time, "time", lambda: 1000.0)
        # 1000 - 990 = 10s ago
        assert cp._fmt_age(990).endswith("s ago")

    def test_minutes(self, monkeypatch) -> None:
        import time as _time
        monkeypatch.setattr(_time, "time", lambda: 1000.0)
        # 1000 - 700 = 300s = 5m
        assert cp._fmt_age(700).endswith("m ago")

    def test_hours(self, monkeypatch) -> None:
        import time as _time
        monkeypatch.setattr(_time, "time", lambda: 10_000.0)
        assert cp._fmt_age(0).endswith("h ago") or cp._fmt_age(0).endswith("d ago")

    def test_dash_on_bad_value(self) -> None:
        assert cp._fmt_age(None) == "—"
        assert cp._fmt_age("not-a-number") == "—"


# ── argparse wiring ───────────────────────────────────────────────────


class TestRegisterCli:
    def test_subcommands_are_registered(self) -> None:
        parser = argparse.ArgumentParser(prog="hermes")
        cp.register_cli(parser)
        # ``hermes checkpoints`` defaults to status.
        defaults = parser.parse_args([])
        assert defaults.func is cp.cmd_status

    def test_status_accepts_limit(self) -> None:
        parser = argparse.ArgumentParser(prog="hermes")
        cp.register_cli(parser)
        args = parser.parse_args(["status", "--limit", "5"])
        assert args.limit == 5

    def test_prune_flags(self) -> None:
        parser = argparse.ArgumentParser(prog="hermes")
        cp.register_cli(parser)
        args = parser.parse_args(
            ["prune", "--retention-days", "3", "--max-size-mb", "10", "--keep-orphans"]
        )
        assert args.retention_days == 3
        assert args.max_size_mb == 10
        assert args.keep_orphans is True
        assert args.func is cp.cmd_prune

    def test_clear_force_flag(self) -> None:
        parser = argparse.ArgumentParser(prog="hermes")
        cp.register_cli(parser)
        args = parser.parse_args(["clear", "-f"])
        assert args.force is True
        assert args.func is cp.cmd_clear

    def test_clear_legacy(self) -> None:
        parser = argparse.ArgumentParser(prog="hermes")
        cp.register_cli(parser)
        args = parser.parse_args(["clear-legacy", "-f"])
        assert args.force is True
        assert args.func is cp.cmd_clear_legacy


# ── confirm prompt ────────────────────────────────────────────────────


class TestConfirm:
    def test_yes(self, monkeypatch) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        assert cp._confirm("ok?") is True

    def test_y(self, monkeypatch) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert cp._confirm("ok?") is True

    def test_default_no(self, monkeypatch) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert cp._confirm("ok?") is False

    def test_n(self, monkeypatch) -> None:
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert cp._confirm("ok?") is False

    def test_eof_returns_false(self, monkeypatch) -> None:
        def _raise(_prompt: str) -> str:
            raise EOFError

        monkeypatch.setattr("builtins.input", _raise)
        assert cp._confirm("ok?") is False

    def test_keyboard_interrupt_returns_false(self, monkeypatch) -> None:
        def _raise(_prompt: str) -> str:
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", _raise)
        assert cp._confirm("ok?") is False


# ── cmd_status / cmd_clear behaviour with stubbed backing tool ────────


def _stub_store_status(monkeypatch, info: dict) -> None:
    """Replace ``tools.checkpoint_manager.store_status`` for one test."""
    import tools.checkpoint_manager as ckpt

    monkeypatch.setattr(ckpt, "store_status", lambda: info)


class TestStatusCommand:
    def test_empty_store_prints_zero(self, monkeypatch) -> None:
        _stub_store_status(monkeypatch, {
            "base": "/tmp/none",
            "total_size_bytes": 0,
            "store_size_bytes": 0,
            "legacy_size_bytes": 0,
            "project_count": 0,
            "projects": [],
            "legacy_archives": [],
        })
        args = argparse.Namespace(limit=20)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cp.cmd_status(args)
        assert rc == 0
        out = buf.getvalue()
        assert "Projects:" in out
        assert "0" in out


class TestClearCommand:
    def test_aborts_when_unconfirmed(self, monkeypatch, tmp_path: Path) -> None:
        import tools.checkpoint_manager as ckpt

        info = {
            "base": str(tmp_path / "store"),
            "total_size_bytes": 12345,
            "store_size_bytes": 12345,
            "legacy_size_bytes": 0,
            "project_count": 1,
            "projects": [],
            "legacy_archives": [],
        }
        (tmp_path / "store").mkdir()
        monkeypatch.setattr(ckpt, "store_status", lambda: info)
        monkeypatch.setattr(ckpt, "CHECKPOINT_BASE", str(tmp_path / "store"))
        monkeypatch.setattr(ckpt, "clear_all", lambda: {"deleted": True, "bytes_freed": 0})
        # ``_confirm`` returns False without -f.
        monkeypatch.setattr("builtins.input", lambda _: "n")
        args = argparse.Namespace(force=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cp.cmd_clear(args)
        assert rc == 1
        assert "Aborted" in buf.getvalue()

    def test_clears_when_forced(self, monkeypatch, tmp_path: Path) -> None:
        import tools.checkpoint_manager as ckpt

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        info = {
            "base": str(store_dir),
            "total_size_bytes": 99,
            "store_size_bytes": 99,
            "legacy_size_bytes": 0,
            "project_count": 0,
            "projects": [],
            "legacy_archives": [],
        }
        monkeypatch.setattr(ckpt, "store_status", lambda: info)
        monkeypatch.setattr(ckpt, "CHECKPOINT_BASE", str(store_dir))
        called = {"clear": False}

        def _stub_clear() -> dict:
            called["clear"] = True
            return {"deleted": True, "bytes_freed": 99}

        monkeypatch.setattr(ckpt, "clear_all", _stub_clear)
        args = argparse.Namespace(force=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cp.cmd_clear(args)
        assert rc == 0
        assert called["clear"] is True
        assert "Cleared" in buf.getvalue()
