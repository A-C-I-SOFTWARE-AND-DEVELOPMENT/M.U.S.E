"""Tests for the low context length warning in the CLI banner."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def _isolate(tmp_path, monkeypatch):
    """Isolate HERMES_HOME so tests don't touch real config."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))


@pytest.fixture
def cli_obj(_isolate):
    """Create a minimal HermesCLI instance for banner testing."""
    with patch("cli.load_cli_config", return_value={
        "display": {"tool_progress": "new"},
        "terminal": {},
    }), patch("cli.get_tool_definitions", return_value=[]), \
         patch("cli.build_welcome_banner"):
        from cli import HermesCLI
        obj = HermesCLI.__new__(HermesCLI)
        obj.model = "test-model"
        obj.enabled_toolsets = ["hermes-core"]
        obj.compact = False
        obj.console = MagicMock()
        obj.session_id = None
        obj.api_key = "test"
        obj.base_url = ""
        obj.provider = "test"
        obj._provider_source = None
        # Mock agent with context compressor
        obj.agent = SimpleNamespace(
            context_compressor=SimpleNamespace(context_length=None)
        )
        return obj


class TestLowContextWarning:
    """Tests that the CLI warns about low context lengths."""

    def test_no_warning_for_normal_context(self, cli_obj):
        """No warning when context is 32k+."""
        cli_obj.agent.context_compressor.context_length = 32768
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        # Check that no yellow warning was printed
        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 0

    def test_warning_for_low_context(self, cli_obj):
        """Warning shown when context is 4096 (Ollama default)."""
        cli_obj.agent.context_compressor.context_length = 4096
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 1
        assert "4,096" in warning_calls[0]

    def test_warning_for_2048_context(self, cli_obj):
        """Warning shown for 2048 tokens (common LM Studio default)."""
        cli_obj.agent.context_compressor.context_length = 2048
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 1

    def test_no_warning_at_boundary(self, cli_obj):
        """No warning at exactly 8192 — 8192 is borderline but included in warning."""
        cli_obj.agent.context_compressor.context_length = 8192
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 1  # 8192 is still warned about

    def test_no_warning_above_boundary(self, cli_obj):
        """No warning at 16384."""
        cli_obj.agent.context_compressor.context_length = 16384
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 0

    def test_ollama_specific_hint(self, cli_obj):
        """Ollama-specific fix shown when port 11434 detected."""
        cli_obj.agent.context_compressor.context_length = 4096
        cli_obj.base_url = "http://localhost:11434/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        # The Ollama fix command must be shown. It may be accompanied by a
        # CPU/agentic context note that also references OLLAMA_CONTEXT_LENGTH.
        assert any(
            "OLLAMA_CONTEXT_LENGTH" in c and "ollama serve" in c for c in calls
        )

    def test_lm_studio_specific_hint(self, cli_obj):
        """LM Studio-specific fix shown when port 1234 detected."""
        cli_obj.agent.context_compressor.context_length = 2048
        cli_obj.base_url = "http://localhost:1234/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        lms_hints = [c for c in calls if "LM Studio" in c]
        assert len(lms_hints) == 1

    def test_generic_hint_for_other_servers(self, cli_obj):
        """Generic fix shown for unknown servers."""
        cli_obj.agent.context_compressor.context_length = 4096
        cli_obj.base_url = "http://localhost:8080/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        generic_hints = [c for c in calls if "config.yaml" in c]
        assert len(generic_hints) == 1

    def test_no_warning_when_no_context_length(self, cli_obj):
        """No warning when context length is not yet known."""
        cli_obj.agent.context_compressor.context_length = None
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 0


class TestLocalAgenticContextNote:
    """The local-endpoint agentic context note (ctx < 12288, local URL)."""

    def test_local_note_for_low_context_on_local_endpoint(self, cli_obj):
        """Local endpoint at 8192 → emits the OLLAMA_CONTEXT_LENGTH agentic note."""
        cli_obj.agent.context_compressor.context_length = 8192
        cli_obj.base_url = "http://localhost:11434/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        notes = [c for c in calls if "Local tool agents need" in c]
        assert len(notes) == 1
        assert "OLLAMA_CONTEXT_LENGTH" in notes[0]
        assert "NOT OLLAMA_NUM_CTX" in notes[0]

    def test_local_note_fires_in_8192_to_12288_gap(self, cli_obj):
        """Local endpoint at 10240 (above 8192, below 12288) still gets the note."""
        cli_obj.agent.context_compressor.context_length = 10240
        cli_obj.base_url = "http://127.0.0.1:11434/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        notes = [c for c in calls if "Local tool agents need" in c]
        assert len(notes) == 1
        # The generic "too low" warning does NOT fire above 8192.
        too_low = [c for c in calls if "too low" in c]
        assert len(too_low) == 0

    def test_no_local_note_for_remote_endpoint(self, cli_obj):
        """A remote endpoint never gets the local agentic note."""
        cli_obj.agent.context_compressor.context_length = 8192
        cli_obj.base_url = "https://openrouter.ai/api/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        notes = [c for c in calls if "Local tool agents need" in c]
        assert len(notes) == 0

    def test_no_local_note_at_or_above_12288(self, cli_obj):
        """At 12288 the local agentic note no longer fires."""
        cli_obj.agent.context_compressor.context_length = 12288
        cli_obj.base_url = "http://localhost:11434/v1"
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        notes = [c for c in calls if "Local tool agents need" in c]
        assert len(notes) == 0

    def test_no_local_note_when_no_base_url(self, cli_obj):
        """Empty base_url → not local → no note even at low context."""
        cli_obj.agent.context_compressor.context_length = 4096
        cli_obj.base_url = ""
        with patch("cli.get_tool_definitions", return_value=[]), \
             patch("cli.build_welcome_banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        notes = [c for c in calls if "Local tool agents need" in c]
        assert len(notes) == 0

    def test_compact_banner_does_not_crash_on_narrow_terminal(self, cli_obj):
        """Compact mode should still have ctx_len defined for warning logic."""
        cli_obj.agent.context_compressor.context_length = 4096

        with patch("shutil.get_terminal_size", return_value=os.terminal_size((70, 40))), \
             patch("cli._build_compact_banner", return_value="compact banner"):
            cli_obj.show_banner()

        calls = [str(c) for c in cli_obj.console.print.call_args_list]
        warning_calls = [c for c in calls if "too low" in c]
        assert len(warning_calls) == 1
