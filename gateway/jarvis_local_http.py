"""Local JSONL chat endpoint for the muse Android cockpit.

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

import ipaddress
import json
import threading
import warnings
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Iterable, Iterator

CHAT_PATH = "/v1/jarvis/chat"


def _is_loopback_host(host: str) -> bool:
    """True if ``host`` is a loopback/localhost bind address."""

    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # Unknown hostname — treat as non-loopback (fail safe).
        return False


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


# --- extended wire contract: phases, tool calls, evidence/ledger refs ----
#
# These are *additive* chunk types. Older clients ignore unknown ``type``
# values (the Kotlin parser drops them), so emitting them never breaks a
# pre-update app. They give the mobile cockpit a phase rail, compact tool
# visibility, and one-tap evidence/ledger inspection.

# Named pipeline phases the avatar surfaces as a progress rail. Kept in
# sync with the Kotlin ``JarvisPhase`` enum.
PHASES = (
    "RECEIVING",
    "THINKING",
    "ROUTING",
    "TOOL",
    "CODING",
    "RESEARCH",
    "VERIFICATION",
    "FINAL",
)

# Tool-call lifecycle statuses (1:1 with Kotlin ``ToolCall.status``).
TOOL_STATUSES = ("START", "OK", "FAIL")


def phase(name: str) -> dict:
    """A named pipeline phase (e.g. ``ROUTING``, ``VERIFICATION``).

    Unknown names pass through upper-cased so a future phase still renders
    as a labelled chip rather than crashing the client.
    """
    return {"type": "phase", "phase": (name or "").upper()}


def tool_call(
    call_id: str,
    name: str,
    summary: str,
    status: str = "START",
    detail: str | None = None,
) -> dict:
    """One tool invocation surfaced to the cockpit.

    ``summary``/``detail`` are **secret-scrubbed here** via
    ``secrets_policy.redact`` so a tool arg/result that captured a token
    can never reach the wire, even if a caller forgets to pre-redact.
    """
    payload: dict = {
        "type": "tool_call",
        "id": call_id,
        "name": name,
        "summary": _scrub(summary),
        "status": status.upper() if status else "START",
    }
    if detail:
        payload["detail"] = _scrub(detail)
    return payload


def body_delta(text: str) -> dict:
    """An incremental slice of the reply body (model streaming).

    Additive: clients that don't understand ``body_delta`` drop it and
    still receive the final accumulated ``body`` chunk, so streaming
    never breaks a pre-update app.
    """
    return {"type": "body_delta", "text": text}


def approval(
    approval_id: str,
    session_key: str,
    summary: str,
    *,
    tool: str | None = None,
    choices: tuple[str, ...] = ("once", "session", "always", "deny"),
) -> dict:
    """An owner-approval request blocking the current agent run.

    The client renders Approve/Deny controls and resolves via
    ``POST /v1/agent/approvals`` with ``{"session_key": ..., "choice": ...}``.
    ``summary`` is secret-scrubbed like tool summaries.
    """
    payload: dict = {
        "type": "approval",
        "id": approval_id,
        "sessionKey": session_key,
        "summary": _scrub(summary),
        "choices": list(choices),
    }
    if tool:
        payload["tool"] = tool
    return payload


def evidence_ref(audit_id: str, title: str) -> dict:
    """A reference to an evidence/proof record the app resolves on tap.

    Reference-only: carries the id the app looks up via ``auditProof`` —
    no evidence body rides the chat stream.
    """
    return {"type": "evidence", "auditId": audit_id, "title": title}


def ledger_ref(ledger_id: str, title: str) -> dict:
    """A reference to a decision-ledger entry the app resolves on tap."""
    return {"type": "ledger", "ledgerId": ledger_id, "title": title}


def _scrub(text: str) -> str:
    """Best-effort secret redaction for anything tool-derived.

    Reuses the canonical ``hermes_cli.secrets_policy.redact`` so the chat
    stream shares the same secret policy as the rest of Hermes. Degrades
    to the original text only if that module is unavailable (never raises).
    """
    if not text:
        return text
    try:
        from hermes_cli.secrets_policy import redact

        return redact(text)
    except Exception:  # pragma: no cover - redaction is best-effort
        return text


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

        def log_message(self, format, *args):  # noqa: A002 - match base signature
            pass  # silence default stderr logging

        def do_POST(self):  # noqa: N802 (http.server API)
            # Streaming responses don't benefit from keep-alive here; close
            # after each response so clients never block waiting for more.
            self.close_connection = True
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
            body = next(encode_stream([error(message)]))
            # Frame the error response fully (Content-Length) and close the
            # connection, so a keep-alive client never blocks reading the body.
            self.close_connection = True
            self.send_response(code)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

    return Handler


def serve(
    responder: Responder = echo_responder,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    allow_external: bool = False,
) -> ThreadingHTTPServer:
    """Start the local chat server in a background thread and return it.

    Bind to loopback only — this endpoint is for the on-device app and
    the Termux runtime, never the network. Binding to a non-loopback
    address (exposing JARVIS to the network) is refused unless the caller
    explicitly passes ``allow_external=True``, and even then a warning is
    emitted. This is a safety gate, not a feature: a local agent endpoint
    on a routable interface is a credential/attack-surface risk.
    """
    if not _is_loopback_host(host) and not allow_external:
        raise ValueError(
            f"refusing to bind JARVIS local HTTP to non-loopback host {host!r}; "
            "pass allow_external=True only if you understand the exposure risk"
        )
    if not _is_loopback_host(host):
        warnings.warn(
            f"JARVIS local HTTP is binding to non-loopback host {host!r} — "
            "this exposes the agent endpoint to the network",
            stacklevel=2,
        )
    server = ThreadingHTTPServer((host, port), _make_handler(_Config(responder)))
    thread = threading.Thread(
        target=server.serve_forever, name="jarvis-local-http", daemon=True
    )
    thread.start()
    return server
