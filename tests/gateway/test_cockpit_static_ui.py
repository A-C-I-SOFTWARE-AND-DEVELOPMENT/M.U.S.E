"""The browser cockpit's static UI shell, served by the cockpit HTTP server.

Boots the real server on an ephemeral loopback port and hits it with
http.client. Confirms: the shell is served (unauthenticated), assets resolve,
path traversal can't leak source, the `/v1/*` API still takes precedence over
the static handler, and the shell actually *consumes* the rich backend it is
served alongside (live SSE jobs stream, owner-gated approvals, phase rail,
model switcher, first-run pairing, autonomy control).
"""

from __future__ import annotations

import http.client
import json

import pytest

from gateway.cockpit import server as srv


def _get(port: int, path: str, token: str | None = None) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        conn.request("GET", path, headers=headers)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


@pytest.fixture()
def cockpit(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    httpd = srv.serve(
        "127.0.0.1", 0, token="testtoken",
        responder=lambda prompt, history: iter(()),
    )
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()


@pytest.fixture()
def shell() -> str:
    """The full client bundle (index.html + tokens.css + cockpit.css + every
    js module) as one string.

    The cockpit is a modular, build-free ES-module app: the shell is just the
    structure, and the backend wiring lives across ``js/core/*`` and
    ``js/views/*`` (loaded via ``<script type=module>``). These "shell consumes
    the depth backend" assertions check the *client surface* contract, so they
    run against the whole served bundle, not just index.html.
    """
    from pathlib import Path

    static = Path(srv.__file__).resolve().parent / "static"
    parts = [
        (static / "index.html").read_text(encoding="utf-8"),
        (static / "tokens.css").read_text(encoding="utf-8"),
        (static / "cockpit.css").read_text(encoding="utf-8"),
    ]
    parts += [p.read_text(encoding="utf-8") for p in sorted((static / "js").rglob("*.js"))]
    return "\n".join(parts)


def test_serves_cockpit_index_unauthenticated(cockpit):
    # The shell is plain HTML/CSS/JS; it must load without a token (its API
    # calls carry the bearer token afterward).
    for path in ("/cockpit/", "/cockpit", "/"):
        status, body = _get(cockpit, path)
        assert status == 200, path
        assert b"muse" in body, path
        assert b"Multi-Use Synaptic Entity" in body


def test_serves_tokens_css(cockpit):
    status, body = _get(cockpit, "/cockpit/tokens.css")
    assert status == 200
    assert b"--void" in body and b"--ring-1" in body


def test_traversal_cannot_leak_source(cockpit):
    status, body = _get(cockpit, "/cockpit/../../gateway/cockpit/server.py")
    # Never serve the python source; either 404 or the SPA index fallback.
    assert b"_make_handler" not in body
    assert b"def _serve_static" not in body
    assert status in (200, 404)


@pytest.mark.parametrize(
    "path",
    [
        # Percent-encoded traversal variants must not decode into the parent
        # dir and leak the server source (folded in from code review).
        "/cockpit/%2e%2e/%2e%2e/server.py",
        "/cockpit/%2e%2e/%2e%2e/gateway/cockpit/server.py",
        "/cockpit/..%2f..%2fserver.py",
        "/cockpit/..%2f..%2fgateway%2fcockpit%2fserver.py",
    ],
)
def test_percent_encoded_traversal_cannot_leak_source(cockpit, path):
    status, body = _get(cockpit, path)
    # Server source bytes must never leak, regardless of status.
    assert b"_make_handler" not in body
    assert b"def _serve_static" not in body
    assert b"ThreadingHTTPServer" not in body
    assert status in (200, 404)


def test_api_takes_precedence_over_static(cockpit):
    # /v1/health is unauthenticated and must hit the API, not the static handler.
    status, body = _get(cockpit, "/v1/health")
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_api_route_still_requires_auth(cockpit):
    # A /v1/* route under the static prefix space must still reach the API and
    # enforce auth (proves the static hook didn't shadow the route table).
    status, _ = _get(cockpit, "/v1/cockpit/jobs")
    assert status == 401


# --- The shell consumes the depth backend (FU-14) --------------------------
# These assert the client actually wires up to the real endpoints, so the
# "browser shell throws away the rich backend" regression cannot return.


def test_shell_subscribes_to_jobs_sse_stream(shell):
    # A live subscription to the SSE jobs stream — not the old one-shot poll.
    # (A native EventSource can't carry the bearer header the server requires,
    # so the shell streams the SSE body via fetch with the Accept header.)
    assert "/v1/cockpit/jobs/stream" in shell
    assert "text/event-stream" in shell
    # It consumes the server's job delta events.
    assert "job.upsert" in shell
    assert "job.removed" in shell


def test_shell_has_phase_rail(shell):
    # A visible per-job phase progression element.
    assert "phaserail" in shell
    assert "phaseRail" in shell


def test_shell_has_owner_gated_approve_deny(shell):
    # Approve/Reject controls that POST the decision; approve is owner-gated.
    assert "/v1/cockpit/approvals/" in shell
    assert '"approve"' in shell and '"reject"' in shell
    # The owner phrase is prompted at action time (ownerPost) and a 403
    # re-prompts; it is never hardcoded/stored in the client.
    assert "ownerPost" in shell
    assert "promptOwnerPhrase" in shell
    assert "Yes, with authorization." not in shell


def test_shell_has_model_switcher(shell):
    # Reads model-routes and POSTs an override per task class.
    assert "/v1/cockpit/model-routes" in shell
    assert "/v1/cockpit/model-routes/override" in shell
    assert "task_class" in shell


def test_shell_has_pairing_entry_point(shell):
    # First-run pairing flow (start + confirm) instead of a dead end.
    assert "/v1/cockpit/pair/start" in shell
    assert "/v1/cockpit/pair/confirm" in shell
    assert "pairing_code" in shell


def test_shell_has_autonomy_control(shell):
    # Autonomy raise is owner-gated: sends the authorization phrase, handles 403.
    assert "/v1/cockpit/autonomy" in shell
    assert "ownerPost" in shell
    assert "authorization" in shell


def test_shell_loads_without_token_then_uses_token(shell):
    # The shell must boot unauthenticated and only attach the bearer token to
    # its API calls (carried via the Authorization header, like the existing
    # fetch calls).
    assert "musecockpit.token" in shell
    assert "Bearer " in shell
