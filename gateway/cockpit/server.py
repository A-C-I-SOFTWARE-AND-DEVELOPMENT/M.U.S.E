"""Loopback HTTP server for the Hermes cockpit API.

A tiny stdlib router (no web framework — Termux-safe) that:

* binds loopback-only by default (reusing ``jarvis_local_http``'s gate),
* requires a bearer token on every route except ``GET /v1/health``,
* dispatches JSON CRUD routes to :mod:`gateway.cockpit.handlers`, and
* streams the **real** JARVIS agent for ``POST /v1/jarvis/chat`` via
  :func:`gateway.cockpit.agent.jarvis_responder`.

Start it with :func:`serve` (background thread) or from the CLI
``hermes cockpit serve``.
"""

from __future__ import annotations

import json
import re
import threading
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import parse_qs, urlsplit

from gateway.cockpit import auth as cockpit_auth
from gateway.cockpit import handlers as h
from gateway.cockpit.agent import jarvis_responder
from gateway.jarvis_local_http import (
    CHAT_PATH,
    _is_loopback_host,
    encode_stream,
    error,
)

# Route table: (method, compiled-pattern, handler, requires_auth).
# Patterns use ``{name}`` placeholders captured into ``path_params``.
_HandlerFn = Callable[[h.Request], h.JsonResponse]


def _compile(path: str) -> re.Pattern[str]:
    pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path.rstrip("/"))
    return re.compile(f"^{pattern}$")


_ROUTES: list[tuple[str, re.Pattern[str], _HandlerFn, bool]] = [
    ("GET", _compile("/v1/health"), h.health, False),
    ("GET", _compile("/v1/cockpit/runtime/status"), h.runtime_status, True),
    ("GET", _compile("/v1/cockpit/runtime/workers"), h.runtime_workers, True),
    ("GET", _compile("/v1/cockpit/diagnostics"), h.diagnostics, True),
    ("GET", _compile("/v1/cockpit/models"), h.models, True),
    ("GET", _compile("/v1/cockpit/model-routes"), h.model_routes, True),
    ("POST", _compile("/v1/cockpit/model-routes/override"), h.model_route_override, True),
    ("GET", _compile("/v1/cockpit/memory"), h.memory_list, True),
    ("POST", _compile("/v1/cockpit/memory"), h.memory_create, True),
    ("DELETE", _compile("/v1/cockpit/memory/{id}"), h.memory_delete, True),
    ("GET", _compile("/v1/cockpit/events"), h.audit_events, True),
    ("GET", _compile("/v1/cockpit/audit"), h.audit_list, True),
    ("GET", _compile("/v1/cockpit/audit/{id}/proof"), h.audit_proof, True),
    ("GET", _compile("/v1/cockpit/jobs"), h.jobs_list, True),
    ("POST", _compile("/v1/cockpit/jobs"), h.jobs_dispatch, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/run"), h.job_run, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/cancel"), h.job_cancel, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}"), h.job_get, True),
    ("GET", _compile("/v1/cockpit/approvals"), h.approvals_list, True),
    ("POST", _compile("/v1/cockpit/approvals/{id}"), h.approvals_decide, True),
    ("GET", _compile("/v1/cockpit/proposals"), h.proposals_list, True),
    ("GET", _compile("/v1/cockpit/skills"), h.skills_list, True),
    ("GET", _compile("/v1/cockpit/navigation"), h.navigation_list, True),
    ("GET", _compile("/v1/cockpit/sessions"), h.sessions_list, True),
    ("GET", _compile("/v1/cockpit/avatar/persona"), h.avatar_persona_get, True),
    ("POST", _compile("/v1/cockpit/avatar/persona"), h.avatar_persona_set, True),
    ("GET", _compile("/v1/cockpit/avatar/room"), h.room_list, True),
    ("POST", _compile("/v1/cockpit/avatar/room"), h.room_generate, True),
    ("DELETE", _compile("/v1/cockpit/avatar/room/{id}"), h.room_delete, True),
    ("POST", _compile("/v1/cockpit/avatar/room/{id}/place"), h.room_place, True),
]


def _match(method: str, path: str):
    clean = path.rstrip("/") or "/"
    for route_method, pattern, handler, requires_auth in _ROUTES:
        if route_method != method:
            continue
        m = pattern.match(clean)
        if m:
            return handler, requires_auth, m.groupdict()
    return None


