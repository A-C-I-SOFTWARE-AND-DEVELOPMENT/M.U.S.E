"""Tests for the JARVIS launch-readiness doctor.

Hermetic: a fresh HERMES_HOME under tmp_path. The doctor must report
LAUNCH READY on a clean checkout — missing local runtimes / workers are
warnings, never hard launch blockers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import launch_doctor as ld


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _check(report: ld.LaunchReport, name: str) -> ld.LaunchCheck:
    for c in report.checks:
        if c.name == name:
            return c
    raise AssertionError(f"check {name!r} not found")


def test_launch_doctor_overall_ready(hermes_home: Path) -> None:
    report = ld.run_launch_doctor()
    assert report.ok is True, [c.to_dict() for c in report.failures]


def test_hard_checks_pass(hermes_home: Path) -> None:
    report = ld.run_launch_doctor()
    for name in (
        "package_import",
        "jarvis_prime_import",
        "jarvis_module_runnable",
        "jarvis_handle",
        "memory_dir",
        "owner_gate",
        "emergency_stop",
        "model_brain",
        "termux_compat",
    ):
        assert _check(report, name).status == ld.PASS, name


def test_owner_gate_check_enforces_exact_phrase(hermes_home: Path) -> None:
    report = ld.run_launch_doctor()
    c = _check(report, "owner_gate")
    assert c.status == ld.PASS
    assert "phrase" in c.detail.lower()


def test_missing_runtime_is_warning_not_failure(
    hermes_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force "no local runtime" by monkeypatching detection.
    from hermes_cli.jarvis_prime import model_bootstrap as mb

    monkeypatch.setattr(
        mb, "detect_local_runtimes",
        lambda which=None: {"ollama": {"available": False}},
    )
    report = ld.run_launch_doctor()
    c = _check(report, "local_runtimes")
    assert c.status == ld.WARN
    assert c.hard is False
    # A warning must not flip the overall verdict.
    assert report.ok is True


def test_no_paid_dependency_on_free_path(hermes_home: Path) -> None:
    report = ld.run_launch_doctor()
    c = _check(report, "no_paid_dependency")
    assert c.status == ld.PASS


def test_install_script_flag_detected(hermes_home: Path) -> None:
    # The shipped installer must advertise --jarvis-launch.
    report = ld.run_launch_doctor()
    c = _check(report, "install_script")
    assert c.status == ld.PASS, c.detail


def test_report_json_shape(hermes_home: Path) -> None:
    report = ld.run_launch_doctor()
    d = report.to_dict()
    assert set(d) == {"ok", "checks", "summary"}
    assert d["summary"]["failures"] == 0
    assert all({"name", "status", "detail", "hard"} <= set(c) for c in d["checks"])


def test_failure_in_hard_check_flips_overall(
    hermes_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate a hard model-brain failure and confirm the report is not ok.
    def boom() -> ld.LaunchCheck:
        return ld.LaunchCheck("model_brain", ld.FAIL, "simulated", hard=True)

    monkeypatch.setattr(ld, "_check_model_brain", boom)
    report = ld.run_launch_doctor()
    assert report.ok is False
    assert any(c.name == "model_brain" and c.status == ld.FAIL for c in report.checks)


def test_guardrail_checks_present_and_pass(hermes_home: Path) -> None:
    report = ld.run_launch_doctor()
    for name in (
        "guardrail_ledger_writable",
        "guardrail_ledger_verifies",
        "strict_gate_rejects_self_attestation",
        "owner_challenge_nonce_enforced",
        "secret_scan_operational",
        "emergency_stop_journaled",
        "packet_id_stable",
    ):
        assert _check(report, name).status == ld.PASS, name


def test_guardrail_hard_failure_blocks_launch(
    hermes_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> ld.LaunchCheck:
        return ld.LaunchCheck(
            "strict_gate_rejects_self_attestation", ld.FAIL, "simulated", hard=True
        )

    monkeypatch.setattr(ld, "_check_strict_gate_rejects_self_attestation", boom)
    report = ld.run_launch_doctor()
    assert report.ok is False
