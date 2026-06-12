"""Tests for the friendly failure paths of model/toolset switching.

/model should suggest close matches when a lookup fails, and the no-arg
picker should surface inventory errors instead of silently claiming no
providers are authenticated.
"""

from unittest.mock import MagicMock, patch

from cli import HermesCLI
from hermes_cli.model_switch import _suggest_close_models


class TestSuggestCloseModels:
    def test_typo_of_known_alias_is_suggested(self):
        assert "sonnet" in _suggest_close_models("sonet", "")

    def test_garbage_input_yields_no_suggestions(self):
        assert _suggest_close_models("zzqqxxvv", "") == []

    def test_catalog_failure_is_swallowed(self):
        with patch(
            "hermes_cli.model_switch.list_provider_models",
            side_effect=RuntimeError("catalog offline"),
        ):
            # Alias pool still works even when the provider catalog raises.
            assert "sonnet" in _suggest_close_models("sonet", "openrouter")


class TestModelPickerInventoryErrors:
    def _make_cli_stub(self):
        cli = HermesCLI.__new__(HermesCLI)
        cli.provider = "openrouter"
        cli.model = "test-model"
        cli.base_url = ""
        cli.api_key = ""
        return cli

    def test_inventory_failure_prints_actionable_error(self):
        cli = self._make_cli_stub()

        with patch(
            "hermes_cli.inventory.load_picker_context",
            side_effect=RuntimeError("config.yaml unreadable"),
        ), patch("cli._cprint") as cprint:
            cli._handle_model_switch("/model")

        out = "\n".join(str(c.args[0]) for c in cprint.call_args_list)
        assert "Could not load the model inventory" in out
        assert "config.yaml unreadable" in out
        assert "muse doctor" in out

    def test_genuinely_empty_inventory_keeps_no_providers_message(self):
        cli = self._make_cli_stub()

        ctx = MagicMock()
        ctx.with_overrides.return_value = ctx
        ctx.user_providers = None
        ctx.custom_providers = None

        with patch("hermes_cli.inventory.load_picker_context", return_value=ctx), patch(
            "hermes_cli.inventory.build_models_payload",
            return_value={"providers": []},
        ), patch("cli._cprint") as cprint:
            cli._handle_model_switch("/model")

        out = "\n".join(str(c.args[0]) for c in cprint.call_args_list)
        assert "No authenticated providers found." in out
        assert "Could not load the model inventory" not in out
