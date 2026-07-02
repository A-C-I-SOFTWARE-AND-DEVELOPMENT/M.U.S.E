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

import ipaddress
import json
import os
import re
import threading
import time
import warnings
from collections.abc import Iterable as _Iterable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlsplit

from gateway.cockpit import auth as cockpit_auth
from gateway.cockpit import event_log
from gateway.cockpit import handlers as h
from gateway.cockpit import handlers_game as h_game
from gateway.cockpit import handlers_observatory_recs as h_recs
from gateway.cockpit.agent import jarvis_responder
from gateway.jarvis_local_http import (
    CHAT_PATH,
    _is_loopback_host,
    encode_stream,
    error,
)

# Full-agent streaming chat (POST) — served only when the cockpit runs with
# ``--agent full`` (or HERMES_COCKPIT_AGENT=full); otherwise the route answers
# 409 with a hint so clients fall back to /v1/jarvis/chat cleanly.
AGENT_CHAT_PATH = "/v1/agent/chat"

def _nexus_dist_root() -> Optional[Path]:
    """Resolve the built NEXUS PWA directory (``apps/nexus/dist``) so the cockpit
    can serve it *same-origin* at ``/nexus/`` — letting a phone running MUSE in
    Termux reach the whole app over ``http://127.0.0.1:8765/nexus/`` with no
    mixed-content barrier. Override with ``NEXUS_DIST_DIR``. Returns ``None`` when
    no build is present (the mount then simply 404s — nothing else changes)."""
    override = os.environ.get("NEXUS_DIST_DIR")
    if override:
        # An explicit override is authoritative — no fallback. Either it holds a
        # build or the mount is off.
        p = Path(override)
        try:
            return p.resolve() if (p / "index.html").is_file() else None
        except OSError:
            return None
    # Default: apps/nexus/dist relative to the repo root (parents[2]).
    default = Path(__file__).resolve().parents[2] / "apps" / "nexus" / "dist"
    try:
        return default.resolve() if (default / "index.html").is_file() else None
    except OSError:
        return None


# Browser Origins allowed to call the cockpit API cross-origin, by DEFAULT —
# the first-party muse cockpit plus the muse desktop app's webview. Defaulting
# these on means a user can run ``muse cockpit serve`` and reach their gateway
# from the public cockpit — or install the desktop app and have it connect —
# with no extra flags. It is bounded: every sensitive route still requires the
# bearer token, and device pairing on an externally-reachable cockpit still
# requires the owner phrase. Any OTHER origin is rejected. Extend with
# --cors-origin / HERMES_COCKPIT_CORS_ORIGINS (CSV), or disable with
# HERMES_COCKPIT_CORS_ORIGINS=off.
_DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "https://musehq.io",
    "https://www.musehq.io",
    # The muse desktop shell (Tauri v2 webview). macOS/Linux serve the bundled
    # UI from the tauri: custom scheme; Windows (WebView2) uses
    # http(s)://tauri.localhost. Allowing them lets the desktop app talk to
    # the gateway directly (streaming SSE/NDJSON) instead of via its native
    # HTTP proxy fallback.
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    # The desktop UI's Vite dev server (`cargo tauri dev` / `npm run dev`).
    "http://localhost:1420",
    "http://127.0.0.1:1420",
)
_CORS_OFF_TOKENS = frozenset({"off", "none", "false", "0", "disable", "disabled"})


def _resolve_cors_origins(explicit: Optional[_Iterable[str]] = None) -> frozenset[str]:
    """Compute the cross-origin allowlist: first-party defaults + env + CLI.

    ``HERMES_COCKPIT_CORS_ORIGINS`` is a comma-separated extension of the
    defaults, or one of ``off``/``none``/``false``/``0``/``disable`` to clear
    the defaults entirely. Explicit ``--cors-origin`` values are always added.
    Origins are normalized (trailing slash stripped) for exact-match compare.
    """
    env = os.environ.get("HERMES_COCKPIT_CORS_ORIGINS")
    if env is not None and env.strip().lower() in _CORS_OFF_TOKENS:
        base: set[str] = set()  # explicit opt-out clears the first-party defaults
    else:
        base = {o.rstrip("/") for o in _DEFAULT_CORS_ORIGINS}
        for raw in (env or "").split(","):
            o = raw.strip().rstrip("/")
            if o and o.lower() not in _CORS_OFF_TOKENS:
                base.add(o)
    for raw in explicit or ():
        o = (raw or "").strip().rstrip("/")
        if o:
            base.add(o)
    return frozenset(base)


# Route table: (method, compiled-pattern, handler, requires_auth).
# Patterns use ``{name}`` placeholders captured into ``path_params``.
_HandlerFn = Callable[[h.Request], h.JsonResponse]


def _compile(path: str) -> re.Pattern[str]:
    pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path.rstrip("/"))
    return re.compile(f"^{pattern}$")


