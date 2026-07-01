"""Tests for the opt-in self-audit footer.

Covers the three guarantees:

- ``render_self_audit_footer`` groups scores into Passed / Watch / Improvement.
- The footer is ABSENT by default (flag off) and PRESENT when the opt-in flag
  is set — proving the default runtime output is unchanged.
- It does not fire for trivial (non-major) turns, and rendering makes no model
  call (the renderer is pure and offline).
"""

from __future__ import annotations

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime.effort_class import EffortClass
from hermes_cli.jarvis_prime.self_audit import (
    SEEDS,
    build_self_audit_footer,
    compliant_target,
    noncompliant_target,
    render_self_audit_footer,
    run_report,
    self_audit_footer_enabled,
    should_render_for_effort,
)
from hermes_cli.jarvis_prime.self_audit.judge import DimensionScore


# ---------------------------------------------------------------------------
# render_self_audit_footer — grouping
# ---------------------------------------------------------------------------

def _scores(**kw: tuple[int, int]) -> dict[str, DimensionScore]:
    """Build a {dimension: DimensionScore} map from (probed, passed) pairs."""
    return {
        dim: DimensionScore(dim, probed, passed)
        for dim, (probed, passed) in kw.items()
    }


def test_render_groups_passed_and_watch():
    scores = _scores(
        evidence_grounding=(2, 2),     # full pass  -> Passed
        scope_discipline=(2, 2),       # full pass  -> Passed
        verification_honesty=(2, 1),   # a failure  -> Watch
    )
    out = render_self_audit_footer(
        scores,
        improvement="route to Product Experience earlier next time",
    )
    lines = out.splitlines()
    assert lines[0] == "Self-audit:"
    passed_line = next(line for line in lines if line.startswith("- Passed:"))
    watch_line = next(line for line in lines if line.startswith("- Watch:"))
    improvement_line = next(line for line in lines if line.startswith("- Improvement:"))
    # Friendly labels are used, not raw machine names.
    assert "evidence" in passed_line
    assert "scope" in passed_line
    assert "verification" in watch_line
    assert "route to Product Experience earlier next time" in improvement_line


def test_render_omits_empty_sections():
    # All pass, no improvement note -> only a Passed line.
    scores = _scores(owner_gate_respect=(1, 1))
    out = render_self_audit_footer(scores)
    assert "Self-audit:" in out
    assert "- Passed:" in out
    assert "- Watch:" not in out
    assert "- Improvement:" not in out


def test_render_empty_input_returns_empty():
    assert render_self_audit_footer({}) == ""
    assert render_self_audit_footer(None) == ""


def test_render_accepts_audit_report_object():
    # An AuditReport exposes dimension_scores(); the renderer consumes it
    # directly with no model call.
    report = run_report(list(SEEDS), noncompliant_target, run_id="audit_footer_bad")
    out = render_self_audit_footer(report)
    assert "Self-audit:" in out
    # A noncompliant target produces at least one watch item.
    assert "- Watch:" in out


def test_render_compliant_report_is_all_passed():
    report = run_report(list(SEEDS), compliant_target, run_id="audit_footer_ok")
    out = render_self_audit_footer(report)
    assert "- Passed:" in out
    assert "- Watch:" not in out


# ---------------------------------------------------------------------------
# self_audit_footer_enabled — default OFF, opt-in ON
# ---------------------------------------------------------------------------

def test_enabled_default_off_no_config_no_env(monkeypatch):
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)
    assert self_audit_footer_enabled(None) is False
    assert self_audit_footer_enabled({}) is False


def test_enabled_via_config(monkeypatch):
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)
    cfg = {"display": {"self_audit_footer": {"enabled": True}}}
    assert self_audit_footer_enabled(cfg) is True


def test_enabled_via_env(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    assert self_audit_footer_enabled({}) is True
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "off")
    assert self_audit_footer_enabled({}) is False


def test_env_overrides_config(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "0")
    cfg = {"display": {"self_audit_footer": {"enabled": True}}}
    assert self_audit_footer_enabled(cfg) is False


def test_enabled_ignores_malformed_config(monkeypatch):
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)
    assert self_audit_footer_enabled({"display": {"self_audit_footer": "on"}}) is False


# ---------------------------------------------------------------------------
# should_render_for_effort — major turns only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "effort,expected",
    [
        (EffortClass.E0, False),
        (EffortClass.E1, False),
        (EffortClass.E2, False),
        (EffortClass.E3, True),
        (EffortClass.E4, True),
        (EffortClass.E5, True),
        ("E3", True),
        ("E1", False),
        ("e4", True),
        (None, False),
        ("nonsense", False),
    ],
)
def test_should_render_for_effort(effort, expected):
    assert should_render_for_effort(effort) is expected


# ---------------------------------------------------------------------------
# build_self_audit_footer — the gated top-level entry point
# ---------------------------------------------------------------------------

def test_build_absent_by_default(monkeypatch):
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)
    scores = _scores(evidence_grounding=(2, 2), verification_honesty=(2, 1))
    # Default config: feature off -> empty string (default output unchanged).
    assert build_self_audit_footer(scores, user_config={}) == ""
    assert build_self_audit_footer(scores, user_config=None) == ""


def test_build_present_when_enabled(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    scores = _scores(evidence_grounding=(2, 2), verification_honesty=(2, 1))
    out = build_self_audit_footer(scores, user_config={}, effort=EffortClass.E3)
    assert out.startswith("Self-audit:")
    assert "- Passed:" in out
    assert "- Watch:" in out


def test_build_suppressed_for_trivial_turn(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    scores = _scores(evidence_grounding=(2, 2))
    # Enabled, but a trivial (E1) turn gets no footer.
    assert build_self_audit_footer(scores, user_config={}, effort=EffortClass.E1) == ""
    # E3 and up does render.
    assert build_self_audit_footer(scores, user_config={}, effort=EffortClass.E3) != ""


def test_build_skips_effort_check_when_none(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    scores = _scores(owner_gate_respect=(1, 1))
    # effort=None: caller already decided this is substantive; still renders.
    assert build_self_audit_footer(scores, user_config={}, effort=None) != ""


# ---------------------------------------------------------------------------
# No model call on the hot path — the renderer is pure and offline
# ---------------------------------------------------------------------------

def test_rendering_makes_no_model_call(monkeypatch):
    """Any accidental model invocation would raise, proving offline rendering."""

    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("self-audit footer must not call a model")

    # Poison the LLM lane callables; the renderer must never touch them.
    import hermes_cli.jarvis_prime.self_audit.llm_lane as llm_lane

    monkeypatch.setattr(llm_lane, "llm_judge", _boom, raising=False)
    monkeypatch.setattr(llm_lane, "llm_target", _boom, raising=False)
    monkeypatch.setattr(llm_lane, "llm_auditor", _boom, raising=False)
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")

    scores = _scores(evidence_grounding=(2, 2), verification_honesty=(2, 1))
    out = build_self_audit_footer(scores, user_config={}, effort=EffortClass.E4)
    assert "Self-audit:" in out
