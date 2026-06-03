"""Integration tests for TokenJuice in the agent tool loop.

Exercises the shared ``_tokenjuice_compact`` helper that both the concurrent and
sequential executors call, and asserts structurally that both paths invoke it
before the existing persistence/budget layer (so neither path regresses to
sending raw, unscrubbed output).
"""

import re
from pathlib import Path

import pytest

import agent.tool_executor as te
from tools.tokenjuice import CompactionConfig


class _FakeAgent:
    session_id = "sess-test"


LONG_GIT = (
    "On branch main\nYour branch is up to date with 'origin/main'.\n\n"
    + "\n".join(f"\tmodified:   src/file_{i}.py" for i in range(120))
    + "\n"
)


@pytest.fixture
def enabled_cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    cfg = CompactionConfig(enabled=True, preserve_raw=True)
    monkeypatch.setattr(te, "load_active_config", lambda: cfg)
    return cfg


def test_helper_compacts_string_output(enabled_cfg):
    out = te._tokenjuice_compact(_FakeAgent(), "exec", {"command": "git status"}, LONG_GIT, False, "t1")
    assert len(out) < len(LONG_GIT)
    assert "On branch main" not in out  # git rule noise stripped


def test_helper_scrubs_secret_even_if_not_compacted(enabled_cfg):
    secret = "export API_KEY=supersecretvalue12345"
    out = te._tokenjuice_compact(_FakeAgent(), "exec", {"command": "printenv"}, secret, False, "t2")
    assert "supersecretvalue12345" not in out
    assert "[REDACTED]" in out


def test_helper_preserves_raw_output_on_disk(enabled_cfg, tmp_path):
    raw = LONG_GIT + "\nAPI_KEY=supersecretvalue12345\n"
    te._tokenjuice_compact(_FakeAgent(), "exec", {"command": "git status"}, raw, False, "t3")
    logs = list((tmp_path / "tool-raw" / "sess-test").glob("*.log"))
    assert logs, "raw output log file should exist"
    content = logs[0].read_text(encoding="utf-8")
    # Raw log keeps the FULL pre-scrub output (debuggability), incl. the secret.
    assert "supersecretvalue12345" in content


def test_helper_passthrough_truly_non_string(enabled_cfg):
    # A non-string that is NOT a multimodal envelope is returned unchanged.
    plain = {"not": "multimodal"}
    assert te._tokenjuice_compact(_FakeAgent(), "x", {}, plain, False, "t4") is plain
    assert te._tokenjuice_compact(_FakeAgent(), "x", {}, 12345, False, "t4b") == 12345


def test_helper_multimodal_compacts_text_preserves_images(enabled_cfg):
    long_text = LONG_GIT + "\nAPI_KEY=supersecretvalue12345\n"
    image_part = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAABBBB"}}
    envelope = {
        "_multimodal": True,
        "content": [
            {"type": "text", "text": long_text},
            image_part,
        ],
        "text_summary": long_text,
    }
    out = te._tokenjuice_compact(_FakeAgent(), "exec", {"command": "git status"}, envelope, False, "tm")
    assert te is not None
    # Still a multimodal envelope.
    assert out.get("_multimodal") is True
    text_parts = [p for p in out["content"] if p.get("type") == "text"]
    img_parts = [p for p in out["content"] if p.get("type") == "image_url"]
    # Image block preserved byte-for-byte.
    assert img_parts == [image_part]
    # Text part scrubbed + compacted.
    assert "supersecretvalue12345" not in text_parts[0]["text"]
    assert "[REDACTED]" in text_parts[0]["text"]
    assert len(text_parts[0]["text"]) < len(long_text)
    # text_summary also scrubbed.
    assert "supersecretvalue12345" not in out["text_summary"]


def test_helper_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(te, "load_active_config", lambda: CompactionConfig(enabled=False))
    assert te._tokenjuice_compact(_FakeAgent(), "exec", {"command": "git status"}, LONG_GIT, False, "t5") == LONG_GIT


def test_helper_fail_open(monkeypatch, enabled_cfg):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(te, "compact_tool_output", boom)
    out = te._tokenjuice_compact(_FakeAgent(), "exec", {"command": "git status"}, LONG_GIT, False, "t6")
    assert out == LONG_GIT  # never worse than the original


def test_both_executor_paths_invoke_compaction_before_persistence():
    """Structural guard: concurrent + sequential both call the helper, and the
    call precedes ``maybe_persist_tool_result`` in each path."""
    src = Path(te.__file__).read_text(encoding="utf-8")
    assert src.count("_tokenjuice_compact(") >= 2

    for fn in ("execute_tool_calls_concurrent", "execute_tool_calls_sequential"):
        body = src.split(f"def {fn}(", 1)[1].split("\ndef ", 1)[0]
        compact_at = body.find("_tokenjuice_compact(")
        persist_at = body.find("maybe_persist_tool_result(")
        assert compact_at != -1, f"{fn} must call _tokenjuice_compact"
        assert persist_at != -1, f"{fn} must still call maybe_persist_tool_result"
        assert compact_at < persist_at, f"{fn} must compact before persisting"
