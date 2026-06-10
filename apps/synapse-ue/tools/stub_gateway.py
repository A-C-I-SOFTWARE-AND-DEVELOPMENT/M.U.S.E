#!/usr/bin/env python3
"""Prompt 0 fallback stub gateway for the SYNAPSE UE client.

A stdlib-only HTTP server that mimics the three routes the Phase 0
handshake + SSE consumer need, with response shapes copied from the real
gateway (gateway/cockpit/handlers.py, pinned by
docs/contracts/cockpit-wire-contract.md):

  GET /health, GET /v1/health        -> 200 liveness JSON (open; the
                                        contract route is /v1/health, the
                                        bare /health alias is a convenience)
  GET /v1/cockpit/capabilities       -> bearer auth required (401 with the
                                        gateway's exact error body when the
                                        Authorization header is missing or
                                        wrong); 200 minimal capabilities
                                        document matching the real shape
  GET /v1/observatory/stream         -> bearer auth required; SSE heartbeat
                                        (`event: heartbeat`) every 2 seconds
                                        for client testing

Token: read from the STUB_TOKEN environment variable. If unset, a default
dev token is used and printed at startup (this is a local test stub — the
real gateway issues per-device tokens via the pairing routes).

Usage (set STUB_TOKEN in the environment first):
  python tools/stub_gateway.py [--port 8787]

Pair the UE client by writing the same token to
<Project>/Saved/muse_token.txt (see MuseGatewaySettings.h).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_VERSION = "1.0.0"
GATEWAY_VERSION = "stub-0.1.0"
SERVICE_NAME = "synapse-stub-gateway"
DEFAULT_TOKEN = "synapse-dev-token"  # pragma: allowlist secret — local test stub only
HEARTBEAT_SECONDS = 2.0

TOKEN = os.environ.get("STUB_TOKEN") or DEFAULT_TOKEN


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Handler(BaseHTTPRequestHandler):
    server_version = SERVICE_NAME

    # -- helpers ----------------------------------------------------------

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {TOKEN}"

    def _reject_unauthorized(self) -> None:
        # Exact 401 body shape of the real gateway (server.py).
        self._send_json(401, {"error": "missing or invalid bearer token"})

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if path in ("/health", "/v1/health"):
            # Mirror of gateway.cockpit.handlers.health (contract §2).
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": SERVICE_NAME,
                    "api_version": API_VERSION,
                    "gateway_version": GATEWAY_VERSION,
                    "time": _now_iso(),
                },
            )
            return

        if path == "/v1/cockpit/capabilities":
            if not self._authed():
                self._reject_unauthorized()
                return
            # Minimal mirror of gateway.cockpit.handlers.capabilities —
            # same field names, stub values (no subsystems importable here).
            self._send_json(
                200,
                {
                    "api_version": API_VERSION,
                    "gateway_version": GATEWAY_VERSION,
                    "subsystems": {
                        "memory": False,
                        "jobs": False,
                        "orchestrator": False,
                        "coding": False,
                        "evidence": False,
                        "ledger": False,
                        "models": False,
                    },
                    "available_workers": [],
                    "detected_clis": [],
                    "execute_allowed": False,
                    "owner_gate_required": True,
                    "generated_at": _now_iso(),
                },
            )
            return

        if path == "/v1/observatory/stream":
            if not self._authed():
                self._reject_unauthorized()
                return
            self._stream_heartbeats()
            return

        self._send_json(404, {"error": f"unknown route: {path}"})

    def _stream_heartbeats(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            # `retry:` hint, per the SSE framing the UE client tolerates.
            self.wfile.write(b"retry: 1000\n\n")
            self.wfile.flush()
            seq = 0
            while True:
                seq += 1
                data = json.dumps({"seq": seq, "time": _now_iso()})
                frame = f"event: heartbeat\nid: {seq}\ndata: {data}\n\n"
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
                time.sleep(HEARTBEAT_SECONDS)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Client went away — normal for a test stub.

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — signature matches BaseHTTPRequestHandler
        # Never echo headers (the bearer token) into logs.
        print(f"[stub-gateway] {self.address_string()} {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    token_source = "STUB_TOKEN env" if os.environ.get("STUB_TOKEN") else f"default ({DEFAULT_TOKEN!r})"
    print(f"[stub-gateway] serving on http://{args.host}:{args.port}  token: {token_source}")
    print("[stub-gateway] routes: GET /health | /v1/health | /v1/cockpit/capabilities | /v1/observatory/stream")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[stub-gateway] stopped")


if __name__ == "__main__":
    main()
