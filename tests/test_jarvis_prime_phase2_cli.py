"""Integration tests for the Phase-2 NL-compiler CLI surface.

Covers the new language backends, the rerank/grammar flags, the gated
flow-exec command, and the dry-run learning prepare-job — all deterministic
and side-effect-free / owner-gated.
"""

from __future__ import annotations

import json

from muse_cli.jarvis_prime.__main__ import main


def test_compile_python_backend(capsys) -> None:
    rc = main(["compile", "write a python function to parse a date",
               "--json", "--grammar-repair", "--rerank"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"]["selected"] == "python"
    assert payload["compile"]["target"] == "python"
    assert payload["grammar"]["ok"] is True
    assert payload["lane"] is not None


def test_compile_sql_backend(capsys) -> None:
    rc = main(["compile", "select all invoices where the vendor is new",
               "--backend", "sql", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"]["selected"] == "sql"
    assert "sql" in payload["compile"]["artifact"]


def test_compile_rust_backend(capsys) -> None:
    rc = main(["compile", "implement a rust module for fast hashing", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"]["selected"] == "rust"


def test_flow_exec_simulate_no_external_io(capsys) -> None:
    rc = main(["flow-exec", "when an invoice email arrives, alert me", "--json"])
    assert rc == 0
    run = json.loads(capsys.readouterr().out)
    assert run["executed"] is False
    # External steps are recorded but never performed in simulate mode.
    assert all(not s["performed"] for s in run["steps"] if s["op"] in
               ("alert", "message", "send", "post"))


def test_flow_exec_execute_refused_without_authorization(capsys) -> None:
    rc = main(["flow-exec", "when an invoice email arrives, alert me",
               "--execute", "--json"])
    # No authorization phrase → external ops refused, nothing executed.
    run = json.loads(capsys.readouterr().out)
    assert run["executed"] is False


def test_learning_prepare_job_dry_run_launches_nothing(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    out_dir = tmp_path / "job"
    rc = main(["learning", "prepare-job", "--base-model", "demo",
               "--out-dir", str(out_dir), "--json"])
    assert rc == 0
    spec = json.loads(capsys.readouterr().out)
    # No owner-approved examples in a fresh store → not ready, no launch.
    assert spec["ready"] is False
