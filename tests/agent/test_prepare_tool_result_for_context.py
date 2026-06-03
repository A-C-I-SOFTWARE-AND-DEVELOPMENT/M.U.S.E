"""Unit tests for ``agent.tool_executor.prepare_tool_result_for_context``.

This is the single seam both the sequential and concurrent tool paths use to
ready a tool result for the model context. The ordering it guarantees —
oversized-output **persistence before** TokenJuice clamping — is the fix for the
pipeline bug where a 150k result was clamped to the inline ceiling and lost its
recoverable ``<persisted-output>`` / ``[Truncated]`` path (the model would only
see ``…[tokenjuice: clamped]``).

No sandbox env is registered for the task here, so persistence falls back to the
inline ``[Truncated: …]`` form — itself a recoverable contract marker that
proves persistence (not clamping) handled the oversized result.
"""

from __future__ import annotations

import glob
import os
import types

import pytest

from agent.tool_executor import prepare_tool_result_for_context

# Mirrors tools/budget_config.py: DEFAULT_RESULT_SIZE_CHARS.
THRESHOLD = 100_000


@pytest.fixture()
def fake_agent(tmp_path, monkeypatch):
    # Raw debug log + any sandbox writes resolve under a tmp HERMES_HOME.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return types.SimpleNamespace(session_id="sess-1")


def _prepare(fake_agent, tool_name, result, tool_use_id, args=None, is_error=False):
    return prepare_tool_result_for_context(
        fake_agent, tool_name, args or {}, result, is_error, tool_use_id, "task-1",
    )


def test_oversized_output_persists_instead_of_only_clamping(fake_agent):
    # Regression: a 150k result must be persisted/truncated (recoverable),
    # never clamped away by TokenJuice before persistence runs.
    out = _prepare(fake_agent, "web_search", "x" * 150_000, "c1")
    assert len(out) < 150_000
    assert ("Truncated" in out or "<persisted-output>" in out), (
        "oversized output must keep a recoverable persistence marker, not only "
        "the TokenJuice clamp marker"
    )


def test_medium_output_tokenjuice_clamps_below_threshold(fake_agent):
    # Below the persistence threshold, TokenJuice compaction/clamping still runs.
    src = "x" * 5_000
    out = _prepare(fake_agent, "web_search", src, "c2")
    assert len(out) < len(src)
    assert "tokenjuice: clamped" in out
    # It never reached the persistence threshold, so it is not persisted.
    assert "<persisted-output>" not in out
    assert "Truncated" not in out


def test_secret_scrubbed_in_model_output_but_preserved_in_raw_debug(fake_agent):
    secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    payload = secret + "\n" + ("y" * 200_000)
    out = _prepare(fake_agent, "web_search", payload, "c3")

    # Model-readable output is scrubbed before it is persisted/truncated.
    assert secret not in out
    assert ("Truncated" in out or "<persisted-output>" in out)

    # The raw debug log keeps the pre-scrub secret (gitignored, never model-read).
    raw_files = glob.glob(
        os.path.join(os.environ["HERMES_HOME"], "tool-raw", "*", "c3.log")
    )
    assert raw_files, "expected a raw debug log for the tool call"
    assert any(secret in open(p, encoding="utf-8").read() for p in raw_files), (
        "raw debug log must preserve the unscrubbed output for debugging"
    )


def test_read_file_threshold_stays_pinned(fake_agent):
    # read_file is pinned to an infinite persistence threshold (and is a
    # TokenJuice skip-tool) to avoid persist->read->persist loops; a large
    # read_file result passes through unpersisted.
    out = _prepare(fake_agent, "read_file", "x" * 150_000, "c4", args={"path": "f"})
    assert "<persisted-output>" not in out
    assert "Truncated" not in out


def test_non_string_non_multimodal_passes_through(fake_agent):
    sentinel = {"some": "dict", "not": "multimodal"}
    out = _prepare(fake_agent, "web_search", sentinel, "c5")
    assert out is sentinel
