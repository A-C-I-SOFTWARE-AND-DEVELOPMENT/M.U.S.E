"""Gemma 4 — doctor + CLI tests (no network, smoke is opt-in)."""

from __future__ import annotations

import argparse
import json
import io
import contextlib

from hermes_cli.jarvis_prime import gemma_cli
from hermes_cli.jarvis_prime.gemma_doctor import run_gemma_doctor
from hermes_cli.jarvis_prime.launch_doctor import FAIL, PASS, WARN


def test_doctor_reports_wired_status_and_is_ok() -> None:
    report = run_gemma_doctor()  # no runner → installed not probed
    assert report.ok  # missing local Gemma is a warning, not a blocker
    names = {c.name: c for c in report.checks}
    assert names["gemma_provider_catalog"].status == PASS
    assert names["gemma_open_weight_candidates"].status == PASS
    assert names["gemma_oss_brain"].status == PASS
    # Safety invariants are hard PASS.
    assert names["gemma_thought_sanitizer"].status == PASS
    assert names["gemma_memory_proposed_only"].status == PASS
    assert names["gemma_promotion_evidence_gated"].status == PASS


def test_missing_local_gemma_is_warning_not_failure() -> None:
    report = run_gemma_doctor()  # no ollama in test env
    names = {c.name: c for c in report.checks}
    assert names["gemma_local_runtime"].status in (PASS, WARN)
    assert names["gemma_installed"].status == WARN
    assert names["gemma_installed"].hard is False
    # No hard failure overall.
    assert not any(c.status == FAIL and c.hard for c in report.checks)


def test_installed_probe_is_injectable() -> None:
    report = run_gemma_doctor(ollama_list_runner=lambda: "gemma4:e4b  abc  4.0 GB\n")
    installed = {c.name: c for c in report.checks}["gemma_installed"]
    assert installed.status == PASS
    assert "gemma4" in installed.detail


def test_smoke_requires_variant_and_is_opt_in() -> None:
    # No variant → usage error, never touches a model.
    rc = gemma_cli.dispatch(
        argparse.Namespace(gemma_command="smoke", variant=None, json=False)
    )
    assert rc == 2


def test_smoke_uses_injected_runner_and_records_load_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli.jarvis_prime import gemma_load_status as gls

    args = argparse.Namespace(
        gemma_command="smoke", variant="gemma4-e4b", json=True,
        _smoke_runner=lambda tag: (True, f"ok {tag}"),
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = gemma_cli.dispatch(args)
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["status"] == "smoke_tested"
    assert payload["tag"] == "gemma4:e4b"
    # The smoke result is persisted so the router's load-gate can read it.
    assert gls.variant_status("gemma4-e4b") == gls.STATUS_OK

    # A failing smoke records a failure (arms the E4B→E2B downgrade).
    args.json = True
    args._smoke_runner = lambda tag: (False, "OOM")
    with contextlib.redirect_stdout(io.StringIO()):
        gemma_cli.dispatch(args)
    assert gls.variant_failed("gemma4-e4b") is True


def test_status_json_lists_configured_and_candidates() -> None:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = gemma_cli.dispatch(argparse.Namespace(gemma_command="status", json=True))
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert len(payload["configured"]) == 4
    assert len(payload["open_weight_candidates"]) == 4
    assert payload["installed"] is None  # not probed (opt-in)


def test_promote_writes_owner_gated_proposal(tmp_path, monkeypatch) -> None:
    from hermes_cli.jarvis_prime import model_scorecard as ms

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(ms, "DEFAULT_SCORECARD_PATH", tmp_path / "sc.jsonl")
    book = ms.ScorecardBook()
    for _ in range(25):
        book.record(
            ms.ModelScorecard(
                model="gpt-oss-20b", provider="ollama", task_type="memory_curator",
                accepted_diff_rate=0.6, memory_usefulness=0.6,
                tests_passed=6, tests_failed=4,
                hallucination_corrections=1, owner_corrections=1,
            ),
            persist=False,
        )
    for _ in range(25):
        book.record(
            ms.ModelScorecard(
                model="gemma4-e4b", provider="ollama", task_type="memory_curator",
                accepted_diff_rate=0.9, memory_usefulness=0.9,
                tests_passed=9, tests_failed=1,
            ),
            persist=False,
        )
    book.save()

    args = argparse.Namespace(
        gemma_command="promote", task_class="memory_curator", dry_run=False, json=True
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = gemma_cli.dispatch(args)
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["eligible"] and payload["candidate"] == "gemma4-e4b"
    assert payload["proposal_written"] is True
    assert payload["proposal"]["kind"] == "routing_rule_update"

    # The proposal landed in the same store the `proposals` CLI reads.
    store = tmp_path / "jarvis_prime" / "proposals.jsonl"
    assert store.is_file()
    rec = json.loads(store.read_text().splitlines()[0])
    assert rec["kind"] == "routing_rule_update"
    assert "rollback" in rec


def test_promote_dry_run_does_not_write(tmp_path, monkeypatch) -> None:
    from hermes_cli.jarvis_prime import model_scorecard as ms

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(ms, "DEFAULT_SCORECARD_PATH", tmp_path / "sc.jsonl")
    # No scorecards → not eligible → rc 1, nothing written.
    args = argparse.Namespace(
        gemma_command="promote", task_class="memory_curator", dry_run=True, json=False
    )
    rc = gemma_cli.dispatch(args)
    assert rc == 1
    assert not (tmp_path / "jarvis_prime" / "proposals.jsonl").is_file()
