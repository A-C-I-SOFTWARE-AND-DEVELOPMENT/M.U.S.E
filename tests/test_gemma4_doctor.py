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
    # Reconciled catalog: gemma family locals = e2b, e4b, 12b (the phantom
    # gemma4-26b / gemma4-31b were removed; installed gemma4-12b added).
    # Keyed cloud gemma entries (e.g. cerebras/gemma-4-31b-it) may also
    # appear, so assert the local set rather than an exact count.
    assert {
        "ollama-local/gemma4-e2b",
        "ollama-local/gemma4-e4b",
        "ollama-local/gemma4-12b",
    } <= set(payload["configured"])
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


# ---------------------------------------------------------------------------
# GPU / Ollama runtime-health advisories (WARN-only, injectable, never block)
# ---------------------------------------------------------------------------


def _names(report):
    return {c.name: c for c in report.checks}


def test_runtime_health_advisories_present_and_never_block() -> None:
    # Inject a clean, all-good runtime: server up, model fully on GPU, no bad env.
    report = run_gemma_doctor(
        ollama_ps_runner=lambda: (
            "NAME            ID    SIZE   PROCESSOR    UNTIL\n"
            "gemma4:e4b      abc   4.0 GB 100% GPU     4 minutes from now\n"
        ),
        ollama_serve_probe=lambda: True,
        env={},
    )
    names = _names(report)
    # All four advisory checks are wired into the gemma doctor.
    for name in (
        "gpu_driver",
        "ollama_processor",
        "ollama_env_hygiene",
        "ollama_server",
    ):
        assert name in names, name
        assert names[name].hard is False
    assert names["ollama_processor"].status == PASS
    assert names["ollama_env_hygiene"].status == PASS
    assert names["ollama_server"].status == PASS
    # Advisories are WARN-level: a clean wiring report is still ok.
    assert report.ok is True


def test_ollama_processor_warns_on_cpu_loaded_model() -> None:
    report = run_gemma_doctor(
        ollama_ps_runner=lambda: (
            "NAME            ID    SIZE   PROCESSOR        UNTIL\n"
            "qwen3-coder:30b abc   18 GB  48%/52% CPU/GPU  4 minutes from now\n"
        ),
        ollama_serve_probe=lambda: True,
        env={},
    )
    c = _names(report)["ollama_processor"]
    assert c.status == WARN
    assert c.hard is False
    assert "qwen3-coder:30b" in c.detail
    # WARN must not flip the overall verdict.
    assert report.ok is True


def test_ollama_env_hygiene_warns_on_num_ctx() -> None:
    report = run_gemma_doctor(env={"OLLAMA_NUM_CTX": "32768"})
    c = _names(report)["ollama_env_hygiene"]
    assert c.status == WARN
    assert "OLLAMA_CONTEXT_LENGTH" in c.detail
    assert "OLLAMA_NUM_CTX" in c.detail
    assert report.ok is True


def test_ollama_server_warns_when_installed_but_down() -> None:
    report = run_gemma_doctor(ollama_serve_probe=lambda: False, env={})
    c = _names(report)["ollama_server"]
    assert c.status == WARN
    assert "ollama serve" in c.detail
    assert report.ok is True


def test_ollama_server_quiet_when_not_installed() -> None:
    # Inconclusive probe (no ollama binary) → quiet PASS, no false alarm.
    report = run_gemma_doctor(ollama_serve_probe=lambda: None, env={})
    c = _names(report)["ollama_server"]
    assert c.status == PASS
    assert report.ok is True


# ---------------------------------------------------------------------------
# Action #11 — post-download health check (ollama list confirms the tag)
# ---------------------------------------------------------------------------


def test_post_download_health_check_verifies_present_tag() -> None:
    from hermes_cli.local_models.bootstrap import (
        DownloadOutcome,
        post_download_health_check,
    )

    out = DownloadOutcome(model="gemma4-e4b", attempted=True, ok=True)
    listing = "NAME        ID    SIZE   MODIFIED\ngemma4:e4b  abc   4.0 GB 1 minute ago\n"
    post_download_health_check(out, "gemma4:e4b", ollama_list_runner=lambda: listing)
    assert out.health_verified is True
    assert "gemma4:e4b" in out.health_detail


