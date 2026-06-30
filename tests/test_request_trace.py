"""Tests for the opt-in per-request observability layer (hermes_cli.request_trace).

Covers the gating contract (off by default → shared no-op, no events), the
counter/timing logic, endpoint + local/remote derivation, and that an enabled
trace emits exactly one ``request_trace`` record through the cockpit event log.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import event_log
from hermes_cli import request_trace
from hermes_cli.request_trace import RequestTrace, current, lifecycle_event


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HERMES_HOME so the event log writes under tmp_path."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Default state: tracing off (no env override, default config flag False).
    monkeypatch.delenv("HERMES_REQUEST_TRACE", raising=False)
    return tmp_path


# ── gating: off by default ──────────────────────────────────────────────────


def test_disabled_by_default_returns_noop(home: Path) -> None:
    trace = RequestTrace.start(model="m", provider="p", api_mode="chat_completions")
    assert trace.enabled is False
    # All mutations are no-ops and emit writes nothing.
    trace.add_api_call(1.2)
    trace.add_tool_calls(3)
    trace.add_parse_error()
    trace.add_exec_failure()
    trace.record_fallback("other", "rate_limit")
    trace.mark_first_token()
    trace.emit()
    assert event_log.read_since_offset(0)[0] == []


def test_lifecycle_event_noop_when_disabled(home: Path) -> None:
    lifecycle_event("load", model="m", ok=True, dur_ms=5)
    assert event_log.read_since_offset(0)[0] == []


# ── enabled via env override ────────────────────────────────────────────────


def test_enabled_trace_emits_one_record(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_REQUEST_TRACE", "1")
    trace = RequestTrace.start(
        model="qwen", provider="lmstudio",
        base_url="http://127.0.0.1:1234/v1", api_mode="chat_completions",
        session_id="sess-1",
    )
    assert trace.enabled is True
    assert trace.endpoint == "openai_v1_chat_completions"
    assert trace.is_remote is False  # loopback → local

    trace.add_api_call(0.5)
    trace.add_api_call(0.25)
    trace.add_tool_calls(2)
    trace.add_parse_error()
    trace.add_exec_failure()
    trace.record_fallback("gpt-4o", "provider_error")
    trace.mark_first_token()
    trace.emit()

    records, _ = event_log.read_since_offset(0)
    trace_records = [r for r in records if r["message"] == "request_trace"]
    assert len(trace_records) == 1
    attrs = trace_records[0]["attributes"]
    assert attrs["model"] == "qwen"
    assert attrs["provider"] == "lmstudio"
    assert attrs["endpoint"] == "openai_v1_chat_completions"
    assert attrs["is_remote"] is False
    assert attrs["api_calls"] == 2
    assert attrs["api_latency_ms"] == 750
    assert attrs["tool_calls"] == 2
    assert attrs["tool_parse_errors"] == 1
    assert attrs["tool_exec_failures"] == 1
    assert attrs["fallback_used"] is True
    assert attrs["fallback_model"] == "gpt-4o"
    assert attrs["fallback_reason"] == "provider_error"
    assert attrs["first_token_ms"] is not None
    assert attrs["total_latency_ms"] >= 0
    assert attrs["session_id"] == "sess-1"


def test_enabled_lifecycle_event(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_REQUEST_TRACE", "1")
    lifecycle_event(
        "unload", model="qwen", provider="lmstudio", reason="manual_switch",
        ok=True, base_url="http://10.0.0.5:1234/v1", session_id="sess-2",
    )
    records, _ = event_log.read_since_offset(0)
    life = [r for r in records if r["message"] == "model_lifecycle"]
    assert len(life) == 1
    attrs = life[0]["attributes"]
    assert attrs["event"] == "unload"
    assert attrs["reason"] == "manual_switch"
    assert attrs["ok"] is True
    assert attrs["is_remote"] is True  # non-loopback host → remote


# ── derivation helpers ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "api_mode,expected",
    [
        ("chat_completions", "openai_v1_chat_completions"),
        ("anthropic_messages", "anthropic_v1_messages"),
        ("codex_responses", "openai_v1_responses"),
        ("", "unknown"),
        ("something_new", "something_new"),
    ],
)
def test_endpoint_mapping(api_mode: str, expected: str) -> None:
    assert request_trace._endpoint_for(api_mode) == expected


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("http://127.0.0.1:1234/v1", False),
        ("http://localhost:1234/v1", False),
        ("http://192.168.1.50:1234/v1", True),
        ("https://api.example.com/v1", True),
        ("", None),
        (None, None),
    ],
)
def test_is_remote(base_url, expected) -> None:
    assert request_trace._is_remote(base_url) is expected


# ── the current() accessor ──────────────────────────────────────────────────


def test_current_returns_noop_for_bare_object(home: Path) -> None:
    class _Bare:
        pass

    trace = current(_Bare())
    assert trace.enabled is False
    # Safe to call through it.
    trace.add_tool_calls(5)
    trace.emit()


def test_first_token_recorded_once(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_REQUEST_TRACE", "1")
    trace = RequestTrace.start(model="m", provider="p", api_mode="chat_completions")
    trace.mark_first_token()
    first = trace.first_token_ms
    assert first is not None
    trace.mark_first_token()  # second call must not overwrite
    assert trace.first_token_ms == first
