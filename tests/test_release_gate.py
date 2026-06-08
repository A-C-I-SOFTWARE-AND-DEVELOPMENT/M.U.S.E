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
    monkeypatch.setattr(rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "x"))

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
    monkeypatch.setattr(rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "x"))
    monkeypatch.setattr(
        rg,
        "_fast_test_slice_check",
        lambda **_kw: ReadinessCheck(TEST_SLICE_CHECK, PASS, "x"),
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
        lambda **_kw: ReadinessCheck(RUFF_CHECK, FAIL, "dirty", hard=True),
    )
    report = run_release_gate(run_tests=False)
    assert report.ok is False
    assert any(c.name == RUFF_CHECK and c.status == FAIL for c in report.failures)


def test_soft_fail_in_appended_check_does_not_block(monkeypatch):
    # A soft FAIL (hard=False) is never a ship blocker — mirror the doctor rule.
    monkeypatch.setattr(
        rg,
        "_ruff_check",
        lambda **_kw: ReadinessCheck(RUFF_CHECK, FAIL, "soft", hard=False),
    )
    report = run_release_gate(run_tests=False)
    # ok reflects only hard fails; the appended soft fail must not block.
    assert report.ok == (not run_10_10_doctor().hard_failures)


def test_clean_ruff_keeps_healthy_tree_shippable(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    report = run_release_gate(run_tests=False)
    # On a healthy tree (no doctor hard failures) a clean ruff stays shippable.
    assert report.ok == (not run_10_10_doctor().hard_failures)


# -- subprocess wrapper: failures surface as FAIL, never raise --------------


def test_ruff_check_missing_tool_is_soft_warn_not_fail(monkeypatch):
    # FU-10: when NO reachable ruff exists, the argv selector flags it
    # unavailable. That is "tooling absent", not a dirty tree, so the gate must
    # emit a soft WARN (never a hard FAIL that false-REDs ship).
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], False))
    check = rg._ruff_check()
    assert check.status == WARN
    assert check.hard is False
    assert "unavailable" in check.detail.lower()


def test_test_slice_missing_tool_is_soft_warn_not_fail(monkeypatch):
    # FU-10 core: no reachable interpreter has pytest -> the suite never ran.
    # Must be a soft WARN ("tooling absent"), NOT a hard FAIL masquerading as a
    # red slice.
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], False)
    )
    check = rg._fast_test_slice_check()
    assert check.status == WARN
    assert check.hard is False
    assert "unavailable" in check.detail.lower()


def test_test_slice_failure_is_fail(monkeypatch):
    # A genuinely red slice (tool present, exit non-zero, no missing-tool text)
    # is still a hard FAIL. Stub the argv selector to "available" so the probe
    # is bypassed and the run result drives the verdict.
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], True)
    )
    monkeypatch.setattr(rg, "_run_subprocess", lambda *a, **k: (1, "1 failed"))
    check = rg._fast_test_slice_check()
    assert check.status == FAIL
    assert check.hard is True


def test_ruff_failure_is_fail(monkeypatch):
    # A genuinely dirty tree (ruff present, exit non-zero, real lint text) stays
    # a hard FAIL.
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], True))
    monkeypatch.setattr(
        rg, "_run_subprocess", lambda *a, **k: (1, "E501 line too long")
    )
    check = rg._ruff_check()
    assert check.status == FAIL
    assert check.hard is True


def test_run_subprocess_never_raises_on_missing_executable():
    # Real call with a bogus argv: returns (127, msg), does not raise.
    code, tail = rg._run_subprocess(["definitely-not-a-real-binary-xyz"], timeout=5)
    assert code == 127
    assert "not found" in tail


# -- FU-10: pytest-less uv venv must not produce a false-RED ----------------
#
# These tests stub the subprocess seam to simulate the host where ``uv`` is on
# PATH but its project venv lacks pytest (``uv run python -c "import pytest"``
# exits non-zero), while the *system* interpreter has it. The selector must
# fall back to ``sys.executable`` and the gate must never hard-FAIL.


def _fake_subprocess(handlers):
    """Build a _run_subprocess replacement dispatching on argv contents.

    ``handlers`` is a list of ``(predicate, (code, tail))`` pairs; the first
    predicate matching the argv wins. Unmatched argv default to ``(0, "")``.
    """

    def _runner(argv, *, timeout):  # signature mirrors _run_subprocess
        for predicate, result in handlers:
            if predicate(argv):
                return result
        return (0, "")

    return _runner


