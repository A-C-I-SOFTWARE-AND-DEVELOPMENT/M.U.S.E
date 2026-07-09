"""CLI: ``jarvis_prime council`` — roster / dispatch."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from typing import Any

from hermes_cli.jarvis_prime.__main__ import main as cli_main


def _run(argv: list[str]) -> tuple[int, Any]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(argv)
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else {})


def test_council_roster_json():
    code, body = _run(["council", "roster", "--json"])
    assert code == 0
    assert len(body["active_council"]) >= 5
    assert len(body["domain_specialists"]) >= 5


def test_council_dispatch_json_engages_council_plus_specialist():
    code, body = _run(["council", "dispatch", "architecture and scaling change", "--json"])
    assert code == 0
    assert body["engaged_count"] >= 6  # the active council is always engaged
    assert any(m["id"] == "principal-systems-architect" for m in body["specialists"])


def test_council_dispatch_threads_effort_class_into_dispatch(monkeypatch):
    # Prove the real CLI dispatch path now computes and threads a non-None
    # effort_class into dispatch() — so enabling MUSE_EFFORT_CAP would cap a
    # real turn. We wrap dispatch to capture the effort_class it receives.
    import hermes_cli.jarvis_prime.aos_council as council_pkg
    from hermes_cli.jarvis_prime import __main__ as cli_mod

    captured: dict[str, object] = {}
    real_dispatch = council_pkg.dispatch

    def _spy(request, **kwargs):
        captured["effort_class"] = kwargs.get("effort_class")
        return real_dispatch(request, **kwargs)

    # The CLI imports ``dispatch`` from the package at call time, so patch the
    # package attribute the ``from ... import dispatch`` inside _cmd_council binds.
    monkeypatch.setattr(council_pkg, "dispatch", _spy)
    # Also patch the name already imported at module top, if present.
    if hasattr(cli_mod, "dispatch"):
        monkeypatch.setattr(cli_mod, "dispatch", _spy, raising=False)

    request = "should we change product strategy"
    code, _body = _run(["council", "dispatch", request, "--json"])
    assert code == 0
    # The point: a non-None effort_class reached dispatch (so enabling the cap
    # flag would cap a real turn). The exact value is whatever the deterministic
    # offline bridge computes for this request — assert they agree.
    from hermes_cli.jarvis_prime.effort_class import classify_effort_for_request

    expected = classify_effort_for_request(request)
    assert expected is not None
    assert captured["effort_class"] == expected