def test_post_download_health_check_flags_missing_tag() -> None:
    from hermes_cli.local_models.bootstrap import (
        DownloadOutcome,
        post_download_health_check,
    )

    out = DownloadOutcome(model="gemma4-e4b", attempted=True, ok=True)
    listing = "NAME        ID    SIZE   MODIFIED\nqwen3.5:9b  abc   6.0 GB 1 minute ago\n"
    post_download_health_check(out, "gemma4:e4b", ollama_list_runner=lambda: listing)
    assert out.health_verified is False
    assert "ollama list" in out.health_detail


def test_post_download_health_check_inconclusive_when_list_empty() -> None:
    # Empty/unreadable ``ollama list`` must NOT mark a good download as failed.
    from hermes_cli.local_models.bootstrap import (
        DownloadOutcome,
        post_download_health_check,
    )

    out = DownloadOutcome(model="gemma4-e4b", attempted=True, ok=True)
    post_download_health_check(out, "gemma4:e4b", ollama_list_runner=lambda: "")
    assert out.health_verified is None


def test_bare_tag_matches_latest_in_listing() -> None:
    # ``ollama pull gemma4`` lands as ``gemma4:latest`` in the listing.
    from hermes_cli.local_models.bootstrap import (
        DownloadOutcome,
        post_download_health_check,
    )

    out = DownloadOutcome(model="gemma4", attempted=True, ok=True)
    listing = "NAME           ID    SIZE   MODIFIED\ngemma4:latest  abc   4.0 GB 1 minute ago\n"
    post_download_health_check(out, "gemma4", ollama_list_runner=lambda: listing)
    assert out.health_verified is True


def test_execute_bootstrap_verify_health_appends_to_outcome() -> None:
    from hermes_cli.local_models.bootstrap import execute_bootstrap, plan_bootstrap
    from hermes_cli.local_models.hardware_probe import HardwareProfile

    laptop = HardwareProfile("Linux", "x86_64", 8, 16.0, 0.0, 200.0)
    plan = plan_bootstrap("laptop", hardware=laptop)
    # Only the ollama items that report installed will attempt a pull; health
    # verification only runs on those successful ollama pulls. The injected list
    # runner reports every pulled tag as present, so any attempted ollama pull
    # gets health_verified=True; non-attempted items stay None.
    pulled: list[tuple[str, ...]] = []

    def fake_pull(cmd):
        pulled.append(tuple(cmd))
        return True, "ok"

    def fake_list():
        # Echo back every tag that was pulled as a NAME line.
        lines = ["NAME ID SIZE MODIFIED"]
        for cmd in pulled:
            if len(cmd) >= 3 and cmd[0] == "ollama" and cmd[1] == "pull":
                lines.append(f"{cmd[2]} abc 4.0 GB now")
        return "\n".join(lines) + "\n"

    outcomes = execute_bootstrap(
        plan,
        accept_downloads=True,
        runner=fake_pull,
        verify_health=True,
        ollama_list_runner=fake_list,
    )
    assert outcomes
    attempted_ollama = [
        o for o in outcomes if o.attempted and o.ok and o.command[:2] == ("ollama", "pull")
    ]
    # Every attempted ollama pull was health-verified against the listing.
    for o in attempted_ollama:
        assert o.health_verified is True
        assert "ollama list" in o.health_detail


def test_execute_bootstrap_health_default_off_is_unchanged() -> None:
    # Default path: verify_health off ⇒ health fields stay None (byte-for-byte
    # behavior preserved for existing callers).
    from hermes_cli.local_models.bootstrap import execute_bootstrap, plan_bootstrap
    from hermes_cli.local_models.hardware_probe import HardwareProfile

    laptop = HardwareProfile("Linux", "x86_64", 8, 16.0, 0.0, 200.0)
    plan = plan_bootstrap("laptop", hardware=laptop)
    outcomes = execute_bootstrap(
        plan, accept_downloads=True, runner=lambda cmd: (True, "ok")
    )
    assert all(o.health_verified is None for o in outcomes)
