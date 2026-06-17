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
