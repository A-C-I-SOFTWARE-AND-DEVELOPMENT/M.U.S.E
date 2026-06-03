"""Tests for the bounded read-only inline tools + agent phase/tool stream.

These cover the mobile-cockpit "tool visibility" path:

* the inline tools are genuinely read-only, path-traversal safe, redacted,
  and size-capped, and
* the real ``jarvis_responder`` streams the phase rail + tool calls in a
  stable order, surfacing owner-gated actions without executing them.
"""

from __future__ import annotations

from pathlib import Path

from gateway.cockpit import agent as ag
from gateway.cockpit import inline_tools as it


def test_repo_grep_returns_paths_not_contents(tmp_path: Path, monkeypatch):
    # A controlled tiny repo so the bounded scan is deterministic.
    (tmp_path / "a.py").write_text("def jarvis_responder():\n    pass\n")
    (tmp_path / "b.py").write_text("nothing here\n")
    monkeypatch.setenv("HERMES_REPO_ROOT", str(tmp_path))
    res = it.repo_grep("jarvis_responder")
    assert res.name == "repo_grep"
    assert res.status == "OK"
    # Detail is a path list, never the matched line/contents.
    assert "a.py" in (res.detail or "")
    assert "def jarvis_responder" not in (res.detail or "")
    assert "b.py" not in (res.detail or "")


def test_repo_grep_empty_term_fails_cleanly():
    res = it.repo_grep("   ")
    assert res.status == "FAIL"


def test_repo_read_is_path_traversal_safe():
    assert it.repo_read("../../../etc/passwd").status == "FAIL"
    assert it.repo_read("/etc/passwd").status == "FAIL"


def test_repo_read_caps_size(tmp_path: Path, monkeypatch):
    big = tmp_path / "big.py"
    big.write_text("x" * 10_000)
    monkeypatch.setenv("HERMES_REPO_ROOT", str(tmp_path))
    res = it.repo_read("big.py")
    assert res.status == "OK"
    assert "truncated" in res.summary
    # Never returns more than the read cap.
    assert len(res.detail or "") <= it._MAX_READ_BYTES


def test_git_status_branch_not_redacted():
    res = it.git_status()
    # git may be absent in some sandboxes — only assert when it ran.
    if res.status == "OK":
        assert "redacted" not in res.summary


def test_extract_grep_term_prefers_quoted_then_identifier():
    assert it.extract_grep_term('fix "JarvisChatViewModel" please') == "JarvisChatViewModel"
    assert it.extract_grep_term("audit this repo run tests") is None
    assert it.extract_grep_term("look at RoutingJarvisChatGateway") == "RoutingJarvisChatGateway"


def test_responder_streams_phase_rail_in_order():
    chunks = list(ag.jarvis_responder("just say hi", []))
    phases = [c["phase"] for c in chunks if c["type"] == "phase"]
    # Phases are monotonic in the canonical order (a subset may appear).
    order = {name: i for i, name in enumerate(
        ["RECEIVING", "THINKING", "ROUTING", "TOOL", "CODING",
         "RESEARCH", "VERIFICATION", "FINAL"]
    )}
    idx = [order[p] for p in phases]
    assert idx == sorted(idx)
    assert "RECEIVING" in phases and "FINAL" in phases


def test_code_turn_emits_tool_calls_with_start_and_terminal():
    chunks = list(ag.jarvis_responder("fix this bug in JarvisChatViewModel", []))
    tool_calls = [c for c in chunks if c["type"] == "tool_call"]
    assert tool_calls, "a code-shaped turn should run inline tools"
    statuses = {c["status"] for c in tool_calls}
    assert "START" in statuses
    assert statuses & {"OK", "FAIL"}
    # TOOL phase precedes the first tool_call.
    types = [c["type"] for c in chunks]
    first_tool = types.index("tool_call")
    assert "phase" in types[:first_tool]


def test_casual_turn_runs_no_inline_tools():
    chunks = list(ag.jarvis_responder("good morning", []))
    assert not [c for c in chunks if c["type"] == "tool_call"]
