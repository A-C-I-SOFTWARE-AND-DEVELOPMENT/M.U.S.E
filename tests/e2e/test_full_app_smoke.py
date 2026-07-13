"""End-to-end "client journey" smoke for the whole app.

Exercises the surfaces a real owner touches, with no network and no model
configured â€” proving the pieces *synergize* rather than just import:

1. **Cockpit HTTP server** boots, gates on the bearer token, reports health,
   and streams a **real** muse turn over the chunk vocabulary the
   Android avatar consumes (``thinking`` â†’ ``tone`` â†’ â€¦ â†’ ``body`` â†’ ``done``).
2. **Shared memory** is one brain across surfaces: a fact written through one
   ``JarvisPrime`` instance is recollected by a *fresh* instance pointed at the
   same ``HERMES_HOME`` â€” i.e. surfaces learn from one another.

These run without API keys: the chat responder degrades to the JARVIS turn
summary when no model is reachable, which is the designed behaviour.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME so the journey never touches a real profile."""
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def _req(base, method, path, token, body=None, auth=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if auth:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    return urllib.request.urlopen(req, timeout=30)


def test_cockpit_journey_health_auth_and_streaming_chat(hermes_home):
    """Boot the cockpit and walk health â†’ auth gate â†’ streamed JARVIS turn."""
    from gateway.cockpit.server import serve

    token = "e2e-smoke-token"
    server = serve(host="127.0.0.1", port=0, token=token)
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    try:
        # Health needs no auth and reports the service identity.
        health = json.loads(_req(base, "GET", "/v1/health", token, auth=False).read())
        assert health.get("ok") is True
        assert health.get("service") == "muse-cockpit"

        # Authed routes reject a missing token.
        with pytest.raises(urllib.error.HTTPError) as exc:
            _req(base, "GET", "/v1/cockpit/runtime/status", token, auth=False)
        assert exc.value.code == 401

        # Streamed chat returns a real JARVIS turn in the avatar chunk vocabulary.
        resp = _req(
            base, "POST", "/v1/jarvis/chat", token,
            body={"prompt": "Hi Jarvis, what mode are you in?", "history": []},
        )
        kinds = []
        for raw in resp:
            line = raw.decode().strip()
            if not line or line == "0":
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = chunk.get("type") or chunk.get("kind")
            if kind:
                kinds.append(kind)
        # A genuine turn always opens with a thinking beat and closes with body+done.
        assert kinds and kinds[0] == "thinking"
        assert "body" in kinds
        assert kinds[-1] == "done"
    finally:
        server.shutdown()


def test_shared_memory_is_one_brain_across_surfaces(hermes_home):
    """A durable fact written by one surface is recollected by another."""
    from hermes_cli.jarvis_prime.runtime import JarvisPrime

    # Surface A (e.g. the CLI) records a durable owner preference.
    surface_a = JarvisPrime()
    wrote = surface_a.config.memory.remember(
        key="owner_pref",
        value="The owner prefers dark mode and terse replies.",
        durability="durable",
        confidence=1.0,
    )
    assert wrote

    # Surface B (e.g. the cockpit) is a fresh runtime over the same HERMES_HOME.
    surface_b = JarvisPrime()
    hits = surface_b.config.memory.recollect("what does the owner prefer?") or []

    def _text(hit):
        for attr in ("value", "text", "content", "summary"):
            val = getattr(hit, attr, None)
            if val is None and isinstance(hit, dict):
                val = hit.get(attr)
            if val:
                return str(val)
        return str(hit)

    assert any("dark mode" in _text(h) for h in hits), (
        "fact written by surface A was not visible to surface B â€” memory is not shared"
    )
