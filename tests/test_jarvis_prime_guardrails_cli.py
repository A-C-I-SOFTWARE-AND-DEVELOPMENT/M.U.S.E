"""Tests for the ``hermes guardrails`` CLI.

Driven via ``cmd_guardrails`` with argparse Namespaces — no network, no
credentials, no heavyweight CLI import chain. The autouse hermetic fixture
isolates HERMES_HOME under tmp.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json

import pytest

from hermes_cli.guardrails_cli import cmd_guardrails, register


def _run(**kwargs) -> tuple[int, str]:
    ns = argparse.Namespace(**kwargs)
    buf = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf):
            cmd_guardrails(ns)
    except SystemExit as exc:
        code = int(exc.code) if exc.code is not None else 0
    return code, buf.getvalue()


def test_register_attaches_subcommands() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    register(sub)
    args = parser.parse_args(["guardrails", "verify-ledger", "--json"])
    assert args.func is cmd_guardrails
    assert args.guardrails_command == "verify-ledger"


def test_status_runs_without_network() -> None:
    code, out = _run(guardrails_command="status", json=True)
    assert code == 0
    data = json.loads(out)
    assert "ledger_path" in data
    assert data["chain_ok"] is True


def test_verify_ledger_on_empty_ledger() -> None:
    code, out = _run(guardrails_command="verify-ledger", json=True)
    assert code == 0
    assert json.loads(out)["ok"] is True


def test_doctor_passes_in_hermetic_env() -> None:
    code, out = _run(guardrails_command="doctor", json=True)
    data = json.loads(out)
    assert data["ok"] is True, data
    assert code == 0
    names = {c["name"] for c in data["checks"]}
    assert "strict_gate_rejects_self_attestation" in names
    assert "memory_proposed_excluded" in names


def test_authorize_prints_nonce_phrase_and_response_round_trip() -> None:
    code, out = _run(
        guardrails_command="authorize",
        action="package_publish",
        subject="pkg",
        rationale="",
        json=True,
    )
    assert code == 0
    challenge = json.loads(out)
    assert challenge["required_phrase"].startswith("Yes, with authorization. Code:")
    cid = challenge["challenge_id"]

    # Wrong (bare) phrase is not authorized.
    code, out = _run(
        guardrails_command="authorize-response",
        challenge_id=cid,
        phrase="Yes, with authorization.",
        json=True,
    )
    assert code == 1
    assert json.loads(out)["authorized"] is False

    # Correct phrase authorizes and appends a grant to the ledger.
    code, out = _run(
        guardrails_command="authorize-response",
        challenge_id=cid,
        phrase=challenge["required_phrase"],
        json=True,
    )
    assert code == 0
    result = json.loads(out)
    assert result["authorized"] is True
    assert result["ledger_record_hash"]

    # The ledger still verifies after the grant append.
    code, out = _run(guardrails_command="verify-ledger", json=True)
    assert json.loads(out)["ok"] is True


def test_collect_emits_artifacts_for_packet(tmp_path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-c", "user.email=t@t.t",
             "-c", "user.name=t", *args],
            cwd=repo, check=True, capture_output=True,
        )

    git("init")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", "init")
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")

    packet = {
        "packet_id": "p1",
        "repo_root": str(repo),
        "allowed_files": ["a.py"],
        "planned_verification_commands": ["python -m compileall -q a.py"],
        "planned_rollback": ["git checkout a.py"],
    }
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    code, out = _run(
        guardrails_command="collect",
        packet=str(packet_path),
        run_tests=True,
        json=True,
    )
    assert code == 0
    data = json.loads(out)
    types = {a["artifact_type"] for a in data["artifacts"]}
    assert {"git_diff", "secret_scan", "rollback", "test_result"} <= types


def test_unknown_subcommand_usage() -> None:
    code, _ = _run(guardrails_command=None)
    assert code == 2
