"""Tests for the TokenJuice reducer, text primitives, classifier, and rules."""

import json

import pytest

from tools.tokenjuice import text as tj_text
from tools.tokenjuice.classify import classify
from tools.tokenjuice.loader import load_builtin_rules, load_rules
from tools.tokenjuice.reduce import reduce_output
from tools.tokenjuice.types import (
    JsonRule,
    ReduceOptions,
    ToolExecutionInput,
)


# ── text primitives ────────────────────────────────────────────────────────

def test_strip_ansi_removes_escapes_keeps_unicode():
    assert tj_text.strip_ansi("\x1b[31mred\x1b[0m café 🚀") == "red café 🚀"


def test_dedupe_adjacent():
    assert tj_text.dedupe_adjacent(["a", "a", "b", "b", "a"]) == ["a", "b", "a"]


def test_trim_empty_edges():
    assert tj_text.trim_empty_edges(["", " ", "x", "y", "  ", ""]) == ["x", "y"]


def test_head_tail_width_safe_with_emoji():
    lines = [f"line {i} 🚀 café" for i in range(50)]
    out = tj_text.head_tail(lines, 3, 2)
    assert out[:3] == lines[:3]
    assert out[-2:] == lines[-2:]
    assert any("more line" in ln for ln in out)
    # no character was split — every output line is one of the originals or marker
    assert all(ln in lines or "more line" in ln for ln in out)


def test_head_tail_noop_when_small():
    lines = ["a", "b", "c"]
    assert tj_text.head_tail(lines, 5, 5) == lines


def test_pretty_print_json():
    out = tj_text.maybe_pretty_print_json('{"b":1,"a":2}')
    assert "\n" in out and '"b": 1' in out


def test_pretty_print_json_passthrough_non_json():
    assert tj_text.maybe_pretty_print_json("not json") == "not json"


# ── rules / classification ─────────────────────────────────────────────────

def test_builtin_rules_loaded():
    rules = load_builtin_rules()
    assert len(rules) >= 90
    assert any(r.id == "git/status" for r in rules)
    assert any(r.id == "generic/fallback" for r in rules)


def test_classify_prefers_specific_over_fallback():
    rules = load_rules()
    inp = ToolExecutionInput(tool_name="exec", command="git status", argv=["git", "status"], stdout="x")
    rule = classify(inp, rules)
    assert rule is not None and rule.id == "git/status"


def test_classify_falls_back_to_generic():
    rules = load_rules()
    inp = ToolExecutionInput(tool_name="exec", command="some-unknown-tool --x", stdout="x")
    rule = classify(inp, rules)
    assert rule is not None and rule.id == "generic/fallback"


def test_classify_none_when_no_rules():
    inp = ToolExecutionInput(tool_name="exec", stdout="x")
    assert classify(inp, []) is None


# ── reduce behaviors ───────────────────────────────────────────────────────

GIT_STATUS = (
    "On branch main\nYour branch is up to date with 'origin/main'.\n\n"
    + "\n".join(f"\tmodified:   src/file_{i}.py" for i in range(60))
    + '\nnothing added to commit but untracked files present (use "git add" to track)\n'
)


def test_reduce_git_status_drops_noise_and_counts():
    rules = {r.id: r for r in load_rules()}
    inp = ToolExecutionInput(tool_name="exec", argv=["git", "status"], stdout=GIT_STATUS, exit_code=0)
    out = reduce_output(rules["git/status"], inp, ReduceOptions())
    assert "On branch main" not in out  # skip pattern removed
    assert "modified file" in out  # counter summary present
    assert len(out) < len(GIT_STATUS)


def test_reduce_failure_preserves_more_than_success():
    rules = {r.id: r for r in load_rules()}
    fallback = rules["generic/fallback"]
    body = "\n".join(f"log line {i}" for i in range(200))
    ok = reduce_output(fallback, ToolExecutionInput("exec", stdout=body, exit_code=0), ReduceOptions())
    fail = reduce_output(fallback, ToolExecutionInput("exec", stdout=body, exit_code=1), ReduceOptions())
    assert len(fail.splitlines()) > len(ok.splitlines())


def test_reduce_invalid_regex_in_rule_does_not_crash():
    bad = JsonRule.from_dict(
        {
            "id": "test/bad",
            "family": "test",
            "match": {},
            "filters": {"skipPatterns": ["(unclosed"]},
            "counters": [{"name": "x", "pattern": "(also bad"}],
        }
    )
    inp = ToolExecutionInput(tool_name="exec", stdout="a\nb\nc", exit_code=0)
    # Must not raise.
    reduce_output(bad, inp, ReduceOptions())


def test_reduce_keep_patterns_filter():
    rule = JsonRule.from_dict(
        {
            "id": "test/keep",
            "family": "test",
            "match": {},
            "filters": {"keepPatterns": ["ERROR"]},
        }
    )
    body = "info a\nERROR boom\ninfo b\nERROR bang"
    out = reduce_output(rule, ToolExecutionInput("exec", stdout=body), ReduceOptions())
    assert "info a" not in out
    assert "ERROR boom" in out and "ERROR bang" in out


def test_reduce_on_empty_message():
    rule = JsonRule.from_dict(
        {
            "id": "test/empty",
            "family": "test",
            "match": {},
            "filters": {"skipPatterns": [".*"]},
            "onEmpty": "(no output)",
        }
    )
    out = reduce_output(rule, ToolExecutionInput("exec", stdout="a\nb\nc"), ReduceOptions())
    assert out == "(no output)"
