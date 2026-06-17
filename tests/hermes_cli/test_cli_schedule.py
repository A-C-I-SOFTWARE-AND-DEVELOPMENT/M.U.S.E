"""CLI: ``jarvis_prime schedule`` — add / list / due / run."""

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
    try:
        return code, json.loads(out)
    except json.JSONDecodeError:
        return code, out


def test_schedule_add_list_due(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    code, body = _run(["schedule", "add", "--kind", "forge-tournament", "--every", "3600", "--json"])
    assert code == 0
    assert body["kind"] == "forge-tournament"

    code, listed = _run(["schedule", "list", "--json"])
    assert code == 0
    assert len(listed) == 1

    code, due = _run(["schedule", "due", "--json"])
    assert code == 0
    assert len(due) == 1  # never run ⇒ due


def test_schedule_run_skips_owner_gated_without_phrase(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _run(["schedule", "add", "--kind", "autoresearch", "--every", "86400"])
    code, results = _run(["schedule", "run", "--json"])
    assert code == 0
    assert any("skipped" in r["output"] for r in results)
