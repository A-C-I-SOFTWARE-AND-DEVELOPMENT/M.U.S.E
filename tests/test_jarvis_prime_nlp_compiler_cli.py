"""CLI wiring tests for `jarvis_prime compile`.

Covers subparser registration, flag parsing, exit codes (incl. 2 on
clarification), and JSON output shape.
"""

from __future__ import annotations

import json

from hermes_cli.jarvis_prime.__main__ import main

INVOICE = (
    "when a new invoice email arrives, extract the total, save the PDF, "
    "write the amount to the ledger, and alert me if the vendor is new"
)


def test_compile_command_runs(capsys) -> None:
    rc = main(["compile", INVOICE])
    assert rc == 0
    out = capsys.readouterr().out
    assert "backend: automation_flow" in out


def test_compile_json_shape(capsys) -> None:
    rc = main(["compile", INVOICE, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"]["selected"] == "automation_flow"
    assert payload["compile"]["target"] == "automation_flow"
    assert payload["needs_clarification"] is False


def test_compile_clarification_exit_code(capsys) -> None:
    rc = main(["compile", "do the thing with the stuff"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "Clarifying questions" in out


def test_compile_backend_override(capsys) -> None:
    rc = main(["compile", INVOICE, "--backend", "work-packet", "--explain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "backend: repo_work_packet" in out


def test_compile_gate_check_repo(capsys) -> None:
    rc = main(["compile", "add a function to the gateway module", "--gate-check"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "GATE SUMMARY" in out.upper() or "planning" in out.lower()
