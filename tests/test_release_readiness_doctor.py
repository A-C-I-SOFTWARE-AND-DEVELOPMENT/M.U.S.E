"""Tests for the 10/10 release-readiness doctor (`hermes doctor --10-10`)."""

from __future__ import annotations

from hermes_cli import release_readiness_doctor as rrd
from hermes_cli.release_readiness_doctor import (
    FAIL,
    PASS,
    WARN,
    ReadinessCheck,
    ReadinessReport,
    run_10_10_doctor,
)


# -- data model (deterministic / synthetic) --------------------------------


def test_report_ok_logic():
    # A soft warn never blocks; a hard fail does; a soft fail does not.
    soft_warn = ReadinessReport(
        ok=True, checks=[ReadinessCheck("x", WARN, "", hard=False)]
    )
    assert soft_warn.warnings and not soft_warn.hard_failures

    hard_fail = ReadinessReport(
        ok=False, checks=[ReadinessCheck("y", FAIL, "", hard=True)]
    )
    assert hard_fail.hard_failures

    soft_fail = [ReadinessCheck("z", FAIL, "", hard=False)]
    assert not ReadinessReport(ok=True, checks=soft_fail).hard_failures


def test_to_dict_shape():
    report = ReadinessReport(
        ok=True,
        checks=[
            ReadinessCheck("a", PASS, "ok"),
            ReadinessCheck("b", WARN, "later", hard=False),
        ],
    )
    d = report.to_dict()
    assert d["ok"] is True
    assert d["summary"] == {
        "total": 2,
        "passed": 1,
        "warnings": 1,
        "failures": 0,
        "hard_failures": 0,
    }
    assert [c["name"] for c in d["checks"]] == ["a", "b"]


def test_render_human_output():
    report = ReadinessReport(ok=True, checks=[ReadinessCheck("a", PASS, "ok")])
    text = report.render()
    assert "release-readiness doctor" in text
    assert "SAFE TO SHIP" in text

    blocked = ReadinessReport(
        ok=False, checks=[ReadinessCheck("a", FAIL, "no", hard=True)]
    )
    assert "NOT SHIPPABLE" in blocked.render()


def test_check_wrapper_turns_exception_into_fail():
    def boom() -> ReadinessCheck:
        raise RuntimeError("kaboom")

    result = rrd._check(boom)
    assert result.status == FAIL
    assert "kaboom" in result.detail


# -- live run against the actual repo --------------------------------------


def test_run_doctor_is_wellformed():
    report = run_10_10_doctor()
    assert isinstance(report, ReadinessReport)
    assert len(report.checks) >= 20
    # every check has a valid status and a non-empty name
    for c in report.checks:
        assert c.status in {PASS, WARN, FAIL}
        assert c.name
    # summary counts are internally consistent
    s = report.to_dict()["summary"]
    assert s["total"] == len(report.checks)
    assert s["failures"] >= s["hard_failures"]


def test_repo_is_safe_to_ship_with_no_hard_failures():
    # The hard safety/correctness gates must all pass on a healthy tree;
    # if one breaks (e.g. owner gate removed, a dep unpinned), this fails.
    report = run_10_10_doctor()
    assert report.hard_failures == [], "hard gate(s) failing: " + "; ".join(
        f"{c.name}: {c.detail}" for c in report.hard_failures
    )
    assert report.ok is True


def test_stable_hard_gates_pass():
    by_name = {c.name: c for c in run_10_10_doctor().checks}
    for name in (
        "owner gate",
        "secret redaction",
        "decision engine present",
        "exact-pinned dependencies",
        "uv.lock present",
        "github publisher dry-run default",
    ):
        assert by_name[name].status == PASS, f"{name}: {by_name[name].detail}"


def test_release_artifacts_check_sees_the_shipped_docs():
    # The artifacts this PR adds should make the release-gate-artifacts check pass.
    by_name = {c.name: c for c in run_10_10_doctor().checks}
    assert by_name["release-gate artifacts"].status == PASS


def test_hard_gates_inspect_real_signature_defaults():
    # The publisher/cockpit hard gates read the ACTUAL parameter default (AST),
    # not a file-wide substring a regression could fool.
    assert (
        rrd._param_default("hermes_cli/github_publisher.py", "run", "approve") is False
    )
    assert (
        rrd._param_default("gateway/cockpit/server.py", "serve", "host") == "127.0.0.1"
    )
    assert (
        rrd._param_default("gateway/cockpit/server.py", "serve", "allow_external")
        is False
    )
    # absent function / parameter -> sentinel (gate would fail, not false-pass)
    assert (
        rrd._param_default("hermes_cli/github_publisher.py", "nope", "x")
        is rrd._MISSING
    )
    assert (
        rrd._param_default("hermes_cli/github_publisher.py", "run", "nope")
        is rrd._MISSING
    )
