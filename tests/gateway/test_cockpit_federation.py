"""Cockpit Federation status route — read-only, public fields only.

Critically asserts the handler never leaks private key / HMAC secret material;
only public identity fields and the peer list are surfaced.
"""

from __future__ import annotations

import json

from gateway.cockpit.handlers import Request, federation_status

_PUBLIC_IDENTITY_KEYS = {"node_id", "display_name", "created_at", "algo", "public_key_hex"}


def _req() -> Request:
    return Request(method="GET", path="/v1/cockpit/federation/status")


def test_federation_status_shape_and_no_secret_leak():
    resp = federation_status(_req())
    assert resp.status == 200
    p = resp.payload
    assert {"identity", "peers", "peer_count"}.issubset(p)
    assert isinstance(p["peers"], list)
    assert isinstance(p["peer_count"], int)
    # Never leak private/secret key material.
    dumped = json.dumps(p)
    assert "private" not in dumped and "secret" not in dumped
    # If a node identity exists, it must be public-only.
    if p["identity"] is not None:
        assert set(p["identity"].keys()) <= _PUBLIC_IDENTITY_KEYS
