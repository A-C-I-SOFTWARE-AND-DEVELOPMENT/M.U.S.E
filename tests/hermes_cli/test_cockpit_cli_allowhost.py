"""Tests for the ``cockpit serve --allow-external-host`` CLI flag.

The cockpit server (`gateway/cockpit/server.py`) already implements a
fail-closed host/CIDR allowlist: a *non-loopback* bind requires the host be
named in ``serve(allow_external_hosts=[...])`` (host string or CIDR), on top of
``allow_external=True``. This grain (FU-13 follow-on) exposes that allowlist
from the CLI via a repeatable ``--allow-external-host HOST/CIDR`` option on
``hermes cockpit serve`` and threads it into ``serve(...)``.

These tests are hermetic — they never bind a real external socket. The
parser-shape tests parse argv only; the dispatch tests patch the real
``serve`` (and the pairing-token loader) so no network, no threads, and no
on-disk token are touched. One subprocess ``--help`` smoke test guards the
local parser replica against drifting from the real flag name.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from unittest.mock import patch

import pytest

from gateway.cockpit import server as cockpit_server
from muse_cli.main import cmd_cockpit


def _build_cockpit_parser() -> argparse.ArgumentParser:
    """Replicate the real ``cockpit serve`` subparser registration.

    Mirrors the block in ``muse_cli.main.main()`` (around the
    ``cockpit_serve`` parser). ``main()`` is a large monolith that builds the
    whole CLI with side effects, so — following the repo convention in
    ``test_argparse_flag_propagation.py`` — we replicate just the relevant
    subparser here. ``test_real_cli_help_lists_allow_external_host`` drives the
    real CLI to guard this replica against drift.
    """
    parser = argparse.ArgumentParser(prog="hermes")
    subparsers = parser.add_subparsers(dest="command")
    cockpit_parser = subparsers.add_parser("cockpit")
    cockpit_sub = cockpit_parser.add_subparsers(dest="cockpit_command")
    cockpit_serve = cockpit_sub.add_parser("serve")
    cockpit_serve.add_argument("--host", default="127.0.0.1")
    cockpit_serve.add_argument("--port", type=int, default=8765)
    cockpit_serve.add_argument(
        "--allow-external", dest="allow_external", action="store_true",
    )
    cockpit_serve.add_argument(
        "--allow-external-host", dest="allow_external_hosts", action="append",
        default=None, metavar="HOST/CIDR",
    )
    return parser


def _capturing_serve():
    """Return ``(fake_serve, captured)`` — a drop-in for ``serve`` that records
    the kwargs it was called with and returns a fake server object.

    The fake server mimics just what ``cmd_cockpit`` touches:
    ``server_address`` (a tuple it unpacks/prints) and ``shutdown()``.
    """
    captured: dict = {}

    class _FakeServer:
        server_address = ("127.0.0.1", 8765)

        def shutdown(self):  # pragma: no cover - trivial
            captured["shutdown"] = True

    def fake_serve(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeServer()

    return fake_serve, captured


def _run_cmd_cockpit(args: argparse.Namespace) -> dict:
    """Invoke ``cmd_cockpit`` hermetically and return the captured ``serve``
    call. Patches the real ``serve`` and the token loader; breaks the serve
    loop by raising ``KeyboardInterrupt`` from ``time.sleep``.
    """
    fake_serve, captured = _capturing_serve()
    with patch.object(cockpit_server, "serve", fake_serve), \
            patch("gateway.cockpit.auth.load_or_create_token", return_value="tok"), \
            patch("time.sleep", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc:
            cmd_cockpit(args)
    assert exc.value.code == 0
    return captured


# ---------------------------------------------------------------------------
# Parser shape
# ---------------------------------------------------------------------------

class TestParser:
    def test_flag_absent_defaults_to_none(self):
        """No flag → ``allow_external_hosts`` is ``None`` (byte-identical to the
        pre-grain default, which omitted the kwarg entirely)."""
        parser = _build_cockpit_parser()
        ns = parser.parse_args(["cockpit", "serve"])
        assert ns.allow_external_hosts is None

    def test_single_host(self):
        parser = _build_cockpit_parser()
        ns = parser.parse_args(
            ["cockpit", "serve", "--allow-external-host", "10.0.0.5"]
        )
        assert ns.allow_external_hosts == ["10.0.0.5"]

    def test_repeatable_appends_in_order(self):
        """``action="append"`` collects every occurrence, preserving order and
        accepting both bare hosts and CIDR ranges."""
        parser = _build_cockpit_parser()
        ns = parser.parse_args([
            "cockpit", "serve",
            "--allow-external-host", "10.0.0.5",
            "--allow-external-host", "192.168.1.0/24",
        ])
        assert ns.allow_external_hosts == ["10.0.0.5", "192.168.1.0/24"]

    def test_real_cli_help_lists_allow_external_host(self):
        """Drift guard: the *real* CLI registers ``--allow-external-host`` on
        ``cockpit serve`` (so the local replica above can't silently diverge
        from the shipped flag name)."""
        result = subprocess.run(
            [sys.executable, "-m", "muse_cli.main", "cockpit", "serve", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"returned {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )
        assert "--allow-external-host" in result.stdout


# ---------------------------------------------------------------------------
# cmd_cockpit threads the parsed list into serve(...)
# ---------------------------------------------------------------------------

class TestCmdCockpitThreading:
    def test_passes_host_list_to_serve(self):
        parser = _build_cockpit_parser()
        ns = parser.parse_args([
            "cockpit", "serve",
            "--allow-external",
            "--allow-external-host", "10.0.0.5",
            "--allow-external-host", "192.168.1.0/24",
        ])
        captured = _run_cmd_cockpit(ns)
        assert captured["kwargs"]["allow_external_hosts"] == [
            "10.0.0.5", "192.168.1.0/24",
        ]
        assert captured["kwargs"]["allow_external"] is True

    def test_default_passes_none(self):
        """Default (no flag) → ``serve`` receives ``allow_external_hosts=None``
        and ``allow_external=False``: the pre-grain default behavior, unchanged.
        """
        parser = _build_cockpit_parser()
        ns = parser.parse_args(["cockpit", "serve"])
        captured = _run_cmd_cockpit(ns)
        assert captured["kwargs"]["allow_external_hosts"] is None
        assert captured["kwargs"]["allow_external"] is False
        assert captured["kwargs"]["host"] == "127.0.0.1"


# ---------------------------------------------------------------------------
# The reused server allowlist still fails closed (defense-in-depth intact)
# ---------------------------------------------------------------------------

class TestServerStillFailsClosed:
    def test_non_loopback_not_in_allowlist_raises(self):
        """A non-loopback host with ``allow_external=True`` but absent from the
        allowlist must still raise ``ValueError`` — the CLI flag merely feeds
        this existing fail-closed gate; it does not weaken it."""
        with pytest.raises(ValueError, match="allow_external_hosts"):
            cockpit_server.serve(
                host="10.0.0.5", port=0, token="tok",
                allow_external=True, allow_external_hosts=None,
            )

    def test_non_loopback_outside_cidr_raises(self):
        """Host not contained by any allowlisted CIDR also fails closed."""
        with pytest.raises(ValueError, match="allow_external_hosts"):
            cockpit_server.serve(
                host="10.0.0.5", port=0, token="tok",
                allow_external=True, allow_external_hosts=["192.168.1.0/24"],
            )
