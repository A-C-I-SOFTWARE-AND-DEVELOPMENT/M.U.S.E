"""Integration tests for hermes_cli.jarvis_prime.runtime — JarvisPrime."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.modes import ClassifierContext, Mode
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime


@pytest.fixture
def jp(tmp_path: Path) -> JarvisPrime:
    config = JarvisConfig(memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"))
    return JarvisPrime(config=config)


def test_handle_returns_complete_turn(jp: JarvisPrime) -> None:
    turn = jp.handle("audit the repo for blockers", skip_perceive=True)
    assert turn.classification.mode == Mode.OPERATOR
    assert turn.route is not None
    assert turn.persona_prompt is not None
    assert turn.started_at <= turn.finished_at


def test_handle_explicit_mode_override(jp: JarvisPrime) -> None:
    ctx = ClassifierContext(explicit_mode=Mode.CRITIC)
    turn = jp.handle("any intent", context=ctx, skip_perceive=True)
    assert turn.classification.mode == Mode.CRITIC


def test_handle_recollection_injected_into_prompt(jp: JarvisPrime) -> None:
    jp.remember(
        "mission",
        "ship JARVIS Prime v1.0.0",
        durability="durable",
        confidence=0.95,
    )
    turn = jp.handle("ship the v1 release", skip_perceive=True)
    rendered = turn.persona_prompt.render()
    assert "RECOLLECTION" in rendered
    assert "JARVIS Prime" in rendered


def test_handle_triggers_research_for_unfamiliar_topic(jp: JarvisPrime) -> None:
    turn = jp.handle(
        "explain post-quantum cryptography in detail",
        skip_perceive=True,
    )
    assert turn.research_brief is not None
    assert turn.research_brief.triggered_by in (
        "no_recollection", "unfamiliar_topic", "low_confidence", "code_unknown",
    )


def test_handle_owner_pending_routes_to_owner_decision(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("package_publish", rationale="release")
    turn = jp.handle("ship the release", skip_perceive=True)
    assert turn.route.target.value == "owner_decision"
    assert turn.route.requires_owner_authorization is True


def test_authorize_clears_pending_action(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("production_deploy", rationale="hot fix")
    granted = jp.authorize("Yes, with authorization.")
    assert granted == ["production_deploy"]
    assert jp.config.owner_auth.pending_actions() == []


def test_authorize_rejects_loose_phrase(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("production_deploy", rationale="hot fix")
    assert jp.authorize("go for it") == []
    assert jp.config.owner_auth.pending_actions() == ["production_deploy"]


def test_audit_calibrated_response_passes(jp: JarvisPrime) -> None:
    report = jp.audit("I'm not certain — let me check the repo first.", confidence=0.9)
    assert report.outcome.value == "pass"


def test_audit_low_confidence_demands_research(jp: JarvisPrime) -> None:
    report = jp.audit("definite claim with no hedge", confidence=0.2)
    assert report.outcome.value == "needs_research"


def test_render_handoff_includes_canonical_lines(jp: JarvisPrime) -> None:
    turn = jp.handle("audit repo", skip_perceive=True)
    handoff = jp.render_handoff(turn, result="done", next_step="open PR")
    for label in (
        "Mission:", "Route selected:", "Actions taken:",
        "Verification:", "Owner gates:", "Result:", "Next step:",
    ):
        assert label in handoff


def test_perceive_returns_snapshot(jp: JarvisPrime) -> None:
    snap = jp.perceive(timeout=1.0)
    # Don't assert specific contents — just that the snapshot is well-formed.
    assert snap.timestamp is not None
    assert isinstance(snap.summary(), str)
