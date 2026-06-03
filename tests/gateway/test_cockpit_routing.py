"""Tests for JARVIS's brain-switching hint + reference grounding."""

from __future__ import annotations

from types import SimpleNamespace

from gateway.cockpit import grounding
from gateway.cockpit.agent import _brain_hint


def _turn(*, mode="companion", target="direct_answer", confidence=0.9, research=False):
    return SimpleNamespace(
        classification=SimpleNamespace(confidence=confidence),
        route=SimpleNamespace(target=SimpleNamespace(value=target)),
        research_brief=object() if research else None,
    )


def test_hint_code_for_builder_mode() -> None:
    h = _brain_hint(_turn(mode="builder"), "builder")
    assert h["kind"] == "code"


def test_hint_code_for_codex_target() -> None:
    h = _brain_hint(_turn(target="codex_bounded_fix"), "operator")
    assert h["kind"] == "code"


def test_hint_reasoning_and_escalate_on_low_confidence() -> None:
    h = _brain_hint(_turn(confidence=0.3), "companion")
    assert h["kind"] == "reasoning"
    assert h["escalate"] is True


def test_hint_escalates_on_research_brief() -> None:
    h = _brain_hint(_turn(research=True), "companion")
    assert h["escalate"] is True


def test_hint_escalates_on_council() -> None:
    h = _brain_hint(_turn(target="aos_council"), "strategy")
    assert h["escalate"] is True


def test_hint_plain_chat_stays_local_kind() -> None:
    h = _brain_hint(_turn(mode="companion", confidence=0.95), "companion")
    assert h == {
        "kind": "chat",
        "escalate": False,
        "target": "direct_answer",
        "mode": "companion",
        "task_class": "mobile_chat",
    }


def test_maybe_remember_only_on_explicit_cue() -> None:
    from gateway.cockpit.agent import _maybe_remember

    stored: list[tuple] = []

    class _Mem:
        def remember(self, *, key, value, durability, confidence):
            stored.append((key, value, durability))
            return object()  # accepted

    jp = SimpleNamespace(config=SimpleNamespace(memory=_Mem()))
    # no cue → nothing stored, no note
    assert _maybe_remember(jp, "what's the weather?") == ""
    assert stored == []
    # explicit cue → stored durably + note returned
    assert _maybe_remember(jp, "remember I prefer dark mode") == "Noted to memory."
    assert stored and stored[0][2] == "durable"


def test_maybe_remember_honest_when_rejected() -> None:
    from gateway.cockpit.agent import _maybe_remember

    class _Mem:
        def remember(self, **kw):
            return None  # rejected (e.g. secret / below floor)

    jp = SimpleNamespace(config=SimpleNamespace(memory=_Mem()))
    assert _maybe_remember(jp, "remember my api_key=sk-secret") == ""  # no false "noted"


def test_epistemic_caveat_flags_non_pass() -> None:
    from gateway.cockpit.agent import _epistemic_caveat

    turn = _turn()

    class _JpFail:
        def audit(self, text, confidence=1.0):
            return SimpleNamespace(outcome=SimpleNamespace(value="needs_citations"))

    class _JpPass:
        def audit(self, text, confidence=1.0):
            return SimpleNamespace(outcome=SimpleNamespace(value="pass"))

    assert "needs citations" in _epistemic_caveat(_JpFail(), turn, "some risky claim")
    assert _epistemic_caveat(_JpPass(), turn, "a hedged, cited reply") == ""


def test_pacing_directive_is_brief_for_backchannel() -> None:
    from gateway.cockpit.agent import _pacing_directive

    # A bare acknowledgement → BRIEF / backchannel: one beat, hand back the floor.
    out = _pacing_directive("right")
    assert "cadence" in out.lower()
    assert "brief" in out.lower()
    assert "stop-go" in out.lower()


def test_pacing_directive_allows_depth_on_substantive_prompt() -> None:
    from gateway.cockpit.agent import _pacing_directive

    out = _pacing_directive(
        "Walk me through the full architecture of the orchestration system and "
        "how navigation, dispatch, and the decision ledger fit together in detail."
    )
    # Substantive ask → not clamped to BRIEF; mentions natural cadence either way.
    assert "cadence" in out.lower()
    assert out  # non-empty directive produced


def test_reference_context_indexes_repo_docs() -> None:
    # Against the real repo root, the grounding block should list known docs.
    block = grounding.reference_context()
    assert "Reference material" in block
    assert "AGENTS.md" in block or "CLAUDE.md" in block


def test_reference_context_bounded_and_safe(tmp_path) -> None:
    # Empty dir → no reference material, never raises.
    assert grounding.reference_context(str(tmp_path)) == ""
