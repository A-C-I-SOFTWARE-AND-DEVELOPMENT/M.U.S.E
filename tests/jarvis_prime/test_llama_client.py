"""Tests for the native llama-server client (Phase 3)."""

from __future__ import annotations

import json
import threading
from typing import Any, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hermes_cli.jarvis_prime.llama_client import (
    TASK_SAMPLING_PARAMS,
    LlamaServerClient,
    LlamaServerError,
    SpecDecodeConfig,
    build_launch_command,
    get_sampling_params,
)


def test_completion_payload_contract() -> None:
    captured: dict = {}

    def fake_post(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = dict(payload)
        return {
            "content": "ok",
            "tokens_predicted": 5,
            "tokens_cached": 7,
            "timings": {"prompt_ms": 1.5, "predicted_ms": 2.5},
        }

    client = LlamaServerClient("http://x:1/", post=fake_post)
    result = client.completion("hello", grammar='root ::= "a"', id_slot=2, n_predict=64)
    assert captured["url"] == "http://x:1/completion"
    assert captured["payload"] == {
        "prompt": "hello",
        "n_predict": 64,
        "cache_prompt": True,
        "temperature": 0.0,
        "seed": 0,
        "grammar": 'root ::= "a"',
        "id_slot": 2,
    }
    assert (result.text, result.tokens_predicted, result.tokens_cached) == ("ok", 5, 7)
    assert (result.prompt_ms, result.predict_ms) == (1.5, 2.5)


def test_completion_omits_unset_optionals_and_reads_timings_fallback() -> None:
    def fake_post(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        assert "grammar" not in payload and "id_slot" not in payload
        return {"content": "x", "timings": {"predicted_n": 3, "cache_n": 9}}

    result = LlamaServerClient("http://x:1", post=fake_post).completion("p")
    assert result.tokens_predicted == 3
    assert result.tokens_cached == 9


def test_completion_raises_on_malformed_response() -> None:
    client = LlamaServerClient("http://x:1", post=lambda u, p, t: {"error": "boom"})
    with pytest.raises(LlamaServerError, match="unexpected /completion response"):
        client.completion("p")


def test_spec_decode_config_args() -> None:
    spec = SpecDecodeConfig("/models/draft.gguf", draft_max=8, draft_min=2, p_min=0.5)
    assert spec.to_server_args() == (
        "--spec-draft-model",
        "/models/draft.gguf",
        "--spec-draft-n-max",
        "8",
        "--spec-draft-n-min",
        "2",
        "--spec-draft-p-min",
        "0.5",
    )


def test_build_launch_command_full() -> None:
    cmd = build_launch_command(
        "/models/gemma.gguf",
        port=8123,
        n_slots=2,
        slot_save_path="/tmp/kv",
        spec=SpecDecodeConfig("/models/draft.gguf"),
        swa_full=True,
    )
    assert cmd[:3] == ("llama-server", "-m", "/models/gemma.gguf")
    assert ("--parallel", "2") == cmd[cmd.index("--parallel") : cmd.index("--parallel") + 2]
    assert "--slot-save-path" in cmd and "/tmp/kv" in cmd
    assert "--swa-full" in cmd
    assert "--spec-draft-model" in cmd


class _StubHandler(BaseHTTPRequestHandler):
    """Minimal llama-server stub: /health + /completion with cache emulation."""

    slot_cache: dict[int, int] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (http.server API)
        del format, args  # silence request logging

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path == "/health":
            self._send({"status": "ok"})
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/completion":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        slot = int(payload.get("id_slot", -1))
        cached = self.slot_cache.get(slot, 0)
        prompt_tokens = len(str(payload.get("prompt", "")).split())
        if payload.get("cache_prompt") and slot >= 0:
            self.slot_cache[slot] = prompt_tokens
        content = "{}" if payload.get("grammar") else "free text"
        self._send(
            {
                "content": content,
                "tokens_predicted": 2,
                "tokens_cached": cached,
                "timings": {"prompt_ms": 1.0, "predicted_ms": 1.0},
            }
        )

    def _send(self, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def stub_server():
    _StubHandler.slot_cache = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


def test_real_http_roundtrip_and_slot_cache_growth(stub_server: str) -> None:
    client = LlamaServerClient(stub_server, timeout=10)
    assert client.health() is True
    first = client.completion("one two three four", id_slot=1)
    second = client.completion("one two three four five", id_slot=1)
    assert first.tokens_cached == 0
    assert second.tokens_cached == 4  # tokens cached by the first same-slot call


def test_health_false_when_unreachable() -> None:
    assert LlamaServerClient("http://127.0.0.1:9", timeout=2).health() is False


# ---------------------------------------------------------------------------
# Per-task sampling presets (#10) — opt-in; greedy default preserved.
# ---------------------------------------------------------------------------


def test_default_completion_is_greedy_and_sets_no_extra_sampling_keys() -> None:
    """With no sampling_params the payload is the legacy greedy decode."""
    captured: dict = {}

    def fake_post(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        captured["payload"] = dict(payload)
        return {"content": "x"}

    LlamaServerClient("http://x:1", post=fake_post).completion("p")
    payload = captured["payload"]
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 0
    # No extra sampling fields leak when no preset is supplied.
    for key in ("top_p", "top_k", "repeat_penalty", "min_p"):
        assert key not in payload


def test_sampling_params_overlay_recognized_keys() -> None:
    """A preset overlays temperature/top_p/top_k/repeat_penalty/min_p; junk drops."""
    captured: dict = {}

    def fake_post(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        captured["payload"] = dict(payload)
        return {"content": "x"}

    params = dict(get_sampling_params("creative"))
    params["frequency_penalty"] = 9.9  # not a recognized key → must be dropped
    LlamaServerClient("http://x:1", post=fake_post).completion("p", sampling_params=params)
    payload = captured["payload"]
    assert payload["temperature"] == 0.85
    assert payload["top_p"] == 0.95
    assert payload["top_k"] == 60
    assert payload["repeat_penalty"] == 1.08
    assert payload["min_p"] == 0.05
    assert "frequency_penalty" not in payload


def test_get_sampling_params_matrix_values_and_copy() -> None:
    """Presets match the verified matrix and are returned as a mutable copy."""
    assert get_sampling_params("coding") == {
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.05,
    }
    assert get_sampling_params("reasoning")["temperature"] == 0.6
    assert get_sampling_params("fast")["temperature"] == 0.4
    assert get_sampling_params("vision") == {"temperature": 0.3, "top_p": 0.9}
    # Case-insensitive, and a copy (mutating the result must not poison the map).
    got = get_sampling_params("CODING")
    got["temperature"] = 1.0
    assert TASK_SAMPLING_PARAMS["coding"]["temperature"] == 0.1


def test_get_sampling_params_unknown_lane_is_none() -> None:
    assert get_sampling_params(None) is None
    assert get_sampling_params("") is None
    assert get_sampling_params("no-such-lane") is None
