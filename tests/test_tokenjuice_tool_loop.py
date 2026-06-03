"""Integration tests for TokenJuice in the agent tool loop.

Exercises the ``_tokenjuice_compact`` primitive (scrub / compact / raw-preserve)
and the shared ``prepare_tool_result_for_context`` seam that both the concurrent
and sequential executors route through. Asserts structurally that both paths use
the single seam (no drift) and that the seam persists oversized output *before*
TokenJuice clamping, so a large result keeps its recoverable persisted/truncated
path instead of being clamped away.
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


def test_both_executor_paths_use_shared_prepare_seam():
    """Structural guard: concurrent + sequential both route results through the
    single ``prepare_tool_result_for_context`` seam, and neither inlines the
    persistence or TokenJuice layers — keeping the two paths from drifting and
    from reintroducing the clamp-before-persist bug."""
    src = Path(te.__file__).read_text(encoding="utf-8")
    assert "def prepare_tool_result_for_context(" in src

    for fn in ("execute_tool_calls_concurrent", "execute_tool_calls_sequential"):
        body = src.split(f"def {fn}(", 1)[1].split("\ndef ", 1)[0]
        assert "prepare_tool_result_for_context(" in body, (
            f"{fn} must ready results via the shared prepare seam"
        )
        # Ordering is owned by the seam; the executor paths must not inline
        # persistence or compaction themselves.
        assert "maybe_persist_tool_result(" not in body, (
            f"{fn} must not inline persistence — the shared seam owns it"
        )
        assert "compact_tool_output(" not in body and "_tokenjuice_compact(" not in body, (
            f"{fn} must not inline TokenJuice — the shared seam owns it"
        )


def test_prepare_seam_persists_oversized_before_clamping():
    """The shared seam must run oversized-output persistence *before* TokenJuice
    compaction, so a large result keeps its recoverable persisted/truncated path
    rather than being clamped to the inline ceiling first (the original bug)."""
    src = Path(te.__file__).read_text(encoding="utf-8")
    body = src.split("def prepare_tool_result_for_context(", 1)[1].split("\ndef ", 1)[0]
    first_persist = body.find("maybe_persist_tool_result(")
    first_compact = body.find("compact_tool_output(")
    assert first_persist != -1, "seam must persist oversized output"
    assert first_compact != -1, "seam must still run TokenJuice compaction"
    assert first_persist < first_compact, (
        "oversized persistence must precede TokenJuice compaction in the seam"
    )