_ROUTES: list[tuple[str, re.Pattern[str], _HandlerFn, bool]] = [
    ("GET", _compile("/v1/health"), h.health, False),
    # Per-device pairing (Sprint 6) — gated like /v1/health (no shared-token
    # requirement) so a NEW device can obtain its own per-device token. The
    # short-lived pairing code + lockout are the protection; the existing
    # shared token still guards every other route below, unchanged.
    ("POST", _compile("/v1/cockpit/pair/start"), h.pair_start, False),
    ("POST", _compile("/v1/cockpit/pair/confirm"), h.pair_confirm, False),
    ("GET", _compile("/v1/cockpit/runtime/status"), h.runtime_status, True),
    ("GET", _compile("/v1/cockpit/runtime/workers"), h.runtime_workers, True),
    ("GET", _compile("/v1/cockpit/diagnostics"), h.diagnostics, True),
    ("GET", _compile("/v1/cockpit/axiom"), h.axiom_panel, True),
    ("GET", _compile("/v1/cockpit/models"), h.models, True),
    ("GET", _compile("/v1/cockpit/models/local"), h.models_local, True),
    ("POST", _compile("/v1/cockpit/models/local/smoke"), h.models_local_smoke, True),
    ("GET", _compile("/v1/cockpit/model-routes"), h.model_routes, True),
    ("POST", _compile("/v1/cockpit/model-routes/override"), h.model_route_override, True),
    # Owner-gated, opt-in (HERMES_COCKPIT_SECRET_IMPORT=1), loopback-only export of
    # the user's existing ~/.hermes/.env credential keys so NEXUS can import them.
    ("GET", _compile("/v1/cockpit/secrets/import"), h.secrets_import, True),
    ("GET", _compile("/v1/cockpit/memory"), h.memory_list, True),
    ("POST", _compile("/v1/cockpit/memory"), h.memory_create, True),
    ("DELETE", _compile("/v1/cockpit/memory/{id}"), h.memory_delete, True),
    # Evidence Engine. `verify` is registered before `{id}` so the literal
    # path wins over the id capture (first-match dispatch).
    ("GET", _compile("/v1/cockpit/evidence"), h.evidence_list, True),
    ("POST", _compile("/v1/cockpit/evidence/verify"), h.evidence_verify, True),
    # Literal `/evidence/search` MUST precede the `/evidence/{id}` captures
    # below (first-match dispatch — otherwise "search" is read as an id).
    ("GET", _compile("/v1/cockpit/evidence/search"), h.evidence_search, True),
    ("POST", _compile("/v1/cockpit/evidence/{id}/promote"), h.evidence_promote, True),
    ("GET", _compile("/v1/cockpit/evidence/{id}"), h.evidence_detail, True),
    ("DELETE", _compile("/v1/cockpit/evidence/{id}"), h.evidence_demote, True),
    # Memory Tree (MEM-2): proposed inbox, owner decisions, contradictions,
    # freshness review. More-specific paths; matcher is fully anchored.
    ("GET", _compile("/v1/cockpit/memory/tree"), h.memory_tree_search, True),
    ("GET", _compile("/v1/cockpit/memory/tree/proposed"), h.memory_tree_proposed, True),
    ("POST", _compile("/v1/cockpit/memory/tree/{id}/decision"), h.memory_tree_decision, True),
    ("GET", _compile("/v1/cockpit/memory/contradictions"), h.memory_contradictions, True),
    ("POST", _compile("/v1/cockpit/memory/contradictions/{id}/resolve"), h.memory_contradiction_resolve, True),
    ("GET", _compile("/v1/cockpit/memory/freshness"), h.memory_freshness, True),
    ("GET", _compile("/v1/cockpit/events"), h.audit_events, True),
    # Read-only summary of recent per-request observability traces
    # (latency percentiles, tool-failure / fallback rates, endpoint mix).
    ("GET", _compile("/v1/cockpit/trace"), h.trace_summary, True),
    ("GET", _compile("/v1/cockpit/audit"), h.audit_list, True),
    ("GET", _compile("/v1/cockpit/audit/{id}/proof"), h.audit_proof, True),
    ("GET", _compile("/v1/cockpit/capabilities"), h.capabilities, True),
    ("POST", _compile("/v1/cockpit/emergency-stop"), h.emergency_stop, True),
    ("GET", _compile("/v1/cockpit/ledger"), h.ledger_timeline, True),
    ("GET", _compile("/v1/cockpit/ledger/{job}/{index}"), h.ledger_event_detail, True),
    ("POST", _compile("/v1/cockpit/ledger/{job}/{index}/rollback"), h.ledger_rollback_request, True),
    ("GET", _compile("/v1/cockpit/jobs"), h.jobs_list, True),
    ("POST", _compile("/v1/cockpit/jobs"), h.jobs_dispatch, True),
    # Static sub-paths MUST precede "/jobs/{id}" (else "lanes" is captured as id).
    ("GET", _compile("/v1/cockpit/jobs/lanes"), h.job_lanes, True),
    ("POST", _compile("/v1/cockpit/orchestrate"), h.orchestrate_submit, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/run"), h.job_run, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/cancel"), h.job_cancel, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}/ledger"), h.job_ledger, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/pause"), h.job_pause, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/resume"), h.job_resume, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/rerun"), h.job_rerun, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/approve"), h.job_approve, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}/diff"), h.job_diff, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/validate"), h.job_validate, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/revalidate"), h.job_revalidate, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/override"), h.job_override, True),
    # Read-only job-workspace sub-resources (bearer-authed, no owner phrase —
    # they only read inside the already-approved local workspace). Literal
    # sub-paths, so they precede the bare "/jobs/{id}" capture below.
    ("GET", _compile("/v1/cockpit/jobs/{id}/files-changed"), h.job_files_changed, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}/validation"), h.job_validation, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}/tree"), h.job_tree, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}/file"), h.job_file, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}/publish/preview"), h.job_publish_preview, True),
    ("POST", _compile("/v1/cockpit/jobs/{id}/publish"), h.job_publish, True),
    ("GET", _compile("/v1/cockpit/jobs/{id}"), h.job_get, True),
    ("POST", _compile("/v1/cockpit/coding/audit"), h.coding_audit, True),
    ("POST", _compile("/v1/cockpit/coding/plan"), h.coding_plan, True),
    ("POST", _compile("/v1/cockpit/coding/execute"), h.coding_execute, True),
    ("POST", _compile("/v1/cockpit/research"), h.research_run, True),
    ("GET", _compile("/v1/cockpit/research"), h.research_list, True),
    ("POST", _compile("/v1/cockpit/research/{id}/promote"), h.research_promote, True),
    ("POST", _compile("/v1/cockpit/research/{id}/task"), h.research_create_task, True),
    ("GET", _compile("/v1/cockpit/research/{id}"), h.research_get, True),
    ("GET", _compile("/v1/cockpit/approvals"), h.approvals_list, True),
    ("POST", _compile("/v1/cockpit/approvals/{id}"), h.approvals_decide, True),
    # Full-agent chat companions (POST /v1/agent/chat streams; these resolve
    # its owner-approval requests and interrupt an in-flight run).
    ("POST", _compile("/v1/agent/approvals"), h.agent_approval_decide, True),
    ("POST", _compile("/v1/agent/stop"), h.agent_stop, True),
    ("GET", _compile("/v1/cockpit/autonomy"), h.autonomy_get, True),
    ("POST", _compile("/v1/cockpit/autonomy"), h.autonomy_set, True),
    ("GET", _compile("/v1/cockpit/autonomy/decisions"), h.autonomy_decisions, True),
    ("POST", _compile("/v1/cockpit/voice/intake"), h.voice_intake_create, True),
    # Server-side audio duplex. Literal sub-paths registered before the
    # "/voice/{id}/decide" capture so "transcribe"/"responses" are never read
    # as an intake id (first-match dispatch).
    ("POST", _compile("/v1/cockpit/voice/transcribe"), h.voice_transcribe, True),
    ("POST", _compile("/v1/cockpit/voice/responses"), h.voice_responses, True),
    ("POST", _compile("/v1/cockpit/voice/{id}/decide"), h.voice_intake_decide, True),
    ("GET", _compile("/v1/cockpit/proposals"), h.proposals_list, True),
    ("GET", _compile("/v1/cockpit/learning"), h.learning_list, True),
    ("GET", _compile("/v1/cockpit/learning/export"), h.learning_export, True),
    ("POST", _compile("/v1/cockpit/learning/{id}"), h.learning_decide, True),
    ("GET", _compile("/v1/cockpit/skills"), h.skills_list, True),
    ("GET", _compile("/v1/cockpit/templates"), h.templates_list, True),
    ("GET", _compile("/v1/cockpit/navigation"), h.navigation_list, True),
    ("GET", _compile("/v1/cockpit/graph/related"), h.graph_related, True),
    ("GET", _compile("/v1/cockpit/graph/query"), h.graph_query, True),
    ("POST", _compile("/v1/cockpit/graph/build"), h.graph_build, True),
    ("GET", _compile("/v1/cockpit/second-brain/status"), h.second_brain_status, True),
    ("GET", _compile("/v1/cockpit/second-brain/retrieve"), h.second_brain_retrieve, True),
    ("GET", _compile("/v1/cockpit/forge/leaderboard"), h.forge_leaderboard, True),
    ("GET", _compile("/v1/cockpit/federation/status"), h.federation_status, True),
    ("GET", _compile("/v1/cockpit/council/dispatch"), h.council_dispatch, True),
    ("GET", _compile("/v1/cockpit/sessions"), h.sessions_list, True),
    ("GET", _compile("/v1/cockpit/avatar/persona"), h.avatar_persona_get, True),
    ("POST", _compile("/v1/cockpit/avatar/persona"), h.avatar_persona_set, True),
    ("GET", _compile("/v1/cockpit/avatar/room"), h.room_list, True),
    ("POST", _compile("/v1/cockpit/avatar/room"), h.room_generate, True),
    ("DELETE", _compile("/v1/cockpit/avatar/room/{id}"), h.room_delete, True),
    ("POST", _compile("/v1/cockpit/avatar/room/{id}/place"), h.room_place, True),
    # Neural Observatory (SYNAPSE Phase 3) — strictly additive, read-only,
    # bearer-authed. Pure reads over the passive observatory_metrics collector
    # plus the GraphRAG cache; honest unavailable/insufficient-evidence shapes
    # when nothing has been recorded (docs/synapse/design/10-observatory-spec.md).
    ("GET", _compile("/v1/observatory/snapshot"), h.observatory_snapshot, True),
    ("GET", _compile("/v1/observatory/metrics"), h.observatory_metrics, True),
    ("GET", _compile("/v1/observatory/layout"), h.observatory_layout, True),
    # Recommendation engine (spec §6). Bearer-authed, NOT owner-gated:
    # staging only feeds the existing owner-phrase approvals queue
    # (POST /v1/cockpit/approvals/{id}), where Apply's owner gate lives.
    ("GET", _compile("/v1/observatory/recommendations"), h_recs.observatory_recommendations, True),
    ("POST", _compile("/v1/observatory/recommendations/{id}/stage"), h_recs.observatory_recommendation_stage, True),
    # SYNAPSE game substrate (master plan §4; additive per the §1 coupling
    # rule). Bearer-authed CRUD over local save/Foundry state — no owner
    # phrase: nothing here flips a real muse capability. Literal "/design"
    # and "/saves" precede the "{slot}" capture (first-match dispatch).
    ("GET", _compile("/v1/game/design"), h_game.game_design, True),
    ("GET", _compile("/v1/game/saves"), h_game.game_saves_list, True),
    ("GET", _compile("/v1/game/saves/{slot}"), h_game.game_save_get, True),
    ("POST", _compile("/v1/game/saves/{slot}"), h_game.game_save_write, True),
    ("DELETE", _compile("/v1/game/saves/{slot}"), h_game.game_save_delete, True),
    # The Foundry loop spine (master plan §4.7, docs/synapse/design/09-
    # foundry-spec.md): observe -> candidate -> recorded validation -> ship.
    # The gateway stores honest results only; it never simulates.
    ("POST", _compile("/v1/foundry/observe"), h_game.foundry_observe, True),
    ("GET", _compile("/v1/foundry/candidates"), h_game.foundry_candidates_list, True),
    ("POST", _compile("/v1/foundry/candidates"), h_game.foundry_candidate_create, True),
    ("POST", _compile("/v1/foundry/candidates/{id}/validation"), h_game.foundry_candidate_validation, True),
    ("POST", _compile("/v1/foundry/candidates/{id}/ship"), h_game.foundry_candidate_ship, True),
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


