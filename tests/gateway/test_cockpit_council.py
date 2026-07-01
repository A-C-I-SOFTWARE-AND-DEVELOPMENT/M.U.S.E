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


def test_council_dispatch_threads_effort_class(monkeypatch):
    # The cockpit council route now computes an effort_class (offline) and
    # threads it into dispatch, so enabling MUSE_EFFORT_CAP would cap a real
    # cockpit turn. Spy on the package dispatch the handler imports.
    import hermes_cli.jarvis_prime.aos_council as council_pkg

    captured: dict[str, object] = {}
    real_dispatch = council_pkg.dispatch

    def _spy(request, **kwargs):
        captured["effort_class"] = kwargs.get("effort_class")
        return real_dispatch(request, **kwargs)

    monkeypatch.setattr(council_pkg, "dispatch", _spy)
    request = "should we change product strategy"
    resp = council_dispatch(
        Request(
            method="GET",
            path="/v1/cockpit/council/dispatch",
            query={"q": request},
        )
    )
    assert resp.status == 200
    # A non-None effort_class reached dispatch (so enabling MUSE_EFFORT_CAP would
    # cap a real cockpit turn); it matches the deterministic offline bridge.
    from hermes_cli.jarvis_prime.effort_class import classify_effort_for_request

    expected = classify_effort_for_request(request)
    assert expected is not None
    assert captured["effort_class"] == expected
