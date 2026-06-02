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
    }


def test_reference_context_indexes_repo_docs() -> None:
    # Against the real repo root, the grounding block should list known docs.
    block = grounding.reference_context()
    assert "Reference material" in block
    assert "AGENTS.md" in block or "CLAUDE.md" in block


def test_reference_context_bounded_and_safe(tmp_path) -> None:
    # Empty dir → no reference material, never raises.
    assert grounding.reference_context(str(tmp_path)) == ""
