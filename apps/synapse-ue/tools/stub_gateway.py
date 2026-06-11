#!/usr/bin/env python3
"""Prompt 0 fallback stub gateway for the SYNAPSE UE client.

A stdlib-only HTTP server that mimics the routes the Phase 0 handshake +
the SynapseObservatory module need, with response shapes copied from the
real gateway (gateway/cockpit/handlers.py + handlers_observatory.py,
pinned by docs/contracts/cockpit-wire-contract.md and
docs/synapse/design/10-observatory-spec.md):

  GET /health, GET /v1/health        -> 200 liveness JSON (open; the
                                        contract route is /v1/health, the
                                        bare /health alias is a convenience)
  GET /v1/cockpit/capabilities       -> bearer auth required (401 with the
                                        gateway's exact error body when the
                                        Authorization header is missing or
                                        wrong); 200 minimal capabilities
                                        document matching the real shape
  GET /v1/observatory/snapshot       -> bearer; canned spec-shaped map boot
                                        (spec §3.1: graph clusters +
                                        stations + ladder + metrics rollup)
  GET /v1/observatory/metrics        -> bearer; ?window= 15m|1h|24h|7d
                                        (400 bad_request otherwise), canned
                                        rollup matching the collector shape
  GET /v1/observatory/layout         -> bearer; ?cluster= required (400),
                                        404 unknown_cluster for stale ids,
                                        canned member expansion (spec §3.4)
  GET /v1/observatory/recommendations-> bearer; canned verdict cards (one
                                        validated, one honestly collecting)
  GET /v1/observatory/stream         -> bearer; SSE scripted loop of the
                                        five spec §3.2 event types
                                        (job.stage, gate.verdict,
                                        node.activate, route.decision,
                                        resync) plus a heartbeat, ~1 s
                                        apart, for offline PIE testing

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
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_VERSION = "1.0.0"
GATEWAY_VERSION = "stub-0.1.0"
SERVICE_NAME = "synapse-stub-gateway"
DEFAULT_TOKEN = "synapse-dev-token"  # pragma: allowlist secret — local test stub only
STREAM_STEP_SECONDS = 1.0

TOKEN = os.environ.get("STUB_TOKEN") or DEFAULT_TOKEN

# -- canned Observatory data (spec-shaped, mirrors handlers_observatory.py) --

OBSERVATORY_V = 1
GRAPH_VERSION = "g-20260610-180000"
METRICS_WINDOWS = ("15m", "1h", "24h", "7d")
HEAT_WEIGHTS = {"latency": 0.30, "queue": 0.20, "fail": 0.25, "retry": 0.15, "cost": 0.10}
MIN_HEAT_N = 5

# Cluster 1 carries heat + pos; cluster 2 deliberately has heat: null (below
# the confidence gate) so the UE optional-field handling is exercised.
CLUSTERS = [
    {
        "id": "c-1f2e3d4c",
        "label": "gateway/cockpit",
        "type_mix": {"code": 0.8, "docs": 0.2},
        "members": 412,
        "pos": [12.4, -3.1, 88.0],
        "radius": 4.2,
        "heat": 0.31,
    },
    {
        "id": "c-9a8b7c6d",
        "label": "docs/synapse",
        "type_mix": {"docs": 1.0},
        "members": 96,
        "pos": [-40.2, 7.7, 12.5],
        "radius": 2.1,
        "heat": None,
    },
]

# Node 2 deliberately has pos: null and heat: null (layout not solved for it)
# so the UE bHas* flags are exercised end to end.
LAYOUT_NODES = {
    "c-1f2e3d4c": [
        {
            "id": "n-0001",
            "type": "code",
            "label": "handlers.py",
            "pos": [0.4, 1.1, -0.2],
            "degree": 14,
            "heat": 0.05,
            "source_ref": "gateway/cockpit/handlers.py",
        },
        {
            "id": "n-0002",
            "type": "docs",
            "label": "10-observatory-spec.md",
            "pos": None,
            "degree": 3,
            "heat": None,
            "source_ref": "docs/synapse/design/10-observatory-spec.md",
        },
    ],
    "c-9a8b7c6d": [
        {
            "id": "n-0101",
            "type": "docs",
            "label": "11-technical-design.md",
            "pos": [0.0, 0.6, 0.3],
            "degree": 7,
            "heat": None,
            "source_ref": "docs/synapse/design/11-technical-design.md",
        },
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metrics_rollup(window: str = "1h") -> dict:
    """Canned mirror of ObservatoryCollector.rollup() (spec §3.3 shape)."""
    now = _now_iso()
    return {
        "window": window,
        "from": now,
        "to": now,
        "stages": [
            {
                "stage": "worker",
                "task_class": "code",
                "count": 41,
                "p50_ms": 92000,
                "p95_ms": 311000,
                "queue_wait_p95_ms": 14000,
                "retries": 6,
            }
        ],
        "gates": [
            {
                "gate": "test",
                "task_class": "code",
                "passes": 35,
                "fails": 6,
                "overrides": 1,
                "fail_rate": 0.1429,
            }
        ],
        "models": [
            {
                "tier": "local",
                "model": "qwen2.5-3b-instruct-q4",
                "calls": 412,
                "p95_latency_ms": 2390,
                "tokens_in": 181000,
                "tokens_out": 52000,
                "est_cost_usd": 0.0,
            }
        ],
        "cost_per_task_class": [{"task_class": "code", "usd": 0.41, "n": 41}],
        "heat": [
            {
                "key": "stage:worker:code",
                "score": 0.83,
                "n": 41,
                "evidence_ref": "/v1/cockpit/ledger?category=STAGE&kind=worker",
            },
            {
                # Below the confidence gate: score honestly null, real n.
                "key": "gate:release:code",
                "score": None,
                "n": 2,
                "evidence_ref": "/v1/cockpit/ledger?category=GATE&kind=release",
            },
        ],
        "heat_weights": dict(HEAT_WEIGHTS),
        "min_n": MIN_HEAT_N,
        "collector": {"events_in_window": 53, "events_recorded": 53, "io_errors": 0},
    }


def _observatory_snapshot() -> dict:
    """Canned mirror of observatory_snapshot() (spec §3.1 shape)."""
    return {
        "v": OBSERVATORY_V,
        "generated_at": _now_iso(),
        "graph": {
            "graph_version": GRAPH_VERSION,
            "node_count": 28600,
            "edge_count": 51600,
            "clusters": [dict(c) for c in CLUSTERS],
            "cluster_edges": [
                {"a": "c-1f2e3d4c", "b": "c-9a8b7c6d", "weight": 96, "heat": None}
            ],
            "clusters_total": 2,
            "clusters_truncated": False,
            "layout_status": "computed",
            "layout_algo": "stub-canned-v1",
        },
        "stations": {
            "nodes": ["job", "navigator", "worker", "gate", "ledger"],
            "active_jobs": [
                {
                    "job_id": "jb-91ac",
                    "task_class": "code",
                    "stage": "worker",
                    "stage_entered_at": _now_iso(),
                    "queue_pos": None,
                }
            ],
            "queue_depth": 3,
        },
        "ladder": {
            "tiers": [
                {
                    "tier": "local",
                    "model": "qwen2.5-3b-instruct-q4",
                    "share_1h": 0.62,
                    "n": 412,
                    "p50_latency_ms": 840,
                    "p95_latency_ms": 2390,
                },
                {
                    # No decisions on this tier in window: nullable fields null.
                    "tier": "paired",
                    "model": None,
                    "share_1h": None,
                    "n": 0,
                    "p50_latency_ms": None,
                    "p95_latency_ms": None,
                },
            ]
        },
        "metrics_rollup": {"v": OBSERVATORY_V, **_metrics_rollup("1h")},
    }


def _observatory_layout(cluster: str, limit: int) -> dict:
    """Canned mirror of observatory_layout() (spec §3.4 shape)."""
    nodes = LAYOUT_NODES[cluster]
    truncated = len(nodes) > limit
    kept = nodes[:limit]
    kept_ids = {n["id"] for n in kept}
    edges = [
        {"a": "n-0001", "b": "n-0002", "weight": 3}
        for _ in range(1)
        if {"n-0001", "n-0002"} <= kept_ids
    ]
    return {
        "v": OBSERVATORY_V,
        "cluster": cluster,
        "graph_version": GRAPH_VERSION,
        "layout_status": "computed",
        "layout_algo": "stub-canned-v1",
        "truncated": truncated,
        "nodes": [dict(n) for n in kept],
        "edges": edges,
    }


def _observatory_recommendations() -> dict:
    """Canned verdict cards (spec §6): one validated, one honestly collecting."""
    now = _now_iso()
    return {
        "v": OBSERVATORY_V,
        "generated_at": now,
        "cards": [
            {
                "id": "rec-7f3a",
                "title": "Route short code tasks to qwen-coder-local",
                "state": "validated",
                "delta": "median latency -38%",
                "validation": {
                    "method": "replay",
                    "n_baseline": 212,
                    "n_candidate": 212,
                    "median_delta_pct": -38.0,
                    "ci95": [-44.0, -31.0],
                    "metric": "latency_ms",
                },
                "evidence_refs": [
                    "/v1/cockpit/ledger?category=STAGE&kind=worker",
                ],
                "created_at": now,
            },
            {
                # Spec §6 hard rule: below threshold there are NO numbers —
                # nullable fields are null, state says collecting.
                "id": "rec-2b9c",
                "title": "Raise review-gate strictness on release class",
                "state": "collecting",
                "delta": None,
                "validation": {
                    "method": "replay",
                    "n_baseline": 7,
                    "n_candidate": 0,
                    "median_delta_pct": None,
                    "ci95": None,
                    "metric": "gate_pass_rate",
                },
                "evidence_refs": [],
                "created_at": now,
            },
        ],
    }


def _stream_script(seq: int) -> tuple[str, dict]:
    """The scripted SSE loop: the five spec §3.2 event types + a heartbeat.

    Six steps per cycle; every fourth cycle the heartbeat slot becomes a
    `resync` so the client's snapshot-refetch path is exercised offline.
    """
    ts = _now_iso()
    step = seq % 6
    cycle = seq // 6
    if step == 0:
        return "job.stage", {
            "job_id": f"jb-{1000 + cycle}",
            "task_class": "code",
            "stage": "queued",
            "queue_depth": 3,
            "stage_latency_ms": None,
            "ts": ts,
        }
    if step == 1:
        return "job.stage", {
            "job_id": f"jb-{1000 + cycle}",
            "task_class": "code",
            "stage": "worker",
            "queue_depth": 2,
            "stage_latency_ms": 1840,
            "ts": ts,
        }
    if step == 2:
        return "node.activate", {
            "cluster_id": "c-1f2e3d4c",
            "node_id": "n-0001" if cycle % 2 == 0 else None,
            "kind": "query",
            "weight": 1.0,
            "ts": ts,
        }
    if step == 3:
        return "route.decision", {
            "turn_id": f"turn-{2000 + cycle}",
            "tier": "local",
            "model": "qwen2.5-3b-instruct-q4",
            "reason": "short prompt, local capacity available",
            "latency_ms": 840,
            "tokens_in": 412,
            "tokens_out": 96,
            "ts": ts,
        }
    if step == 4:
        return "gate.verdict", {
            "job_id": f"jb-{1000 + cycle}",
            "gate": "test",
            "verdict": "pass" if cycle % 3 else "fail",
            "attempt": 1 if cycle % 3 else 2,
            "detail_ref": f"/v1/cockpit/jobs/jb-{1000 + cycle}/validation",
            "ts": ts,
        }
    if cycle % 4 == 3:
        return "resync", {"reason": "graph_rebuilt", "ts": ts}
    return "heartbeat", {"seq": seq, "time": ts}


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
        raw_path, _, raw_query = self.path.partition("?")
        path = raw_path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(raw_query)

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

        if path == "/v1/observatory/snapshot":
            if not self._authed():
                self._reject_unauthorized()
                return
            self._send_json(200, _observatory_snapshot())
            return

        if path == "/v1/observatory/metrics":
            if not self._authed():
                self._reject_unauthorized()
                return
            window = query.get("window", ["1h"])[0]
            if window not in METRICS_WINDOWS:
                self._send_json(
                    400,
                    {
                        "error": "bad_request",
                        "detail": (
                            f"window: must be one of "
                            f"{', '.join(sorted(METRICS_WINDOWS))} (got {window!r})"
                        ),
                    },
                )
                return
            self._send_json(200, {"v": OBSERVATORY_V, **_metrics_rollup(window)})
            return

        if path == "/v1/observatory/layout":
            if not self._authed():
                self._reject_unauthorized()
                return
            cluster = query.get("cluster", [""])[0].strip()
            if not cluster:
                self._send_json(
                    400, {"error": "bad_request", "detail": "cluster: required"}
                )
                return
            raw_limit = query.get("limit", ["500"])[0]
            try:
                limit = max(1, min(int(raw_limit), 2000))
            except ValueError:
                self._send_json(
                    400,
                    {
                        "error": "bad_request",
                        "detail": f"limit: must be an integer (got {raw_limit!r})",
                    },
                )
                return
            if cluster not in LAYOUT_NODES:
                # Stale id after a graph rebuild — the client refetches the
                # snapshot (graph_version mismatch is the tell, spec §3.4).
                self._send_json(404, {"error": "unknown_cluster"})
                return
            self._send_json(200, _observatory_layout(cluster, limit))
            return

        if path == "/v1/observatory/recommendations":
            if not self._authed():
                self._reject_unauthorized()
                return
            self._send_json(200, _observatory_recommendations())
            return

        if path == "/v1/observatory/stream":
            if not self._authed():
                self._reject_unauthorized()
                return
            self._stream_observatory_events()
            return

        self._send_json(404, {"error": f"unknown route: {path}"})

    def _stream_observatory_events(self) -> None:
        """Scripted SSE loop of the five spec §3.2 event types (+ heartbeat)
        so the owner can PIE-test the Observatory delegates offline."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            # `retry:` hint, per the SSE framing the UE client tolerates.
            self.wfile.write(b"retry: 5000\n\n")
            self.wfile.flush()
            seq = 0
            while True:
                event, payload = _stream_script(seq)
                seq += 1
                frame = f"event: {event}\nid: {seq}\ndata: {json.dumps(payload)}\n\n"
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
                time.sleep(STREAM_STEP_SECONDS)
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
    print(
        "[stub-gateway] routes: GET /health | /v1/health | /v1/cockpit/capabilities | "
        "/v1/observatory/{snapshot,metrics,layout,recommendations,stream}"
    )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[stub-gateway] stopped")


if __name__ == "__main__":
    main()
