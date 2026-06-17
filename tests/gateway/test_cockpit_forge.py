"""Cockpit Forge route — read-only championship leaderboard.

Surfaces the CLI-only `jarvis_prime forge` tournament system over the gateway.
The shape is stable whether or not anything has competed yet (honest-empty).
"""

from __future__ import annotations

from gateway.cockpit.handlers import Request, forge_leaderboard


def _req() -> Request:
    return Request(method="GET", path="/v1/cockpit/forge/leaderboard")


def test_forge_leaderboard_returns_stable_shape():
    resp = forge_leaderboard(_req())
    assert resp.status == 200
    p = resp.payload
    assert isinstance(p["standings"], list)
    assert isinstance(p["candidates"], int)
    assert isinstance(p["coverage"], (int, float))
    assert isinstance(p["qd_score"], (int, float))
