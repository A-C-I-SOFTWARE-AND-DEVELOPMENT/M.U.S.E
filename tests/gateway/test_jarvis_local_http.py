"""Tests for the Jarvis local chat endpoint wire contract + transport."""

from __future__ import annotations

import json
import urllib.request

from gateway import jarvis_local_http as jh


def test_chunk_builders_match_kotlin_contract():
    assert jh.thinking() == {"type": "thinking"}
    assert jh.working("Searching") == {"type": "working", "label": "Searching"}
    assert jh.tone("serious") == {"type": "tone", "tone": "SERIOUS"}
    assert jh.body("hi") == {"type": "body", "text": "hi"}
    assert jh.detail("more") == {"type": "detail", "text": "more"}
    assert jh.done() == {"type": "done"}
    assert jh.error("boom", "retry") == {"type": "error", "message": "boom", "retryHint": "retry"}
    # retryHint omitted when not supplied
    assert "retryHint" not in jh.error("boom")


def test_encode_stream_is_newline_delimited_json():
    lines = list(jh.encode_stream([jh.thinking(), jh.body("x"), jh.done()]))
    assert all(line.endswith(b"\n") for line in lines)
    parsed = [json.loads(line) for line in lines]
    assert [p["type"] for p in parsed] == ["thinking", "body", "done"]


def test_echo_responder_streams_thinking_body_done():
    chunks = list(jh.echo_responder("hello", []))
    assert [c["type"] for c in chunks] == ["thinking", "body", "done"]
    assert "hello" in chunks[1]["text"]


def test_server_round_trip_streams_jsonl():
    def responder(prompt, history):
        yield jh.thinking()
        yield jh.working("thinking it through")
        yield jh.body(f"reply to {prompt}")
        yield jh.done()

    server = jh.serve(responder=responder, port=0)  # ephemeral port
    try:
        port = server.server_address[1]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{jh.CHAT_PATH}",
            data=json.dumps({"prompt": "ping", "history": []}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode()
        types = [json.loads(line)["type"] for line in text.splitlines() if line.strip()]
        assert types == ["thinking", "working", "body", "done"]
        assert "ping" in text
    finally:
        server.shutdown()


def test_unknown_path_returns_error_chunk():
    server = jh.serve(port=0)
    try:
        port = server.server_address[1]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/nope",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTP error")
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read().decode())
            assert payload["type"] == "error"
    finally:
        server.shutdown()