# --- Server-Sent Events (live streams) --------------------------------------
# SSE GETs cannot go through the buffered _ROUTES/_send_json path (which writes a
# single fixed-length body and closes). They are matched here and special-cased
# in _dispatch, exactly like the chat POST. The intervals are module globals so
# tests can shorten them.
_SSE_POLL_S = 1.0
_SSE_HEARTBEAT_S = 15.0
_SSE_MAX_DURATION_S = 600.0  # backstop; the client reconnects with backoff

_STREAM_ROUTES: list[tuple[re.Pattern[str], str]] = [
    (_compile("/v1/cockpit/jobs/stream"), "_stream_jobs"),
    (_compile("/v1/cockpit/events/stream"), "_stream_events"),
    (_compile("/v1/observatory/stream"), "_stream_observatory"),
    (_compile("/v1/observatory/actions"), "_stream_actions"),
]


def _match_stream(path: str) -> Optional[str]:
    clean = path.rstrip("/") or "/"
    for pattern, method_name in _STREAM_ROUTES:
        if pattern.match(clean):
            return method_name
    return None


def _job_deltas(prev: dict[str, dict], curr: dict[str, dict]):
    """Yield ``(event, data)`` SSE deltas between two job snapshots.

    ``job.upsert`` for any new or changed job (cheap dict compare — every store
    mutation bumps ``updated_at``); ``job.removed`` for any id that disappeared.
    On the first tick ``prev`` is empty, so the subscriber gets the full state as
    upserts, then deltas.
    """
    for jid, job in curr.items():
        if prev.get(jid) != job:
            yield "job.upsert", job
    for jid in prev.keys() - curr.keys():
        yield "job.removed", {"id": jid}


