"""Cockpit AOS council route — read-only registry routing."""

from __future__ import annotations

from gateway.cockpit.handlers import Request, council_dispatch


def test_council_dispatch_routes_request():
    resp = council_dispatch(
        Request(method="GET", path="/v1/cockpit/council/dispatch", query={"q": "architecture and scaling change"})
    )
    assert resp.status == 200
    assert resp.payload["engaged_count"] >= 6
    assert any(m["id"] == "principal-systems-architect" for m in resp.payload["specialists"])


def test_council_dispatch_requires_q():
    resp = council_dispatch(Request(method="GET", path="/v1/cockpit/council/dispatch", query={}))
    assert resp.status == 400
