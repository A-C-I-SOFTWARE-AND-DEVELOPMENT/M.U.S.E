"""Tests for the TokenJuice entry point: pass-through, fail-open, clamp, config."""

import pytest

from tools.tokenjuice import CompactionConfig, compact_tool_output
from tools.tokenjuice.integration import extract_command_argv

LONG_GIT = (
    "On branch main\nYour branch is up to date with 'origin/main'.\n\n"
    + "\n".join(f"\tmodified:   src/file_{i}.py" for i in range(120))
    + "\n"
)


def test_extract_command_argv_shapes():
    assert extract_command_argv({"command": "git status"}) == ("git status", ["git", "status"])
    assert extract_command_argv({"argv": ["git", "diff"]}) == ("git diff", ["git", "diff"])
    assert extract_command_argv({"command": "git", "args": ["log"]}) == ("git log", ["git", "log"])
    assert extract_command_argv({"cmd": "ls -la"}) == ("ls -la", ["ls", "-la"])
    assert extract_command_argv({"path": "x"}) == (None, None)
    assert extract_command_argv("not a dict") == (None, None)


def test_large_output_compacts():
    out, stats = compact_tool_output("exec", {"command": "git status"}, LONG_GIT, 0)
    assert stats.applied
    assert stats.compacted_chars < stats.original_chars
    assert stats.rule_id == "git/status"
    assert len(out) < len(LONG_GIT)


def test_tiny_output_passthrough():
    out, stats = compact_tool_output("exec", {"command": "echo hi"}, "hi", 0)
    assert not stats.applied
    assert out == "hi"
    assert stats.rule_id == "too-small"


def test_incompressible_output_passthrough():
    # Random-ish unique lines over the size floor that the generic rule cannot
    # meaningfully shrink → ratio gate keeps the original.
    body = "\n".join(f"unique-token-{i}-{i*7}-{i*13}" for i in range(40))
    out, stats = compact_tool_output("exec", {"command": "weirdtool"}, body, 0)
    # Either not applied, or applied only if it genuinely shrank.
    if stats.applied:
        assert stats.compacted_chars < stats.original_chars
    else:
        assert out == body


def test_skip_tool_passthrough():
    big = "x" * 5000
    out, stats = compact_tool_output("read_file", {"path": "f"}, big, 0)
    assert not stats.applied
    assert stats.rule_id == "skip-tool"
    assert out == big


def test_disabled_config_passthrough():
    out, stats = compact_tool_output(
        "exec", {"command": "git status"}, LONG_GIT, 0, CompactionConfig(enabled=False)
    )
    assert not stats.applied
    assert out == LONG_GIT


def test_max_inline_chars_clamp():
    cfg = CompactionConfig(max_inline_chars=120, min_ratio_improvement=0.0)
    out, stats = compact_tool_output("exec", {"command": "git status"}, LONG_GIT, 0, cfg)
    assert len(out) <= 120 + len("\n…[tokenjuice: clamped]")
    assert "clamped" in out


def test_fail_open_returns_original(monkeypatch):
    # Force the reducer to raise; entry point must return the original text.
    import tools.tokenjuice.integration as integ

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(integ, "load_rules", boom)
    out, stats = compact_tool_output("exec", {"command": "git status"}, LONG_GIT, 0)
    assert out == LONG_GIT
    assert not stats.applied
    assert stats.rule_id == "error"


def test_failure_exit_code_preserves_more(monkeypatch):
    cfg = CompactionConfig(min_ratio_improvement=0.0, max_inline_chars=100000)
    body = "\n".join(f"build log line {i}" for i in range(300))
    ok, _ = compact_tool_output("exec", {"command": "make"}, body, 0, cfg)
    fail, _ = compact_tool_output("exec", {"command": "make"}, body, 1, cfg)
    assert len(fail) >= len(ok)
