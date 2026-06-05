"""Tests for the unified release gate (`hermes doctor --release-gate`)."""

from __future__ import annotations

from hermes_cli import release_gate as rg
from hermes_cli.release_gate import run_release_gate
from hermes_cli.release_readiness_doctor import (
    FAIL,
    PASS,
    WARN,
    ReadinessCheck,
    ReadinessReport,
    run_10_10_doctor,
)

# Names of the runtime checks the gate appends on top of the doctor's checks.
RUFF_CHECK = "ruff lint"
TEST_SLICE_CHECK = "fast test slice"


# -- composition: gate == doctor checks + ruff (+ test slice) --------------


def test_release_gate_appends_ruff_to_doctor_checks(monkeypatch):
    # Stub the ruff subprocess so the shape test is deterministic and fast.
    monkeypatch.setattr(rg, "_ruff_check", lambda: ReadinessCheck(RUFF_CHECK, PASS, "x"))

    doctor_checks = run_10_10_doctor().checks
    report = run_release_gate(run_tests=False)

    assert isinstance(report, ReadinessReport)
    names = [c.name for c in report.checks]
    # Every doctor check is present, in order, followed by the ruff check.
    assert names[: len(doctor_checks)] == [c.name for c in doctor_checks]
    assert names[-1] == RUFF_CHECK
    # run_tests=False must NOT append the slow test-slice check.
    assert TEST_SLICE_CHECK not in names
    # Exactly one extra check (ruff) beyond the doctor's set.
    assert len(report.checks) == len(doctor_checks) + 1


def test_release_gate_includes_test_slice_when_requested(monkeypatch):
    monkeypatch.setattr(rg, "_ruff_check", lambda: ReadinessCheck(RUFF_CHECK, PASS, "x"))
    monkeypatch.setattr(
        rg,
        "_fast_test_slice_check",
        lambda: ReadinessCheck(TEST_SLICE_CHECK, PASS, "x"),
    )

    doctor_checks = run_10_10_doctor().checks
    report = run_release_gate(run_tests=True)

    names = [c.name for c in report.checks]
    assert names[-2:] == [RUFF_CHECK, TEST_SLICE_CHECK]
    assert len(report.checks) == len(doctor_checks) + 2


# -- ok aggregation: only hard FAILs block ---------------------------------


def test_ok_aggregates_only_hard_failures(monkeypatch):
    # A real doctor run on a healthy tree has no hard failures; force ruff to
    # FAIL hard and the combined verdict must flip to not-ok.
    monkeypatch.setattr(
        rg,
        "_ruff_check",
        lambda: ReadinessCheck(RUFF_CHECK, FAIL, "dirty", hard=True),
    )
    report = run_release_gate(run_tests=False)
    assert report.ok is False
    assert any(c.name == RUFF_CHECK and c.status == FAIL for c in report.failures)


def test_soft_fail_in_appended_check_does_not_block(monkeypatch):
    # A soft FAIL (hard=False) is never a ship blocker — mirror the doctor rule.
    monkeypatch.setattr(
        rg,
        "_ruff_check",
        lambda: ReadinessCheck(RUFF_CHECK, FAIL, "soft", hard=False),
    )
    report = run_release_gate(run_tests=False)
    # ok reflects only hard fails; the appended soft fail must not block.
    assert report.ok == (not run_10_10_doctor().hard_failures)


def test_clean_ruff_keeps_healthy_tree_shippable(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    report = run_release_gate(run_tests=False)
    # On a healthy tree (no doctor hard failures) a clean ruff stays shippable.
    assert report.ok == (not run_10_10_doctor().hard_failures)


# -- subprocess wrapper: failures surface as FAIL, never raise --------------


def test_ruff_check_missing_tool_is_fail(monkeypatch):
    # If neither uv nor ruff is on PATH, the subprocess wrapper reports 127 and
    # the ruff gate becomes a FAIL rather than raising.
    monkeypatch.setattr(rg, "_run_subprocess", lambda *a, **k: (127, "not found"))
    check = rg._ruff_check()
    assert check.status == FAIL
    assert check.hard is True


def test_test_slice_failure_is_fail(monkeypatch):
    monkeypatch.setattr(rg, "_run_subprocess", lambda *a, **k: (1, "1 failed"))
    check = rg._fast_test_slice_check()
    assert check.status == FAIL
    assert check.hard is True


def test_run_subprocess_never_raises_on_missing_executable():
    # Real call with a bogus argv: returns (127, msg), does not raise.
    code, tail = rg._run_subprocess(["definitely-not-a-real-binary-xyz"], timeout=5)
    assert code == 127
    assert "not found" in tail


# -- JSON / dict render shape ----------------------------------------------


def test_release_gate_json_shape(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    report = run_release_gate(run_tests=False)
    d = report.to_dict()
    assert set(d) == {"ok", "checks", "summary"}
    assert set(d["summary"]) == {
        "total",
        "passed",
        "warnings",
        "failures",
        "hard_failures",
    }
    assert d["summary"]["total"] == len(report.checks)
    # The appended ruff check appears in the serialized checks with all fields.
    ruff = next(c for c in d["checks"] if c["name"] == RUFF_CHECK)
    assert set(ruff) == {"name", "status", "detail", "hard"}


def test_release_gate_render_is_human_readable(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    text = run_release_gate(run_tests=False).render()
    # Reuses the doctor's renderer, so the heading + a verdict line are present.
    assert "release-readiness doctor" in text
    assert ("SAFE TO SHIP" in text) or ("NOT SHIPPABLE" in text)
    assert RUFF_CHECK in text


# -- well-formedness (live doctor checks, stubbed runtime gates) ------------


def test_every_check_is_wellformed(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    report = run_release_gate(run_tests=False)
    assert len(report.checks) >= 20
    for c in report.checks:
        assert c.status in {PASS, WARN, FAIL}
        assert c.name
    s = report.to_dict()["summary"]
    assert s["total"] == len(report.checks)
    assert s["failures"] >= s["hard_failures"]
