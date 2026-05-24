"""Tests for the voice-intake (text-path) helpers.

The CI environment has no microphone, no sounddevice install, and no
faster-whisper model — but the *text* path through the voice module is
where almost every regression lands (keybinding parsing, config shape
tolerance, status rendering). Those helpers are pure and have zero
audio deps, so they are safe to test everywhere.

The audio-capture entry points (``start_recording`` /
``start_continuous``) are deliberately *not* exercised — they are
covered by integration tests on machines with audio hardware.
"""

from __future__ import annotations

import sys

import pytest

from hermes_cli.voice import (
    format_voice_record_key_for_status,
    normalize_voice_record_key_for_prompt_toolkit,
    voice_record_key_from_config,
)


# ── voice_record_key_from_config ──────────────────────────────────────


class TestConfigShapeTolerance:
    def test_none_config(self) -> None:
        assert voice_record_key_from_config(None) is None

    def test_non_dict_config(self) -> None:
        assert voice_record_key_from_config("true") is None
        assert voice_record_key_from_config(True) is None
        assert voice_record_key_from_config(42) is None

    def test_missing_voice_block(self) -> None:
        assert voice_record_key_from_config({}) is None

    def test_voice_as_bool_falls_back_to_none(self) -> None:
        assert voice_record_key_from_config({"voice": True}) is None
        assert voice_record_key_from_config({"voice": "ctrl+b"}) is None

    def test_voice_as_dict_returns_record_key(self) -> None:
        cfg = {"voice": {"record_key": "ctrl+space"}}
        assert voice_record_key_from_config(cfg) == "ctrl+space"

    def test_voice_dict_without_record_key(self) -> None:
        cfg = {"voice": {"engine": "whisper"}}
        assert voice_record_key_from_config(cfg) is None


# ── normalize_voice_record_key_for_prompt_toolkit ─────────────────────


class TestKeyNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ctrl+b", "c-b"),
            ("control+o", "c-o"),
            ("alt+r", "a-r"),
            ("option+r", "a-r"),
            ("CTRL+B", "c-b"),
            ("ctrl+space", "c-space"),
            ("ctrl+return", "c-enter"),
            ("alt+escape", "a-escape"),
        ],
    )
    def test_well_formed_keys(self, raw: str, expected: str) -> None:
        assert normalize_voice_record_key_for_prompt_toolkit(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "",
            "   ",
            42,
            True,
            "b",  # bare char (no modifier)
            "ctrl+alt+r",  # multi modifier
            "shift+b",  # unsupported modifier
            "ctrl+spcae",  # typo'd named key
        ],
    )
    def test_malformed_falls_back_to_default(self, raw) -> None:
        assert normalize_voice_record_key_for_prompt_toolkit(raw) == "c-b"

    @pytest.mark.parametrize("char", ["c", "d", "l"])
    def test_reserved_ctrl_chars_fall_back(self, char: str) -> None:
        assert (
            normalize_voice_record_key_for_prompt_toolkit(f"ctrl+{char}") == "c-b"
        )

    @pytest.mark.parametrize("mod", ["super", "win", "windows"])
    def test_super_modifier_falls_back(self, mod: str) -> None:
        assert normalize_voice_record_key_for_prompt_toolkit(f"{mod}+b") == "c-b"


# ── format_voice_record_key_for_status ────────────────────────────────


class TestKeyStatusFormatting:
    def test_ctrl_chord(self) -> None:
        assert format_voice_record_key_for_status("ctrl+b") == "Ctrl+B"

    def test_alt_chord(self) -> None:
        assert format_voice_record_key_for_status("alt+r") == "Alt+R"

    def test_named_key_is_title_cased(self) -> None:
        assert format_voice_record_key_for_status("ctrl+space") == "Ctrl+Space"

    def test_invalid_input_renders_default(self) -> None:
        assert format_voice_record_key_for_status(None) == "Ctrl+B"
        assert format_voice_record_key_for_status("garbage") == "Ctrl+B"

    @pytest.mark.skipif(sys.platform == "darwin", reason="darwin guards alt+c|d|l")
    def test_alt_letter_on_non_mac(self) -> None:
        # Outside macOS, alt+c is a perfectly fine binding.
        assert format_voice_record_key_for_status("alt+c") == "Alt+C"
