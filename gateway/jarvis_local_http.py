"""Local JSONL chat endpoint for the Jarvis Prime Android cockpit.

The Android app's ``HttpJarvisChatGateway`` POSTs to
``http://127.0.0.1:8765/v1/jarvis/chat`` and reads a newline-delimited
JSON stream back. This module owns the *wire contract* for that stream
and a tiny stdlib HTTP server that speaks it, so the phone's floating
avatar reflects the **real** agent instead of the mock.

Design goals:

* The chunk framing (``thinking`` / ``working`` / ``tone`` / ``body`` /
  ``detail`` / ``done`` / ``error``) is pure and unit-tested — it
  matches ``JarvisChatChunk`` 1:1 on the Kotlin side.
* The server is transport-only: it delegates token production to an
  injected ``responder`` coroutine/generator, so the heavy agent wiring
  lives in the runtime, not here, and tests can drive it with a fake
  responder.
* No third-party web framework — ``http.server`` keeps this dependency
  free and safe to run on-device under Termux.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Iterable, Iterator

CHAT_PATH = "/v1/jarvis/chat"

# A responder takes (prompt, history) and yields chat chunks (dicts).
Responder = Callable[[str, list[dict]], Iterable[dict]]


# --- wire contract (pure, unit-tested) ------------------------------------


def thinking() -> dict:
    return {"type": "thinking"}


def working(label: str) -> dict:
    return {"type": "working", "label": label}


def tone(value: str) -> dict:
    return {"type": "tone", "tone": value.upper()}


def body(text: str) -> dict:
    return {"type": "body", "text": text}


def detail(text: str) -> dict:
    return {"type": "detail", "text": text}


def done() -> dict:
    return {"type": "done"}


def error(message: str, retry_hint: str | None = None) -> dict:
    payload: dict = {"type": "error", "message": message}
    if retry_hint:
        payload["retryHint"] = retry_hint
    return payload


def encode_stream(chunks: Iterable[dict]) -> Iterator[bytes]:
    """Serialize chunks to newline-delimited JSON bytes (one per line)."""
    for chunk in chunks:
        yield (json.dumps(chunk, separators=(",", ":")) + "\n").encode("utf-8")


def echo_responder(prompt: str, history: list[dict]) -> Iterator[dict]:
    """A minimal real responder used when no agent runtime is wired.

    Streams a thinking indicator, a short body, and done — enough to
    prove the avatar's live state feed end-to-end before the full agent
    is attached. Replace via [serve]'s ``responder`` argument.
    """
    yield thinking()
    yield body(f"You said: {prompt}")
    yield done()


# --- transport ------------------------------------------------------------


@dataclass
class _Config:
    responder: Responder


def _make_handler(config: _Config) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # silence default stderr logging
            pass

        def do_POST(self):  # noqa: N802 (http.server API)
            if self.path.rstrip("/") != CHAT_PATH:
                self._send_error(404, "unknown path")
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._send_error(400, "invalid JSON body")
                return

            prompt = str(payload.get("prompt", ""))
            history = list(payload.get("history", []) or [])

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for line in encode_stream(config.responder(prompt, history)):
                    self._write_chunk(line)
                self._write_chunk(b"")  # terminating chunk
            except BrokenPipeError:
                # client cancelled (the user's Stop) — expected, not an error
                pass

        def _write_chunk(self, data: bytes) -> None:
            self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
            if data:
                self.wfile.write(data)
            self.wfile.write(b"\r\n")
            self.wfile.flush()

        def _send_error(self, code: int, message: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            self.wfile.write(next(encode_stream([error(message)])))

    return Handler


def serve(
    responder: Responder = echo_responder,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Start the local chat server in a background thread and return it.

    Bind to loopback only — this endpoint is for the on-device app and
    the Termux runtime, never the network.
    """
    server = ThreadingHTTPServer((host, port), _make_handler(_Config(responder)))
    thread = threading.Thread(target=server.serve_forever, name="jarvis-local-http", daemon=True)
    thread.start()
    return server