def _csv_set(value: Optional[str]) -> Optional[set[str]]:
    """Parse a comma-separated query filter into a set, or ``None`` if empty."""
    if not value:
        return None
    items = {v.strip() for v in value.split(",") if v.strip()}
    return items or None


def _event_passes(
    rec: dict, levels: Optional[set[str]], sources: Optional[set[str]],
    job_id: Optional[str],
) -> bool:
    if levels is not None and rec.get("level") not in levels:
        return False
    if sources is not None and rec.get("source") not in sources:
        return False
    if job_id and rec.get("job_id") != job_id:
        return False
    return True


def _make_handler(
    token: Optional[str],
    responder,
    stop_event: threading.Event,
    cors_origins: frozenset[str] = frozenset(),
    agent_mode: str = "jarvis",
):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # noqa: A002 - match base signature
            pass

        # -- CORS (opt-in via allowlist; empty set => no CORS, default) -----
        def _cors_origin(self) -> Optional[str]:
            """Return the request Origin iff it is in the allowlist, else None.

            With an empty allowlist this is always None, so no CORS header is
            ever emitted and default (same-origin / native-app) behavior is
            byte-for-byte unchanged.
            """
            origin = self.headers.get("Origin")
            if origin and origin.rstrip("/") in cors_origins:
                return origin
            return None

        def end_headers(self):  # inject CORS on every response to an allowed Origin
            origin = self._cors_origin()
            if origin is not None:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            super().end_headers()

        def do_OPTIONS(self):  # noqa: N802 - CORS preflight
            self.close_connection = True
            origin = self._cors_origin()
            if origin is None:
                # Unchanged default: OPTIONS is not a supported method.
                self.send_error(501, "Unsupported method ('OPTIONS')")
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            # Chrome Private Network Access: a public/HTTPS page reaching this
            # loopback (or LAN) gateway must get explicit consent on the
            # preflight, or the request is blocked before any route runs.
            if self.headers.get("Access-Control-Request-Private-Network") == "true":
                self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Content-Length", "0")
            self.end_headers()  # also injects Access-Control-Allow-Origin + Vary

        # -- auth -------------------------------------------------------
        def _authed(self) -> bool:
            # Accept EITHER the shared cockpit token (unchanged path) OR a
            # valid per-device pairing token. Additive + revoke-aware: a
            # revoked device's token never authenticates, and a missing or
            # invalid token still fails closed (-> 401).
            presented = cockpit_auth.extract_bearer(self.headers.get("Authorization"))
            return cockpit_auth.authorize_bearer(presented, token)

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

        # -- static UI shell -------------------------------------------
        _STATIC_TYPES = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".json": "application/json",
            ".ico": "image/x-icon",
            ".png": "image/png",
            ".webmanifest": "application/manifest+json",
            ".woff2": "font/woff2",
            ".woff": "font/woff",
            ".ttf": "font/ttf",
            ".map": "application/json",
            ".txt": "text/plain; charset=utf-8",
        }

        def _serve_static(self, path: str) -> bool:
            """Serve the bundled browser cockpit. Returns True if it handled the
            request. Path-traversal-safe; falls back to the section's entry
            document for unknown sub-paths so the single-page app can route
            client-side.

            The default cockpit document is ``cockpit.dc.html`` (the imported
            "Singularity" Claude Design). The prior modular shell stays reachable
            at ``/cockpit/index.html``; ``/nexus`` is unaffected."""
            root = (Path(__file__).resolve().parent / "static").resolve()
            cockpit_doc = "cockpit.dc.html"
            if path in ("/", "/cockpit", "/cockpit/"):
                rel = cockpit_doc
                default_doc = cockpit_doc
            elif path in ("/nexus", "/nexus/"):
                rel = "index.html"
                default_doc = "index.html"
            elif path.startswith("/cockpit/"):
                rel = path[len("/cockpit/"):].lstrip("/") or cockpit_doc
                default_doc = cockpit_doc
            elif path.startswith("/nexus/"):
                rel = path[len("/nexus/"):].lstrip("/") or "index.html"
                default_doc = "index.html"
            else:
                return False
            try:
                target = (root / rel).resolve()
                target.relative_to(root)  # reject ../ traversal
            except (ValueError, OSError):
                return False
            # Defense-in-depth: a request that names a concrete file suffix is
            # only served when that suffix is in the static type allowlist; an
            # unknown/disallowed suffix 404s (returns False) instead of leaking
            # as application/octet-stream. A *route* (no recognized file suffix,
            # e.g. "/cockpit/jobs") and a missing allowlisted file both fall back
            # to index.html so the single-page app can route client-side
            # (".html" is itself allowlisted).
            suffix = target.suffix
            if suffix and suffix not in self._STATIC_TYPES:
                return False  # disallowed file type -> 404
            if not target.is_file():
                target = root / default_doc  # SPA fallback (route or missing)
                if not target.is_file():
                    return False
            ctype = self._STATIC_TYPES.get(target.suffix, "application/octet-stream")
            try:
                data = target.read_bytes()
            except OSError:
                return False
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.wfile.flush()
            return True

        def _serve_nexus(self, path: str) -> bool:
            """Serve the built NEXUS PWA same-origin under ``/nexus/`` so the whole
            app + API live on one http origin (the phone's loopback). Returns True
            if handled. Path-traversal-safe; SPA-falls-back to its index.html. When
            no NEXUS build is present, returns False (404) and nothing else changes.
            """
            root = _nexus_dist_root()
            if root is None:
                return False
            if path in ("/nexus", "/nexus/"):
                rel = "index.html"
            elif path.startswith("/nexus/"):
                rel = path[len("/nexus/"):].lstrip("/") or "index.html"
            else:
                return False
            try:
                target = (root / rel).resolve()
                target.relative_to(root)  # reject ../ traversal
            except (ValueError, OSError):
                return False
            suffix = target.suffix
            if suffix and suffix not in self._STATIC_TYPES:
                return False  # disallowed file type -> 404
            if not target.is_file():
                target = root / "index.html"  # SPA fallback (route or missing)
                if not target.is_file():
                    return False
            ctype = self._STATIC_TYPES.get(target.suffix, "application/octet-stream")
            try:
                data = target.read_bytes()
            except OSError:
                return False
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.wfile.flush()
            return True

        # -- dispatch ---------------------------------------------------
        def _dispatch(self, method: str) -> None:
            self.close_connection = True
            path = urlsplit(self.path).path

            # Nexus-namespaced liveness probe — unauthenticated alias of
            # /v1/health. Lives BEFORE the static-shell check (which would
            # otherwise SPA-fallback /nexus/health to index.html) and BEFORE
            # the authed route table so device-paired clients on the /nexus/
            # surface can probe the gateway without a bearer token (mirrors
            # /v1/health's gating).
            if method == "GET" and path.rstrip("/") == "/nexus/health":
                req = h.Request(
                    method=method,
                    path=path,
                    query=self._query(),
                    body={},
                    path_params={},
                )
                resp = h.health(req)
                self._send_json(resp.status, resp.payload)
                return

            # Static cockpit UI shell (the browser app). Unauthenticated — it's
            # just HTML/CSS/JS; every API call it makes carries the bearer token.
            # GET only, path-traversal-safe. Served before the API route table.
            if method == "GET" and (path == "/" or path.startswith("/cockpit") or path.startswith("/nexus")):
                if self._serve_static(path):
                    return

            # NEXUS PWA, served same-origin under /nexus/ (when a build exists).
            # Lets a phone running MUSE in Termux reach the whole app + API on one
            # http loopback origin — no mixed-content barrier. Unauthenticated
            # shell; its API calls still carry the bearer token. GET only.
            if method == "GET" and (path == "/nexus" or path.startswith("/nexus/")):
                if self._serve_nexus(path):
                    return

            # Streaming chat endpoint (real agent) — POST only.
            if method == "POST" and path.rstrip("/") == CHAT_PATH:
                if not self._authed():
                    self._send_json(401, {"error": "missing or invalid bearer token"})
                    return
                self._stream_chat()
                return

            # Full-agent streaming chat — POST only, opt-in via --agent full.
            if method == "POST" and path.rstrip("/") == AGENT_CHAT_PATH:
                if not self._authed():
                    self._send_json(401, {"error": "missing or invalid bearer token"})
                    return
                if agent_mode != "full":
                    self._send_json(
                        409,
                        {
                            "error": "full agent mode is not enabled on this gateway",
                            "hint": "start it with: muse cockpit serve --agent full",
                            "agent": agent_mode,
                        },
                    )
                    return
                self._stream_agent_chat()
                return

            # Server-Sent Events live streams — GET only, matched before the
            # buffered table so "/jobs/stream" isn't read as "/jobs/{id}".
            if method == "GET":
                stream_name = _match_stream(path)
                if stream_name is not None:
                    if not self._authed():
                        self._send_json(401, {"error": "missing or invalid bearer token"})
                        return
                    getattr(self, stream_name)()
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

        def _stream_agent_chat(self) -> None:
            """NDJSON stream of one FULL-agent turn (tools, code, sub-agents).

            Body: ``{prompt, history?, session_id?, session_key?}``. The
            chunk vocabulary is the jarvis one plus ``body_delta`` (token
            streaming) and ``approval`` (owner gate; resolve via
            ``POST /v1/agent/approvals``).
            """
            from gateway.cockpit.agent_full import full_agent_responder

            payload = self._read_body()
            prompt = str(payload.get("prompt", ""))
            history = list(payload.get("history", []) or [])
            session_id = payload.get("session_id") or None
            session_key = payload.get("session_key") or None
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("X-Accel-Buffering", "no")  # defeat proxy buffering
            self.end_headers()
            try:
                stream = encode_stream(
                    full_agent_responder(
                        prompt,
                        history,
                        session_id=session_id,
                        session_key=session_key,
                    )
                )
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

        # -- Server-Sent Events ----------------------------------------
        def _sse_headers(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")  # defeat proxy buffering
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

        def _sse_send(self, event: str, data: dict) -> None:
            body = (
                f"event: {event}\r\n"
                f"data: {json.dumps(data, default=str, separators=(',', ':'))}\r\n\r\n"
            ).encode("utf-8")
            self._write_chunk(body)

        def _sse_sleep(self, total: float) -> None:
            # Sleep in small slices so shutdown (stop_event) is honored promptly.
            end = time.monotonic() + total
            while not stop_event.is_set():
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return
                time.sleep(min(0.05, remaining))

        def _stream_jobs(self) -> None:
            self._sse_headers()
            prev: dict[str, dict] = {}
            last_beat = time.monotonic()
            started = time.monotonic()
            try:
                while not stop_event.is_set():
                    curr = {j["id"]: j for j in h._collect_jobs()}
                    for event, data in _job_deltas(prev, curr):
                        self._sse_send(event, data)
                    prev = curr
                    now = time.monotonic()
                    if now - last_beat >= _SSE_HEARTBEAT_S:
                        self._sse_send("heartbeat", {"ts": h._now_iso()})
                        last_beat = now
                    if now - started >= _SSE_MAX_DURATION_S:
                        break
                    self._sse_sleep(_SSE_POLL_S)
                self._write_chunk(b"")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:  # pragma: no cover - defensive
                pass

        def _stream_events(self) -> None:
            self._sse_headers()
            q = self._query()
            levels = _csv_set(q.get("level"))
            sources = _csv_set(q.get("source"))
            job_id = q.get("job_id") or None
            offset = event_log.current_offset()
            last_beat = time.monotonic()
            started = time.monotonic()
            try:
                while not stop_event.is_set():
                    records, offset = event_log.read_since_offset(offset)
                    for rec in records:
                        if _event_passes(rec, levels, sources, job_id):
                            self._sse_send("log", rec)
                    now = time.monotonic()
                    if now - last_beat >= _SSE_HEARTBEAT_S:
                        self._sse_send("heartbeat", {"ts": h._now_iso()})
                        last_beat = now
                    if now - started >= _SSE_MAX_DURATION_S:
                        break
                    self._sse_sleep(_SSE_POLL_S)
                self._write_chunk(b"")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:  # pragma: no cover - defensive
                pass

        def _stream_observatory(self) -> None:
            """SSE stream of observatory events (job.stage / gate.verdict /
            node.activate / route.decision) as the passive collector records
            them. ``id:`` = the collector's monotonic sequence; honours
            ``Last-Event-ID`` replay from the in-memory ring and signals
            ``resync`` on a gap (spec §3.2). Read-only: opening the stream
            records nothing.
            """
            try:
                from gateway.cockpit import observatory_metrics as om

                collector = om.get_collector()
            except Exception:  # pragma: no cover - defensive
                self._send_json(503, {"error": "collector_unavailable"})
                return
            # Last-Event-ID replay: resume after the client's last seen seq;
            # a malformed/absent header starts from "now".
            try:
                seq = int(self.headers.get("Last-Event-ID", ""))
            except (TypeError, ValueError):
                seq = collector.latest_seq()
            self._sse_headers()
            last_beat = time.monotonic()
            started = time.monotonic()
            try:
                self._write_chunk(b"retry: 5000\r\n\r\n")
                events, seq, gap = collector.events_since(seq)
                if gap:
                    self._sse_send("resync", {"reason": "gap", "ts": h._now_iso()})
                    events = []
                while not stop_event.is_set():
                    for event_seq, kind, payload in events:
                        self._write_chunk(f"id: {event_seq}\r\n".encode("ascii"))
                        self._sse_send(kind, payload)
                    now = time.monotonic()
                    if now - last_beat >= _SSE_HEARTBEAT_S:
                        self._write_chunk(b": ping\r\n\r\n")
                        last_beat = now
                    if now - started >= _SSE_MAX_DURATION_S:
                        break
                    self._sse_sleep(_SSE_POLL_S)
                    events, seq, gap = collector.events_since(seq)
                    if gap:  # pragma: no cover - requires >ring events mid-stream
                        self._sse_send("resync", {"reason": "gap", "ts": h._now_iso()})
                        events = []
                self._write_chunk(b"")
            except (BrokenPipeError, ConnectionResetError):
                # Client disconnected mid-stream — expected for SSE consumers
                # (tab closed, reconnect with Last-Event-ID); nothing to clean up.
                pass
            except Exception:  # pragma: no cover - defensive
                pass

        def _stream_actions(self) -> None:
            """SSE feed fusing every real action source (observatory collector +
            flywheel + cockpit event log + axiom chain) for the live "neural
            network wallpaper". Read-only; dormant (503) when the observatory
            collector is opt-out. ``Last-Event-ID`` carries an opaque per-source
            cursor so a reconnect resumes after the last delivered batch.
            Fabricates nothing — only events that were really recorded.
            """
            try:
                from gateway.cockpit import action_fusion as af
                from gateway.cockpit import observatory_metrics as om
            except Exception:  # pragma: no cover - defensive
                self._send_json(503, {"error": "collector_unavailable"})
                return
            if not om.enabled():
                self._send_json(503, {"error": "collector_unavailable"})
                return
            tailer = af.FusionTailer(self.headers.get("Last-Event-ID"))
            self._sse_headers()
            last_beat = time.monotonic()
            started = time.monotonic()
            try:
                self._write_chunk(b"retry: 5000\r\n\r\n")
                if tailer.fresh:
                    self._sse_send("meta.resync", {"reason": "fresh", "ts": h._now_iso()})
                while not stop_event.is_set():
                    events = tailer.drain()
                    if events:
                        cursor = tailer.cursor()
                        for event in events:
                            self._write_chunk(f"id: {cursor}\r\n".encode("ascii"))
                            self._sse_send(event["kind"], event)
                    now = time.monotonic()
                    if now - last_beat >= _SSE_HEARTBEAT_S:
                        self._write_chunk(b": ping\r\n\r\n")
                        last_beat = now
                    if now - started >= _SSE_MAX_DURATION_S:
                        break
                    self._sse_sleep(_SSE_POLL_S)
                self._write_chunk(b"")
            except (BrokenPipeError, ConnectionResetError):
                # Client disconnected during SSE streaming; this is expected.
                return
            except Exception:  # pragma: no cover - defensive
                pass

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def do_PUT(self):  # noqa: N802
            self._dispatch("PUT")

        def do_DELETE(self):  # noqa: N802
            self._dispatch("DELETE")

    return Handler


class _CockpitServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that signals live SSE loops to stop on shutdown.

    An SSE handler occupies its thread for the connection's lifetime; without a
    stop signal it would keep polling after ``shutdown()`` (until its
    max-duration backstop). Setting ``_stop_event`` lets each loop exit within
    one short sleep slice.
    """

    daemon_threads = True
    _stop_event: Optional[threading.Event] = None

    def shutdown(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        super().shutdown()


def _host_in_allowlist(host: str, allowlist: _Iterable[str]) -> bool:
    """True if ``host`` matches any entry in ``allowlist`` (host or CIDR).

    Each entry is matched two ways: as a literal string equality (covers
    hostnames the resolver hasn't expanded) and, when both ``host`` and the
    entry parse as IP addresses/networks, as IP membership — so a bare host
    matches its own ``/32`` (``/128``) and a CIDR entry matches every address
    it contains. Anything that fails to parse falls back to the literal
    compare only. Never raises (fail-closed: an un-matchable entry simply does
    not authorize the bind).
    """
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    for raw in allowlist:
        entry = (raw or "").strip()
        if not entry:
            continue
        if entry == host:
            return True
        if addr is None:
            continue
        try:
            net = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if addr.version == net.version and addr in net:
            return True
    return False


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    token: Optional[str] = None,
    allow_external: bool = False,
    allow_external_hosts: Optional[_Iterable[str]] = None,
    cors_origins: Optional[_Iterable[str]] = None,
    responder=None,
    agent_mode: Optional[str] = None,
) -> ThreadingHTTPServer:
    """Start the cockpit API server in a background thread.

    Loopback-only unless ``allow_external=True`` (which also warns). The
    bearer ``token`` defaults to the persisted cockpit token (created on
    first use). ``responder`` overrides the chat responder (tests).

    ``agent_mode`` selects what ``POST /v1/agent/chat`` serves: ``"full"``
    runs the complete AIAgent (tools, code execution, sub-agents) with
    streaming + owner approvals; the default ``"jarvis"`` keeps that route
    answering 409 so existing deployments are byte-for-byte unchanged.
    Resolution order: explicit arg → ``HERMES_COCKPIT_AGENT`` env → jarvis.

    When binding a **non-loopback** host, ``allow_external=True`` is no longer
    sufficient on its own: the host must also appear in ``allow_external_hosts``
    — a list of explicit host strings and/or CIDR ranges (e.g.
    ``["10.0.0.5", "192.168.1.0/24"]``). A non-loopback host that is not in the
    allowlist raises ``ValueError`` (fail-closed). This is defense-in-depth on
    top of the per-request owner-phrase gate and the loopback-only execute
    refusal (``allow_remote_execute``), neither of which is weakened here. The
    default loopback bind never consults the allowlist and is unchanged.
    """
    if not _is_loopback_host(host) and not allow_external:
        raise ValueError(
            f"refusing to bind cockpit API to non-loopback host {host!r}; "
            "pass allow_external=True only if you understand the exposure risk"
        )
    if not _is_loopback_host(host):
        # Fail-closed allowlist: an explicit, opted-in host (allow_external=True)
        # must STILL be named in allow_external_hosts (host or CIDR). This blocks
        # accidentally exposing the wildcard "0.0.0.0"/"::" or an unintended NIC.
        hosts = list(allow_external_hosts or ())
        if not _host_in_allowlist(host, hosts):
            raise ValueError(
                f"refusing to bind cockpit API to non-loopback host {host!r}: "
                "host is not in the allow_external_hosts allowlist. Pass "
                "allow_external_hosts=[...] with the exact host or a CIDR that "
                f"contains it (got {hosts!r})."
            )
    if not _is_loopback_host(host):
        warnings.warn(
            f"cockpit API binding to non-loopback host {host!r} — exposes the "
            "agent endpoint to the network",
            stacklevel=2,
        )
    if token is None:
        token = cockpit_auth.load_or_create_token()
    # Browser origins allowed to call the API cross-origin (first-party muse
    # cockpit by default; extend/disable via --cors-origin /
    # HERMES_COCKPIT_CORS_ORIGINS). Pairing stays friction-free on a loopback
    # bind; if you expose the gateway over a tunnel, put authentication on the
    # tunnel (e.g. Cloudflare Access) — see
    # docs/remote/connect-cockpit-to-terminal.md. The CLI prints the active
    # allowlist on startup, so no stderr warning here.
    cors = _resolve_cors_origins(cors_origins)
    # Second guard for agentic execute lanes: only loopback cockpits may run
    # them (the owner-phrase gate is the first guard, enforced per-request).
    h.configure_runtime(allow_remote_execute=bool(allow_external))
    # Resolve the /v1/agent/chat mode: explicit arg → env → jarvis (default,
    # no behavior change). Anything unrecognized falls back to jarvis.
    resolved_agent_mode = (
        (agent_mode or os.environ.get("HERMES_COCKPIT_AGENT") or "jarvis").strip().lower()
    )
    if resolved_agent_mode not in ("jarvis", "full"):
        warnings.warn(
            f"unknown cockpit agent mode {resolved_agent_mode!r}; using 'jarvis'",
            stacklevel=2,
        )
        resolved_agent_mode = "jarvis"
    h.configure_agent_mode(resolved_agent_mode)

    if responder is not None:
        chat_responder = responder
    else:
        # Default chat path: drive the real JARVIS turn AND generate reply prose
        # from the running local model (Ollama). If no model is reachable, the
        # responder degrades to the turn summary rather than failing.
        from gateway.cockpit.generate import default_prose_generator

        def chat_responder(prompt, history):
            return jarvis_responder(prompt, history, generate=default_prose_generator)

    stop_event = threading.Event()
    server = _CockpitServer(
        (host, port),
        _make_handler(token, chat_responder, stop_event, cors, resolved_agent_mode),
    )
    server._stop_event = stop_event
    thread = threading.Thread(
        target=server.serve_forever, name="hermes-cockpit-http", daemon=True
    )
    thread.start()
    return server


__all__ = ["serve"]
