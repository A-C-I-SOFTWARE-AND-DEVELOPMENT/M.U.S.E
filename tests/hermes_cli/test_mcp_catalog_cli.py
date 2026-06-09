"""CLI wiring for the newly-activated catalog commands.

Covers (a) the ``hermes mcp`` dispatcher routing the ``catalog`` / ``picker`` /
``install`` actions to the right handlers, and (b) the ``mcp install`` argparse
shape — in particular that ``--all`` parses with no positional ``name`` and
without clobbering the top-level ``args.command`` dest.
"""

import argparse
from unittest.mock import patch

from hermes_cli.mcp_config import mcp_command


def _args(**kw):
    base = {
        "mcp_action": None,
        "name": None,
        "install_all": False,
        "enable": False,
        "with_bootstrap": False,
    }
    base.update(kw)
    return argparse.Namespace(**base)


# ─── dispatcher routing ────────────────────────────────────────────────────────

class TestDispatcherRouting:
    def test_catalog_routes_to_show_catalog(self):
        with patch("hermes_cli.mcp_picker.show_catalog") as m:
            mcp_command(_args(mcp_action="catalog"))
            m.assert_called_once()

    def test_ls_catalog_alias_routes_to_show_catalog(self):
        with patch("hermes_cli.mcp_picker.show_catalog") as m:
            mcp_command(_args(mcp_action="ls-catalog"))
            m.assert_called_once()

    def test_picker_routes_to_run_picker(self):
        with patch("hermes_cli.mcp_picker.run_picker") as m:
            mcp_command(_args(mcp_action="picker"))
            m.assert_called_once()

    def test_install_name_routes_to_install_by_name(self):
        with patch("hermes_cli.mcp_picker.install_by_name", return_value=0) as m:
            mcp_command(_args(mcp_action="install", name="linear"))
            m.assert_called_once_with("linear")

    def test_install_all_routes_to_install_all_entries(self):
        empty = {"installed": [], "needs_creds": [], "skipped": [], "failed": []}
        with patch(
            "hermes_cli.mcp_catalog.install_all_entries", return_value=empty
        ) as m:
            mcp_command(_args(mcp_action="install", install_all=True))
            m.assert_called_once()
            _, kwargs = m.call_args
            assert kwargs == {"enable_without_creds": False, "run_bootstrap": False}

    def test_install_all_forwards_flags(self):
        empty = {"installed": [], "needs_creds": [], "skipped": [], "failed": []}
        with patch(
            "hermes_cli.mcp_catalog.install_all_entries", return_value=empty
        ) as m:
            mcp_command(
                _args(mcp_action="install", install_all=True,
                      enable=True, with_bootstrap=True)
            )
            _, kwargs = m.call_args
            assert kwargs == {"enable_without_creds": True, "run_bootstrap": True}

    def test_install_no_name_no_all_errors(self, capsys):
        mcp_command(_args(mcp_action="install"))
        out = capsys.readouterr().out
        assert "Specify an entry name or use --all" in out


# ─── argparse shape ─────────────────────────────────────────────────────────────

def _build_parser():
    """Minimal replica of the `hermes mcp install` parser slice."""
    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="command")
    mcp_p = sub.add_parser("mcp")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_action")
    inst = mcp_sub.add_parser("install")
    inst.add_argument("name", nargs="?", default=None)
    inst.add_argument("--all", action="store_true", dest="install_all")
    inst.add_argument("--enable", action="store_true", default=False)
    inst.add_argument("--with-bootstrap", action="store_true", default=False)
    return parser


class TestInstallArgparse:
    def test_all_parses_without_name(self):
        a = _build_parser().parse_args(["mcp", "install", "--all"])
        assert a.command == "mcp"
        assert a.mcp_action == "install"
        assert a.name is None
        assert a.install_all is True

    def test_name_parses(self):
        a = _build_parser().parse_args(["mcp", "install", "supabase"])
        assert a.command == "mcp"
        assert a.name == "supabase"
        assert a.install_all is False

    def test_all_with_flags(self):
        a = _build_parser().parse_args(
            ["mcp", "install", "--all", "--enable", "--with-bootstrap"]
        )
        assert a.install_all is True
        assert a.enable is True
        assert a.with_bootstrap is True
