"""Living companion presence policy for JARVIS Prime.

The goal is to make Jarvis feel present without becoming deceptive or unsafe.
This module produces state and animation plans only. Actual Android overlay,
camera, microphone, or accessibility execution remains behind explicit user
permissions and owner gates in the Android client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PresenceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    WATCHING = "watching"
    THINKING = "thinking"
    WORKING = "working"
    MOVING_TO_TARGET = "moving_to_target"
    TAPPING_TARGET = "tapping_target"
    TURNING_PAGE = "turning_page"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    BLOCKED = "blocked"
    OFFLINE = "offline"
    EMERGENCY_STOP = "emergency_stop"


class ActionRisk(Enum):
    ANIMATION_ONLY = "animation_only"
    APP_LAUNCH = "app_launch"
    ACCESSIBILITY_GESTURE = "accessibility_gesture"
    OWNER_GATED = "owner_gated"


@dataclass(frozen=True)
class PresenceSignals:
    gateway_online: bool = True
    emergency_stop: bool = False
    microphone_active: bool = False
    camera_attention_opt_in: bool = False
    user_attention_confidence: float = 0.0
    speaking: bool = False
    thinking: bool = False
    working: bool = False
    target_app: Optional[str] = None
    target_on_next_screen: bool = False
    pending_owner_approval: bool = False
    blocked_reason: str = ""


@dataclass(frozen=True)
class AnimationStep:
    state: PresenceState
    label: str
    duration_ms: int = 600
    requires_real_action: bool = False


@dataclass(frozen=True)
class TaskAnimationPlan:
    mission: str
    risk: ActionRisk
    steps: tuple[AnimationStep, ...]
    owner_gate_required: bool
    privacy_notice: str
    execution_note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mission": self.mission,
            "risk": self.risk.value,
            "steps": [
                {
                    "state": step.state.value,
                    "label": step.label,
                    "duration_ms": step.duration_ms,
                    "requires_real_action": step.requires_real_action,
                }
                for step in self.steps
            ],
            "owner_gate_required": self.owner_gate_required,
            "privacy_notice": self.privacy_notice,
            "execution_note": self.execution_note,
        }


@dataclass
class CompanionPresencePolicy:
    attention_threshold: float = 0.72

    def state_for(self, signals: PresenceSignals) -> PresenceState:
        if signals.emergency_stop:
            return PresenceState.EMERGENCY_STOP
        if not signals.gateway_online:
            return PresenceState.OFFLINE
        if signals.blocked_reason:
            return PresenceState.BLOCKED
        if signals.pending_owner_approval:
            return PresenceState.WAITING_FOR_APPROVAL
        if signals.target_app:
            return PresenceState.TURNING_PAGE if signals.target_on_next_screen else PresenceState.MOVING_TO_TARGET
        if signals.working:
            return PresenceState.WORKING
        if signals.thinking:
            return PresenceState.THINKING
        if signals.microphone_active:
            return PresenceState.LISTENING
        if signals.camera_attention_opt_in and signals.user_attention_confidence >= self.attention_threshold:
            return PresenceState.WATCHING
        return PresenceState.IDLE

    def plan_task_animation(
        self,
        mission: str,
        *,
        target_app: Optional[str] = None,
        target_on_next_screen: bool = False,
        real_device_action_requested: bool = False,
    ) -> TaskAnimationPlan:
        steps: list[AnimationStep] = [
            AnimationStep(PresenceState.THINKING, "Jarvis reads the task and chooses a safe route."),
            AnimationStep(PresenceState.WORKING, "Jarvis prepares the action packet."),
        ]
        if target_app:
            if target_on_next_screen:
                steps.append(
                    AnimationStep(PresenceState.TURNING_PAGE, f"Jarvis turns to the screen with {target_app}.")
                )
            steps.append(
                AnimationStep(PresenceState.MOVING_TO_TARGET, f"Jarvis runs toward {target_app}.")
            )
            steps.append(
                AnimationStep(
                    PresenceState.TAPPING_TARGET,
                    f"Jarvis points at {target_app} and waits for permission.",
                    requires_real_action=real_device_action_requested,
                )
            )
        owner_gate = real_device_action_requested
        risk = ActionRisk.ACCESSIBILITY_GESTURE if real_device_action_requested else ActionRisk.ANIMATION_ONLY
        if owner_gate:
            steps.append(
                AnimationStep(
                    PresenceState.WAITING_FOR_APPROVAL,
                    "Owner approval required before any real tap or app control.",
                    duration_ms=900,
                    requires_real_action=True,
                )
            )
        return TaskAnimationPlan(
            mission=mission,
            risk=risk,
            steps=tuple(steps),
            owner_gate_required=owner_gate,
            privacy_notice=(
                "Attention detection is opt-in. Do not store camera frames, raw audio, "
                "or inferred emotional state as durable memory."
            ),
            execution_note=(
                "Animation is separate from real device control. Real control must go "
                "through Android permission education, AccessibilityService checks, and owner gates."
            ),
        )


def default_avatar_traits() -> dict[str, object]:
    """Defaults for customizable avatars without binding the UI to one style."""

    return {
        "scale_modes": ["full", "mini", "corner", "task_runner"],
        "expressions": ["idle", "listening", "focused", "working", "proud", "blocked"],
        "motion_style": "small_companion_fast_but_not_distracting",
        "customizable": True,
        "permission_posture": "opt_in_only",
    }