def test_pytest_argv_falls_back_to_sys_executable_when_uv_lacks_pytest(monkeypatch):
    # uv is present, but `uv run python -c "import pytest"` fails (venv un-synced).
    # The system interpreter import succeeds. Selector must drop uv and use
    # sys.executable, and report the tool as available (not a WARN).
    monkeypatch.setattr(rg.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(
        rg,
        "_run_subprocess",
        _fake_subprocess(
            [
                # uv's interpreter cannot import pytest -> non-zero.
                (lambda a: a[:2] == ["uv", "run"], (1, "No module named pytest")),
                # the system interpreter import probe succeeds.
                (lambda a: a[0] == rg.sys.executable, (0, "")),
            ]
        ),
    )
    argv, available = rg._pytest_argv()
    assert available is True
    assert argv[:2] != ["uv", "run"]
    assert argv[0] == rg.sys.executable
    assert "pytest" in argv


def test_pytest_argv_prefers_uv_when_its_venv_has_pytest(monkeypatch):
    # Healthy default path: uv present AND its interpreter imports pytest ->
    # selector keeps the uv run path (current behavior, unchanged).
    monkeypatch.setattr(rg.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(rg, "_run_subprocess", _fake_subprocess([]))  # all zero
    argv, available = rg._pytest_argv()
    assert available is True
    assert argv[:3] == ["uv", "run", "python"]


def test_pytest_argv_unavailable_when_no_interpreter_has_pytest(monkeypatch):
    # Neither uv's venv nor the system interpreter has pytest -> available False
    # so the caller emits a soft WARN, never a hard FAIL.
    monkeypatch.setattr(rg.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(
        rg,
        "_run_subprocess",
        _fake_subprocess(
            [(lambda a: True, (1, "No module named pytest"))]  # every import fails
        ),
    )
    _argv, available = rg._pytest_argv()
    assert available is False


def test_pytest_slice_end_to_end_falls_back_not_false_red(monkeypatch):
    # Full _fast_test_slice_check on the pytest-less-uv host: uv import probe
    # fails, system import probe passes, and the actual slice run is GREEN under
    # the system interpreter -> PASS (the false-RED is gone).
    def _runner(argv, *, timeout):
        if argv[:2] == ["uv", "run"]:
            return (1, "No module named pytest")  # uv venv lacks pytest
        if argv[0] == rg.sys.executable and argv[1:] == ["-c", "import pytest"]:
            return (0, "")  # system interpreter has pytest
        if argv[0] == rg.sys.executable and "pytest" in argv:
            return (0, "")  # the real slice run is green
        return (0, "")

    monkeypatch.setattr(rg.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(rg, "_run_subprocess", _runner)
    check = rg._fast_test_slice_check()
    assert check.status == PASS
    assert check.hard is True


def test_pytest_slice_defensive_downgrade_on_missing_module_text(monkeypatch):
    # Defensive layer: even if the probe says "available", a run that still
    # reports "No module named pytest" is downgraded from FAIL to WARN — a
    # missing runner never masquerades as a red suite.
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], True)
    )
    monkeypatch.setattr(
        rg,
        "_run_subprocess",
        lambda *a, **k: (1, "No module named pytest"),
    )
    check = rg._fast_test_slice_check()
    assert check.status == WARN
    assert check.hard is False


def test_tool_absent_warn_keeps_gate_shippable(monkeypatch):
    # A soft WARN from a tool-absent slice must NOT flip the verdict to not-ok
    # on an otherwise-healthy tree (no hard failures => still shippable).
    monkeypatch.setattr(
        rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    monkeypatch.setattr(
        rg,
        "_fast_test_slice_check",
        lambda **_kw: ReadinessCheck(TEST_SLICE_CHECK, WARN, "pytest unavailable", hard=False),
    )
    report = run_release_gate(run_tests=True)
    assert report.ok == (not run_10_10_doctor().hard_failures)
    # The WARN is recorded (audit honesty), it just doesn't block.
    assert any(
        c.name == TEST_SLICE_CHECK and c.status == WARN for c in report.warnings
    )


def test_ruff_argv_falls_back_to_bare_ruff_when_uv_lacks_ruff(monkeypatch):
    # uv present but `uv run ruff --version` fails; a bare ruff works. Selector
    # must fall back to the bare ruff invocation and report it available.
    monkeypatch.setattr(rg.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        rg,
        "_run_subprocess",
        _fake_subprocess(
            [
                (lambda a: a[:2] == ["uv", "run"], (1, "error: no ruff")),
                (lambda a: a[0] == "ruff", (0, "ruff 0.x")),
            ]
        ),
    )
    argv, available = rg._ruff_argv()
    assert available is True
    assert argv[:2] != ["uv", "run"]
    assert argv[0] == "ruff"


def test_probe_ok_never_raises_on_bogus_argv():
    # The probe wraps _run_subprocess, so a missing binary is False, not a raise.
    assert rg._probe_ok(["definitely-not-a-real-binary-xyz"]) is False


# -- JSON / dict render shape ----------------------------------------------


def test_release_gate_json_shape(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "clean")
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
        rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    text = run_release_gate(run_tests=False).render()
    # Reuses the doctor's renderer, so the heading + a verdict line are present.
    assert "release-readiness doctor" in text
    assert ("SAFE TO SHIP" in text) or ("NOT SHIPPABLE" in text)
    assert RUFF_CHECK in text


# -- well-formedness (live doctor checks, stubbed runtime gates) ------------


def test_every_check_is_wellformed(monkeypatch):
    monkeypatch.setattr(
        rg, "_ruff_check", lambda **_kw: ReadinessCheck(RUFF_CHECK, PASS, "clean")
    )
    report = run_release_gate(run_tests=False)
    assert len(report.checks) >= 20
    for c in report.checks:
        assert c.status in {PASS, WARN, FAIL}
        assert c.name
    s = report.to_dict()["summary"]
    assert s["total"] == len(report.checks)
    assert s["failures"] >= s["hard_failures"]


# -- WC-2: strict tooling on release hosts ---------------------------------
#
# The FU-10 anti-false-RED design (soft WARN on tool absence) protects dev
# checkouts but inverts the gate on a release host: a stripped Termux release
# lane or CI runner with no ruff/pytest reports GREEN ship having validated
# nothing. WC-2 adds an opt-in strict mode — set ``HERMES_RELEASE_GATE_STRICT=1``
# (or pass ``strict_tooling=True``) and missing tools become a hard FAIL.


def test_ruff_missing_under_strict_is_hard_fail(monkeypatch):
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], False))
    check = rg._ruff_check(strict_tooling=True)
    assert check.status == FAIL
    assert check.hard is True
    assert "release-host strict mode" in check.detail
    assert "HERMES_RELEASE_GATE_STRICT" in check.detail