def _make_handler(token: Optional[str], responder):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # noqa: A002 - match base signature
            pass

        # -- auth -------------------------------------------------------
        def _authed(self) -> bool:
            presented = cockpit_auth.extract_bearer(self.headers.get("Authorization"))
            return cockpit_auth.token_matches(presented, token)

        # -- JSON helpers ----------------------------------------------
        def _send_json(self, status: int, payload: dict) -> None:
            raw = json.dumps(payload, default=str).encode("utf-8")
            self.close_connection = True
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                data = json.loads(raw)
                return data if isinstance(data, dict) else {"_": data}
            except json.JSONDecodeError:
                return {}

        def _query(self) -> dict[str, str]:
            q = parse_qs(urlsplit(self.path).query)
            return {k: v[0] for k, v in q.items() if v}

        # -- dispatch ---------------------------------------------------
        def _dispatch(self, method: str) -> None:
            self.close_connection = True
            path = urlsplit(self.path).path

            # Streaming chat endpoint (real agent) — POST only.
            if method == "POST" and path.rstrip("/") == CHAT_PATH:
                if not self._authed():
                    self._send_json(401, {"error": "missing or invalid bearer token"})
                    return
                self._stream_chat()
                return

            matched = _match(method, path)
            if matched is None:
                self._send_json(404, {"error": f"unknown route: {method} {path}"})
                return
            handler, requires_auth, path_params = matched
            if requires_auth and not self._authed():
                self._send_json(401, {"error": "missing or invalid bearer token"})
                return
            req = h.Request(
                method=method,
                path=path,
                query=self._query(),
                body=self._read_body() if method in ("POST", "PUT", "PATCH") else {},
                path_params=path_params,
            )
            try:
                resp = handler(req)
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json(500, {"error": str(exc)})
                return
            self._send_json(resp.status, resp.payload)

        def _stream_chat(self) -> None:
            payload = self._read_body()
            prompt = str(payload.get("prompt", ""))
            history = list(payload.get("history", []) or [])
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                stream = encode_stream(responder(prompt, history))
                for line in stream:
                    self._write_chunk(line)
                self._write_chunk(b"")
            except BrokenPipeError:
                pass
            except Exception as exc:  # pragma: no cover - defensive
                try:
                    self._write_chunk(next(encode_stream([error(str(exc))])))
                    self._write_chunk(b"")
                except Exception:
                    pass

        def _write_chunk(self, data: bytes) -> None:
            self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
            if data:
                self.wfile.write(data)
            self.wfile.write(b"\r\n")
            self.wfile.flush()

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def do_PUT(self):  # noqa: N802
            self._dispatch("PUT")

        def do_DELETE(self):  # noqa: N802
            self._dispatch("DELETE")

    return Handler


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    token: Optional[str] = None,
    allow_external: bool = False,
    responder=None,
) -> ThreadingHTTPServer:
    """Start the cockpit API server in a background thread.

    Loopback-only unless ``allow_external=True`` (which also warns). The
    bearer ``token`` defaults to the persisted cockpit token (created on
    first use). ``responder`` overrides the chat responder (tests).
    """
    if not _is_loopback_host(host) and not allow_external:
        raise ValueError(
            f"refusing to bind cockpit API to non-loopback host {host!r}; "
            "pass allow_external=True only if you understand the exposure risk"
        )
    if not _is_loopback_host(host):
        warnings.warn(
            f"cockpit API binding to non-loopback host {host!r} — exposes the "
            "agent endpoint to the network",
            stacklevel=2,
        )
    if token is None:
        token = cockpit_auth.load_or_create_token()
    # Second guard for agentic execute lanes: only loopback cockpits may run
    # them (the owner-phrase gate is the first guard, enforced per-request).
    h.configure_runtime(allow_remote_execute=bool(allow_external))
    if responder is not None:
        chat_responder = responder
    else:
        # Default chat path: drive the real JARVIS turn AND generate reply prose
        # from the running local model (Ollama). If no model is reachable, the
        # responder degrades to the turn summary rather than failing.
        from gateway.cockpit.generate import default_prose_generator

        def chat_responder(prompt, history):
            return jarvis_responder(prompt, history, generate=default_prose_generator)

    server = ThreadingHTTPServer((host, port), _make_handler(token, chat_responder))
    thread = threading.Thread(
        target=server.serve_forever, name="hermes-cockpit-http", daemon=True
    )
    thread.start()
    return server


__all__ = ["serve"]
