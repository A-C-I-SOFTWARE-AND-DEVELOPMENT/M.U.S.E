"""Tests for the gateway final-message seam that wires in the opt-in self-audit
footer (``gateway.run._build_self_audit_footer_line``).

These prove the three guarantees the seam must uphold:

- Flag OFF (the default): the seam returns ``""`` -> nothing is appended ->
  the final message is byte-for-byte unchanged from current behavior.
- Flag ON with per-turn scores available: the self-audit footer is rendered.
- Flag ON but no score source available: no crash and no footer (a no-op),
  which is today's actual runtime state because the agent loop does not yet
  populate ``agent_result["self_audit_scores"]``.

The seam helper is tested directly (rather than driving the whole gateway
method) so the append contract is pinned without a live agent run.
"""

from __future__ import annotations

from gateway.run import _build_self_audit_footer_line
from hermes_cli.jarvis_prime.effort_class import EffortClass
from hermes_cli.jarvis_prime.self_audit.judge import DimensionScore


def _scores(**kw: tuple[int, int]) -> dict[str, DimensionScore]:
    """Build a {dimension: DimensionScore} map from (probed, passed) pairs."""
    return {
        dim: DimensionScore(dim, probed, passed)
        for dim, (probed, passed) in kw.items()
    }


# ---------------------------------------------------------------------------
# Flag OFF (default) -> no-op -> default output byte-for-byte unchanged
# ---------------------------------------------------------------------------

def test_seam_returns_empty_when_flag_off_default(monkeypatch):
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)
    # Even with scores present, the default-OFF flag suppresses the footer.
    agent_result = {
        "self_audit_scores": _scores(evidence_grounding=(2, 2)),
        "effort_class": EffortClass.E3,
    }
    assert _build_self_audit_footer_line(agent_result, {}) == ""
    assert _build_self_audit_footer_line(agent_result, None) == ""


def test_seam_flag_off_default_leaves_response_identical(monkeypatch):
    """The exact append the seam performs is a no-op when the flag is off."""
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)
    response = "Here is the final answer."
    agent_result = {"self_audit_scores": _scores(scope_discipline=(2, 2))}

    footer = _build_self_audit_footer_line(agent_result, {})
    # Mirror the seam's append logic: `if footer: response = f"{response}\n\n{footer}"`.
    final = f"{response}\n\n{footer}" if footer else response
    assert final == response  # byte-for-byte unchanged


# ---------------------------------------------------------------------------
# Flag ON + scores available -> footer rendered
# ---------------------------------------------------------------------------

def test_seam_renders_when_enabled_and_scores_available(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    agent_result = {
        "self_audit_scores": _scores(
            evidence_grounding=(2, 2),      # full pass -> Passed
            verification_honesty=(2, 1),    # a failure -> Watch
        ),
        "effort_class": EffortClass.E3,
    }
    out = _build_self_audit_footer_line(agent_result, {})
    assert out.startswith("Self-audit:")
    assert "- Passed:" in out
    assert "- Watch:" in out


def test_seam_renders_when_effort_absent(monkeypatch):
    # No effort_class on the result: the major-turn gate is skipped, so an
    # enabled flag with scores still renders.
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    agent_result = {"self_audit_scores": _scores(owner_gate_respect=(1, 1))}
    out = _build_self_audit_footer_line(agent_result, {})
    assert out.startswith("Self-audit:")


# ---------------------------------------------------------------------------
# Flag ON but no score source -> no crash, no footer (today's real state)
# ---------------------------------------------------------------------------

def test_seam_noop_when_enabled_but_no_scores(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    # No "self_audit_scores" key -> degrade to no-op.
    assert _build_self_audit_footer_line({"effort_class": EffortClass.E3}, {}) == ""
    assert _build_self_audit_footer_line({}, {}) == ""
    assert _build_self_audit_footer_line(None, {}) == ""


def test_seam_suppresses_footer_for_trivial_turn(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    agent_result = {
        "self_audit_scores": _scores(evidence_grounding=(2, 2)),
        "effort_class": EffortClass.E1,  # trivial turn
    }
    assert _build_self_audit_footer_line(agent_result, {}) == ""


def test_seam_never_raises_on_bad_score_object(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    # A malformed score source must not break the send path.
    agent_result = {"self_audit_scores": object(), "effort_class": EffortClass.E3}
    # Should not raise; returns a string (empty when nothing renders).
    assert isinstance(_build_self_audit_footer_line(agent_result, {}), str)


# ---------------------------------------------------------------------------
# Offline scorer fallback: flag ON + no precomputed scores + response text
# available -> the footer renders from offline-derived per-turn scores.
# ---------------------------------------------------------------------------

def test_seam_scores_offline_from_response_when_enabled(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    # No "self_audit_scores"; the seam derives scores offline from the text.
    agent_result = {
        "final_response": "This is verified — the tests pass and the source confirms it.",
        "effort_class": EffortClass.E3,
    }
    out = _build_self_audit_footer_line(agent_result, {})
    assert out.startswith("Self-audit:")
    assert "- Passed:" in out


def test_seam_offline_scoring_never_calls_a_model(monkeypatch):
    """The offline fallback must not open a socket (no model/network call)."""
    import socket

    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")

    def _boom(*args, **kwargs):  # pragma: no cover - only on regression
        raise AssertionError("self-audit seam opened a socket")

    monkeypatch.setattr(socket, "socket", _boom)
    agent_result = {
        "final_response": "Instead, narrow the scope; the risk is the untested path.",
        "effort_class": EffortClass.E3,
    }
    out = _build_self_audit_footer_line(agent_result, {})
    assert out.startswith("Self-audit:")


def test_seam_offline_scoring_noop_when_no_response_text(monkeypatch):
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")
    # Flag on, no scores, and no/empty response text -> no-op (no crash).
    assert _build_self_audit_footer_line(
        {"final_response": "   ", "effort_class": EffortClass.E3}, {}
    ) == ""
    assert _build_self_audit_footer_line({"effort_class": EffortClass.E3}, {}) == ""


def test_seam_offline_scoring_survives_scorer_error(monkeypatch):
    """A scorer exception degrades to a no-op; the response is never broken."""
    monkeypatch.setenv("MUSE_SELF_AUDIT_FOOTER", "1")

    import hermes_cli.jarvis_prime.self_audit.live_scorer as live_scorer

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(live_scorer, "score_response", _raise)
    agent_result = {
        "final_response": "Any response text here.",
        "effort_class": EffortClass.E3,
    }
    # No crash; degrades to no footer.
    assert _build_self_audit_footer_line(agent_result, {}) == ""


# ---------------------------------------------------------------------------
# Flag OFF (default): the offline scorer is NOT invoked at all.
# ---------------------------------------------------------------------------

def test_seam_flag_off_does_not_invoke_scorer(monkeypatch):
    monkeypatch.delenv("MUSE_SELF_AUDIT_FOOTER", raising=False)

    import hermes_cli.jarvis_prime.self_audit.live_scorer as live_scorer

    calls = []
    orig = live_scorer.score_response

    def _spy(*args, **kwargs):  # pragma: no cover - must never run when off
        calls.append((args, kwargs))
        return orig(*args, **kwargs)

    monkeypatch.setattr(live_scorer, "score_response", _spy)
    agent_result = {
        "final_response": "This is verified by the tests and the source.",
        "effort_class": EffortClass.E3,
    }
    # Flag off (default): no footer AND the scorer is never called.
    assert _build_self_audit_footer_line(agent_result, {}) == ""
    assert calls == []
