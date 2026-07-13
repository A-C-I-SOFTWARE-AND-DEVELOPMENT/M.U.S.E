"""Tests for the living companion presence state machine."""

from __future__ import annotations

from hermes_cli.jarvis_prime.companion_presence import (
    ActionRisk,
    CompanionPresencePolicy,
    PresenceSignals,
    PresenceState,
    default_avatar_traits,
)


def test_attention_requires_opt_in_and_confidence_threshold() -> None:
    policy = CompanionPresencePolicy(attention_threshold=0.7)
    assert policy.state_for(PresenceSignals(user_attention_confidence=0.99)) is PresenceState.IDLE
    assert (
        policy.state_for(
            PresenceSignals(camera_attention_opt_in=True, user_attention_confidence=0.8)
        )
        is PresenceState.WATCHING
    )


def test_owner_gate_beats_working_state() -> None:
    policy = CompanionPresencePolicy()
    state = policy.state_for(PresenceSignals(working=True, pending_owner_approval=True))
    assert state is PresenceState.WAITING_FOR_APPROVAL


def test_facebook_tap_animation_is_separated_from_real_action() -> None:
    policy = CompanionPresencePolicy()
    plan = policy.plan_task_animation(
        "open Facebook",
        target_app="Facebook",
        target_on_next_screen=True,
        real_device_action_requested=True,
    )
    assert plan.risk is ActionRisk.ACCESSIBILITY_GESTURE
    assert plan.owner_gate_required is True
    assert any(step.requires_real_action for step in plan.steps)
    assert "Animation is separate" in plan.execution_note


def test_default_avatar_traits_are_customizable() -> None:
    traits = default_avatar_traits()
    assert traits["customizable"] is True
    assert "mini" in traits["scale_modes"]
