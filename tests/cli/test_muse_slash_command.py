"""Tests for the /muse slash command — no-arg pulls up the muse TUI.

/muse (and /m) with no intent activates the muse "singularity" skin,
persists it, and re-renders the banner. Other aliases (/jarvis, /jp,
/jarvis-prime) keep the usage message, echoing the alias the user typed.
With an intent, every alias routes to the JarvisPrime runtime unchanged.
"""

import builtins
from unittest.mock import MagicMock, patch

import pytest

from cli import HermesCLI
from hermes_cli.skin_engine import get_active_skin_name, set_active_skin


def _make_cli_stub():
    cli = HermesCLI.__new__(HermesCLI)
    cli._app = None
    cli._invalidate = MagicMock()
    cli.show_banner = MagicMock()
    cli._apply_tui_skin_style = MagicMock(return_value=False)
    return cli


@pytest.fixture(autouse=True)
def _restore_skin():
    original = get_active_skin_name()
    yield
    set_active_skin(original)


class TestmuseNoArgActivatesTui:
    def test_muse_no_arg_activates_singularity_skin(self):
        cli = _make_cli_stub()
        set_active_skin("default")

        with patch("cli.save_config_value", return_value=True) as save:
            cli._handle_jarvis_prime_slash("/muse")

        assert get_active_skin_name() == "singularity"
        save.assert_called_once_with("display.skin", "singularity")
        cli.show_banner.assert_called_once_with()

    def test_m_alias_no_arg_activates_tui(self):
        cli = _make_cli_stub()
        set_active_skin("default")

        with patch("cli.save_config_value", return_value=True):
            cli._handle_jarvis_prime_slash("/m")

        assert get_active_skin_name() == "singularity"
        cli.show_banner.assert_called_once_with()

    def test_muse_no_arg_skips_persist_when_already_singularity(self):
        cli = _make_cli_stub()
        set_active_skin("singularity")

        with patch("cli.save_config_value", return_value=True) as save:
            cli._handle_jarvis_prime_slash("/muse")

        save.assert_not_called()
        cli.show_banner.assert_called_once_with()

    def test_muse_no_arg_never_constructs_jarvis_prime(self):
        cli = _make_cli_stub()
        real_import = builtins.__import__

        def deny_jarvis_runtime(name, *args, **kwargs):
            if "jarvis_prime.runtime" in name:
                raise AssertionError("/muse no-arg must not import JarvisPrime")
            return real_import(name, *args, **kwargs)

        with patch("cli.save_config_value", return_value=True), \
                patch("builtins.__import__", side_effect=deny_jarvis_runtime):
            cli._handle_jarvis_prime_slash("/muse")

        cli.show_banner.assert_called_once_with()

    def test_muse_no_arg_prints_welcome_and_hints(self):
        cli = _make_cli_stub()
        set_active_skin("singularity")

        with patch("cli._cprint") as cprint:
            cli._handle_jarvis_prime_slash("/muse")

        out = "\n".join(str(call.args[0]) for call in cprint.call_args_list)
        assert "muse" in out
        assert "/muse <intent>" in out


class TestJarvisAliasesKeepUsage:
    @pytest.mark.parametrize("alias", ["jarvis", "jp", "jarvis-prime"])
    def test_no_arg_prints_usage_echoing_alias(self, alias, capsys):
        cli = _make_cli_stub()
        set_active_skin("default")

        cli._handle_jarvis_prime_slash(f"/{alias}")

        out = capsys.readouterr().out
        assert f"usage: /{alias} <intent> | /{alias} stop" in out
        assert get_active_skin_name() == "default"
        cli.show_banner.assert_not_called()


class TestIntentRouting:
    def test_muse_intent_forwards_to_jarvis_prime_handle(self, capsys):
        cli = _make_cli_stub()

        jp = MagicMock()
        turn = jp.handle.return_value
        turn.classification.mode.value = "strategy"
        turn.classification.confidence = 0.9
        turn.route.target.value = "council"
        turn.route.rationale = "multi-step plan"
        turn.route.delegate_to = None
        turn.route.pending_actions = []
        turn.research_brief = None

        with patch(
            "hermes_cli.jarvis_prime.runtime.JarvisPrime", return_value=jp
        ):
            cli._handle_jarvis_prime_slash("/muse plan my week")

        jp.handle.assert_called_once_with("plan my week")
        out = capsys.readouterr().out
        assert "Mode: strategy" in out
        cli.show_banner.assert_not_called()

    def test_muse_stop_maps_to_emergency_stop(self, capsys):
        cli = _make_cli_stub()

        jp = MagicMock()
        jp.stop.return_value = {
            "cleared": 0,
            "cleared_actions": 0,
            "tick_disabled": True,
        }

        with patch(
            "hermes_cli.jarvis_prime.runtime.JarvisPrime", return_value=jp
        ):
            cli._handle_jarvis_prime_slash("/muse stop")

        jp.stop.assert_called_once_with(reason="cli_user_requested")
        assert "muse stopped" in capsys.readouterr().out