def test_ruff_missing_under_dev_default_stays_soft_warn(monkeypatch):
    """FU-10 behavior preserved: tool absent on a dev box never false-REDs."""
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], False))
    check = rg._ruff_check(strict_tooling=False)
    assert check.status == WARN
    assert check.hard is False


def test_test_slice_missing_under_strict_is_hard_fail(monkeypatch):
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], False)
    )
    check = rg._fast_test_slice_check(strict_tooling=True)
    assert check.status == FAIL
    assert check.hard is True
    assert "release-host strict mode" in check.detail


def test_test_slice_missing_under_dev_default_stays_soft_warn(monkeypatch):
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], False)
    )
    check = rg._fast_test_slice_check(strict_tooling=False)
    assert check.status == WARN
    assert check.hard is False


def test_env_var_enables_strict_mode_by_default(monkeypatch):
    """The env var is the canonical release-lane opt-in."""
    monkeypatch.setenv("HERMES_RELEASE_GATE_STRICT", "1")
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], False))
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], False)
    )
    # No explicit strict_tooling arg — env var should drive the verdict.
    report = run_release_gate(run_tests=True)
    # On a release host where both ruff and pytest are missing, the gate
    # MUST refuse to ship (the WC-2 headline behavior).
    assert report.ok is False
    names = [c.name for c in report.failures]
    assert RUFF_CHECK in names
    assert TEST_SLICE_CHECK in names


def test_env_var_off_keeps_dev_default(monkeypatch):
    """Without the opt-in env var, dev hosts stay shippable on tool absence."""
    monkeypatch.delenv("HERMES_RELEASE_GATE_STRICT", raising=False)
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], False))
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], False)
    )
    report = run_release_gate(run_tests=True)
    # Soft WARNs on both runtime checks — overall verdict tracks the doctor.
    assert report.ok == (not run_10_10_doctor().hard_failures)
    warn_names = [c.name for c in report.warnings]
    assert RUFF_CHECK in warn_names
    assert TEST_SLICE_CHECK in warn_names


def test_strict_tooling_explicit_override_beats_env(monkeypatch):
    """``strict_tooling=False`` is the dev escape hatch even with env set."""
    monkeypatch.setenv("HERMES_RELEASE_GATE_STRICT", "1")
    monkeypatch.setattr(rg, "_ruff_argv", lambda: (["ruff", "check", "."], False))
    monkeypatch.setattr(
        rg, "_pytest_argv", lambda: ([rg.sys.executable, "-m", "pytest"], False)
    )
    report = run_release_gate(run_tests=True, strict_tooling=False)
    # Explicit False overrides the env var truthy value.
    assert report.ok == (not run_10_10_doctor().hard_failures)
    # And tool-absent slots are WARN, not FAIL.
    statuses = {c.name: c.status for c in report.checks}
    assert statuses[RUFF_CHECK] == WARN
    assert statuses[TEST_SLICE_CHECK] == WARN


def test_strict_env_truthy_variants(monkeypatch):
    """Every canonical truthy value flips the gate."""
    for value in ("1", "true", "True", "yes", "ON"):
        monkeypatch.setenv("HERMES_RELEASE_GATE_STRICT", value)
        assert rg._strict_tooling_enabled() is True, f"value={value!r} should enable strict"


def test_strict_env_falsey_and_unset_stay_off(monkeypatch):
    for value in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("HERMES_RELEASE_GATE_STRICT", value)
        assert rg._strict_tooling_enabled() is False, f"value={value!r} should stay off"
    monkeypatch.delenv("HERMES_RELEASE_GATE_STRICT", raising=False)
    assert rg._strict_tooling_enabled() is False
