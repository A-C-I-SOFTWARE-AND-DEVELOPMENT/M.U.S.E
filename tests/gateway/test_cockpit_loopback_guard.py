"""Loopback / external-bind guard coverage for the cockpit server.

Two layers are pinned here:

1. The ``job_approve`` owner-approval route, double-gated exactly like
   ``job_run``: the owner phrase *and* a loopback-only guard (refused when the
   cockpit is bound beyond loopback via ``--allow-external``).
   ``test_cockpit_job_run`` covers the guard on the *execute* lane, but the
   equally sensitive *approval* route — the one that grants a gated phase — had
   no non-loopback coverage. These tests pin that behavior, including the
   security-critical ordering: the loopback guard is checked *before* the owner
   phrase, so a network-reachable cockpit is refused even when it presents the
   correct phrase.

2. FU-13 defense-in-depth: ``serve()``'s ``allow_external_hosts`` host/CIDR
   allowlist (a non-loopback bind must be explicitly allowlisted — fail-closed)
   and ``_serve_static``'s ``_STATIC_TYPES`` suffix allowlist (an existing file
   with a disallowed suffix 404s instead of leaking, while routes still fall
   back to the SPA index). The loopback-only execute refusal stays intact.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from gateway.cockpit import server as srv
from gateway.cockpit.server import serve
from muse_cli import orchestrator as orch
from muse_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    h.configure_runtime(allow_remote_execute=False)  # loopback by default
    return tmp_path


def _approve(job_id: str, **body) -> h.Request:
    return h.Request(method="POST", path="x", body=body, path_params={"id": job_id})


def _orc_job_id() -> str:
    resp = h.orchestrate_submit(
        h.Request(method="POST", path="x", body={"prompt": "edit the uploader"})
    )
    assert resp.status == 201
    return resp.payload["id"]


def test_unknown_job_404_precedes_loopback_guard(home) -> None:
    """``_resolve_job`` runs first: an unknown id is 404 even on non-loopback."""
    h.configure_runtime(allow_remote_execute=True)
    resp = h.job_approve(_approve("nope", authorization=AUTHORIZATION_PHRASE))
    assert resp.status == 404


def test_approve_blocked_on_non_loopback_even_with_phrase(home) -> None:
    """Defense in depth: a non-loopback cockpit is refused *before* the phrase
    check, so the correct phrase cannot grant a gated phase remotely."""
    job_id = _orc_job_id()
    h.configure_runtime(allow_remote_execute=True)  # simulate --allow-external
    resp = h.job_approve(_approve(job_id, authorization=AUTHORIZATION_PHRASE))
    assert resp.status == 403
    assert "non-loopback" in resp.payload["error"]


def test_approve_on_loopback_requires_owner_phrase(home) -> None:
    """On loopback the route still demands the exact owner phrase."""
    job_id = _orc_job_id()
    resp = h.job_approve(_approve(job_id, authorization="please"))
    assert resp.status == 403
    assert "owner approval required" in resp.payload["error"]
    assert AUTHORIZATION_PHRASE in resp.payload["hint"]


def test_approve_succeeds_on_loopback_with_phrase(home, monkeypatch) -> None:
    """Positive control: loopback + exact phrase reaches ``approve_phase`` and
    the guard does not over-block the legitimate path."""
    job_id = _orc_job_id()
    granted: list[str] = []

    def fake_approve(jid, phase):
        granted.append(phase)
        return orch.get_job(jid)

    monkeypatch.setattr(orch, "approve_phase", fake_approve)
    resp = h.job_approve(
        _approve(job_id, phase="execute", authorization=AUTHORIZATION_PHRASE)
    )
    assert resp.status == 200
    assert granted == ["execute"]


# ---------------------------------------------------------------------------
# FU-13: serve() host/CIDR allowlist (_host_in_allowlist matching)
# ---------------------------------------------------------------------------


def test_allowlist_matches_exact_host() -> None:
    assert srv._host_in_allowlist("10.0.0.5", ["10.0.0.5"]) is True


def test_allowlist_matches_cidr_membership() -> None:
    assert srv._host_in_allowlist("192.168.1.42", ["192.168.1.0/24"]) is True


def test_allowlist_rejects_host_outside_cidr() -> None:
    assert srv._host_in_allowlist("192.168.2.1", ["192.168.1.0/24"]) is False


def test_allowlist_no_match_is_false() -> None:
    assert srv._host_in_allowlist("10.0.0.5", ["10.0.0.6", "192.168.0.0/16"]) is False


def test_allowlist_ipv6_cidr_membership() -> None:
    assert srv._host_in_allowlist("fd00::5", ["fd00::/8"]) is True
    # v4 host never matches a v6 network (and vice versa).
    assert srv._host_in_allowlist("10.0.0.5", ["fd00::/8"]) is False


def test_allowlist_literal_hostname_match() -> None:
    # A non-IP hostname only matches by literal string equality.
    assert srv._host_in_allowlist("cockpit.lan", ["cockpit.lan"]) is True
    assert srv._host_in_allowlist("cockpit.lan", ["10.0.0.0/8"]) is False


def test_allowlist_ignores_blank_and_garbage_entries_without_raising() -> None:
    # Empty/whitespace entries are skipped; un-parseable entries fall back to
    # literal compare and never raise (fail-closed).
    assert srv._host_in_allowlist("10.0.0.5", ["", "  ", "not-a-cidr/xx"]) is False
    assert srv._host_in_allowlist("10.0.0.5", ["  10.0.0.5  "]) is True


# ---------------------------------------------------------------------------
# FU-13: serve() bind guard — fail-closed unless host is allowlisted
# ---------------------------------------------------------------------------


def test_serve_non_loopback_without_allow_external_raises(home) -> None:
    """Unchanged base guard: no allow_external -> refuse (with the original
    message), before any allowlist consideration."""
    with pytest.raises(ValueError, match="allow_external=True"):
        serve(host="203.0.113.7", port=0, token="t", allow_external=False)


def test_serve_non_loopback_allow_external_but_not_allowlisted_raises(home) -> None:
    """FU-13 fail-closed: allow_external=True is NOT enough — an empty allowlist
    still refuses a non-loopback bind."""
    with pytest.raises(ValueError, match="allow_external_hosts"):
        serve(host="203.0.113.7", port=0, token="t", allow_external=True)
    # Same when the host is simply absent from a non-empty allowlist.
    with pytest.raises(ValueError, match="allow_external_hosts"):
        serve(
            host="203.0.113.7", port=0, token="t",
            allow_external=True, allow_external_hosts=["10.0.0.0/8"],
        )


def test_serve_loopback_binds_without_allowlist_unchanged(home) -> None:
    """The default loopback path is untouched: it binds with no allowlist and
    does NOT enable the remote-execute lane."""
    h.configure_runtime(allow_remote_execute=False)
    server = serve(host="127.0.0.1", port=0, token="t")
    try:
        assert server.server_address[0] == "127.0.0.1"
        # Loopback must keep the execute lane disabled (guard intact).
        assert h._ALLOW_REMOTE_EXECUTE is False
    finally:
        server.shutdown()


def test_serve_allowlisted_non_loopback_binds_and_keeps_execute_refusal(
    home, monkeypatch
) -> None:
    """Positive control: a host present in the allowlist is allowed to bind.

    We bind a real loopback socket (sandbox can't bind a routable IP) but force
    the *non-loopback* code path by treating 127.0.0.1 as non-loopback for the
    duration. The allowlist then authorizes the bind, the server starts, and the
    loopback-only execute refusal is (correctly) enabled because the cockpit is
    now considered externally reachable."""
    monkeypatch.setattr(srv, "_is_loopback_host", lambda host: False)
    h.configure_runtime(allow_remote_execute=False)
    with pytest.warns(UserWarning, match="non-loopback"):
        server = serve(
            host="127.0.0.1", port=0, token="t",
            allow_external=True, allow_external_hosts=["127.0.0.1"],
            responder=lambda prompt, history: iter(()),
        )
    try:
        # The bind succeeded (allowlist authorized it).
        assert server.server_address[0] == "127.0.0.1"
        # Execute refusal is NOT weakened: an externally-bound cockpit flips the
        # remote-execute flag on, which the per-request handler guard reads to
        # refuse execute/approve lanes (see test below).
        assert h._ALLOW_REMOTE_EXECUTE is True
    finally:
        server.shutdown()


def test_execute_still_refused_when_bound_external(home) -> None:
    """The owner-approval execute lane stays refused on a non-loopback cockpit,
    exactly as before — the allowlist hardens the *bind*, never the lane."""
    job_id = _orc_job_id()
    h.configure_runtime(allow_remote_execute=True)  # simulate external bind
    resp = h.job_approve(_approve(job_id, authorization=AUTHORIZATION_PHRASE))
    assert resp.status == 403
    assert "non-loopback" in resp.payload["error"]


# ---------------------------------------------------------------------------
# FU-13: _serve_static suffix allowlist (defense-in-depth)
# ---------------------------------------------------------------------------


@pytest.fixture()
def static_server(home: Path):
    """A real loopback cockpit server for static-asset checks."""
    server = serve(
        host="127.0.0.1", port=0, token="t",
        responder=lambda prompt, history: iter(()),
    )
    try:
        yield server
    finally:
        server.shutdown()


def _static_get(server, path: str) -> int:
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_static_serves_allowlisted_suffix(static_server) -> None:
    """A known suffix in _STATIC_TYPES (.css) is served."""
    assert _static_get(static_server, "/cockpit/tokens.css") == 200


def test_static_route_falls_back_to_spa_index(static_server) -> None:
    """A route (no file suffix) still falls back to index.html — SPA routing is
    not broken by the suffix allowlist."""
    assert _static_get(static_server, "/cockpit/some/client/route") == 200


def test_static_disallowed_suffix_404s(static_server) -> None:
    """A file whose suffix is NOT in _STATIC_TYPES 404s instead of leaking as
    application/octet-stream. We drop a throwaway file into the static dir for
    the duration of the test (created + removed here, never committed)."""
    static_root = Path(srv.__file__).resolve().parent / "static"
    secret = static_root / "fu13_probe.py"
    secret.write_text("SECRET = 'should never be served'\n", encoding="utf-8")
    try:
        assert _static_get(static_server, "/cockpit/fu13_probe.py") == 404
    finally:
        secret.unlink(missing_ok=True)
