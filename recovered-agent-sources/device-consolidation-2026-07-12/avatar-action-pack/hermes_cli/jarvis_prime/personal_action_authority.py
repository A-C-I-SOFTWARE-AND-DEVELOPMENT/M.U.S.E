"""Owner-authorized personal action authority for JARVIS Prime.

This module converts Jeremiah's standing authorization into a precise runtime
contract. It does not try to bypass Android permissions. Instead, it records
that the owner has authorized personal-use automation while still separating:

- owner authorization: Jeremiah wants JARVIS to act on his device;
- OS capability grants: Android overlay/accessibility/screen-capture settings;
- action risk: reversible navigation vs. destructive/financial/public actions;
- avatar choreography: what the living avatar should visibly do while working.

The goal is not to make the agent timid. The goal is to make it dependable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


class Capability(str, Enum):
    """Android-side capabilities the companion may need."""

    OVERLAY = "overlay"
    ACCESSIBILITY = "accessibility"
    MEDIA_PROJECTION = "media_projection"
    CAMERA_ATTENTION = "camera_attention"
    MICROPHONE_WAKE = "microphone_wake"
    PACKAGE_VISIBILITY = "package_visibility"
    NOTIFICATIONS = "notifications"


class CapabilityStatus(str, Enum):
    UNKNOWN = "unknown"
    GRANTED = "granted"
    DENIED = "denied"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


class ActionRisk(str, Enum):
    NAVIGATION = "navigation"
    INPUT = "input"
    EXTERNAL_COMMUNICATION = "external_communication"
    MONEY_OR_PURCHASE = "money_or_purchase"
    ACCOUNT_OR_SECURITY = "account_or_security"
    DESTRUCTIVE = "destructive"


class ExecutionMode(str, Enum):
    """How the action broker should behave for this request."""

    ANIMATE_ONLY = "animate_only"
    DIRECT_EXECUTE = "direct_execute"
    EXECUTE_WITH_PAUSE_POINT = "execute_with_pause_point"
    BLOCKED_MISSING_CAPABILITY = "blocked_missing_capability"
    EMERGENCY_STOPPED = "emergency_stopped"


@dataclass(frozen=True)
class PersonalUseAuthorization:
    """Standing authorization profile for a private local build."""

    owner_name: str = "Jeremiah Echerd"
    personal_use_only: bool = True
    developer_mode: bool = True
    standing_authorization: bool = True
    allow_cross_app_navigation: bool = True
    allow_gesture_execution: bool = True
    allow_overlay_avatar: bool = True
    allow_attention_sensing: bool = True
    pause_for_external_send: bool = True
    pause_for_money_security_or_destructive: bool = True


@dataclass(frozen=True)
class CapabilityGrant:
    capability: Capability
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    note: str = ""


@dataclass(frozen=True)
class VisualBeat:
    name: str
    description: str
    duration_ms: int = 350


@dataclass(frozen=True)
class PersonalActionContract:
    """Serializable action contract for the Android companion broker."""

    request: str
    target_app_label: str
    target_package: Optional[str]
    risk: ActionRisk
    execution_mode: ExecutionMode
    required_capabilities: tuple[Capability, ...]
    missing_capabilities: tuple[Capability, ...]
    visual_beats: tuple[VisualBeat, ...]
    rationale: str
    owner_authorized: bool
    pause_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "request": self.request,
            "target_app_label": self.target_app_label,
            "target_package": self.target_package,
            "risk": self.risk.value,
            "execution_mode": self.execution_mode.value,
            "required_capabilities": [c.value for c in self.required_capabilities],
            "missing_capabilities": [c.value for c in self.missing_capabilities],
            "visual_beats": [beat.__dict__ for beat in self.visual_beats],
            "rationale": self.rationale,
            "owner_authorized": self.owner_authorized,
            "pause_reason": self.pause_reason,
        }


DEFAULT_GRANTS: tuple[CapabilityGrant, ...] = tuple(
    CapabilityGrant(capability=c, status=CapabilityStatus.UNKNOWN)
    for c in Capability
)


def _status_map(grants: Iterable[CapabilityGrant]) -> dict[Capability, CapabilityStatus]:
    return {g.capability: g.status for g in grants}


def classify_action_risk(request: str) -> ActionRisk:
    """Small deterministic risk classifier for personal-device actions."""

    text = request.lower()
    destructive_terms = ("delete", "wipe", "factory reset", "uninstall", "remove account")
    money_terms = ("buy", "purchase", "pay", "send money", "checkout", "subscribe")
    security_terms = ("password", "2fa", "oauth", "login", "bank", "security", "permission")
    comm_terms = ("post", "send", "email", "message", "dm", "publish", "comment")
    input_terms = ("type", "fill", "enter", "submit", "tap", "click")

    if any(term in text for term in destructive_terms):
        return ActionRisk.DESTRUCTIVE
    if any(term in text for term in money_terms):
        return ActionRisk.MONEY_OR_PURCHASE
    if any(term in text for term in security_terms):
        return ActionRisk.ACCOUNT_OR_SECURITY
    if any(term in text for term in comm_terms):
        return ActionRisk.EXTERNAL_COMMUNICATION
    if any(term in text for term in input_terms):
        return ActionRisk.INPUT
    return ActionRisk.NAVIGATION


def required_capabilities_for(
    risk: ActionRisk,
    *,
    needs_cross_app: bool = True,
    needs_visual_location: bool = True,
    needs_attention: bool = False,
) -> tuple[Capability, ...]:
    caps: list[Capability] = []
    if needs_cross_app:
        caps.extend([Capability.PACKAGE_VISIBILITY, Capability.OVERLAY, Capability.ACCESSIBILITY])
    if needs_visual_location:
        # Accessibility node content comes first; media projection is optional fallback for
        # visual grounding when app nodes are not descriptive enough.
        if Capability.ACCESSIBILITY not in caps:
            caps.append(Capability.ACCESSIBILITY)
    if needs_attention:
        caps.append(Capability.CAMERA_ATTENTION)
    return tuple(dict.fromkeys(caps))


def avatar_beats_for_request(request: str, target_app_label: str) -> tuple[VisualBeat, ...]:
    """Create the mini-avatar animation beats for a task."""

    text = request.lower()
    beats = [
        VisualBeat("acknowledge", "Mini JARVIS looks at Jeremiah and nods."),
        VisualBeat("think", "Mini JARVIS compresses the task into a small work card."),
        VisualBeat("move_to_target", f"Mini JARVIS runs toward {target_app_label}."),
    ]
    if any(term in text for term in ("next screen", "next page", "swipe", "scroll")):
        beats.append(VisualBeat("turn_page", "Mini JARVIS grabs the screen edge and turns the page."))
    beats.extend(
        [
            VisualBeat("point", f"Mini JARVIS points at the {target_app_label} target."),
            VisualBeat("tap", "Mini JARVIS performs the visible tap animation at the same coordinate as the broker gesture."),
            VisualBeat("report", "Mini JARVIS returns to the corner and reports what happened."),
        ]
    )
    return tuple(beats)


def build_personal_action_contract(
    request: str,
    *,
    target_app_label: str = "target app",
    target_package: Optional[str] = None,
    authorization: PersonalUseAuthorization = PersonalUseAuthorization(),
    grants: Iterable[CapabilityGrant] = DEFAULT_GRANTS,
    emergency_stopped: bool = False,
    needs_attention: bool = False,
) -> PersonalActionContract:
    """Build a contract for Android to animate and optionally execute."""

    risk = classify_action_risk(request)
    required = required_capabilities_for(risk, needs_attention=needs_attention)
    statuses = _status_map(grants)
    missing = tuple(
        cap for cap in required if statuses.get(cap, CapabilityStatus.UNKNOWN) != CapabilityStatus.GRANTED
    )
    beats = avatar_beats_for_request(request, target_app_label)

    if emergency_stopped:
        return PersonalActionContract(
            request=request,
            target_app_label=target_app_label,
            target_package=target_package,
            risk=risk,
            execution_mode=ExecutionMode.EMERGENCY_STOPPED,
            required_capabilities=required,
            missing_capabilities=missing,
            visual_beats=beats,
            rationale="Emergency stop is active.",
            owner_authorized=authorization.standing_authorization,
        )

    if not authorization.standing_authorization:
        return PersonalActionContract(
            request=request,
            target_app_label=target_app_label,
            target_package=target_package,
            risk=risk,
            execution_mode=ExecutionMode.ANIMATE_ONLY,
            required_capabilities=required,
            missing_capabilities=missing,
            visual_beats=beats,
            rationale="Standing owner authorization is disabled; avatar can preview only.",
            owner_authorized=False,
        )

    if missing:
        return PersonalActionContract(
            request=request,
            target_app_label=target_app_label,
            target_package=target_package,
            risk=risk,
            execution_mode=ExecutionMode.BLOCKED_MISSING_CAPABILITY,
            required_capabilities=required,
            missing_capabilities=missing,
            visual_beats=beats,
            rationale="Owner has authorized the feature, but Android capability grants are missing.",
            owner_authorized=True,
        )

    pause = ""
    if risk == ActionRisk.EXTERNAL_COMMUNICATION and authorization.pause_for_external_send:
        pause = "pause before final send/post/publish gesture"
    if risk in {ActionRisk.MONEY_OR_PURCHASE, ActionRisk.ACCOUNT_OR_SECURITY, ActionRisk.DESTRUCTIVE} and authorization.pause_for_money_security_or_destructive:
        pause = "pause before money/security/destructive final gesture"

    return PersonalActionContract(
        request=request,
        target_app_label=target_app_label,
        target_package=target_package,
        risk=risk,
        execution_mode=ExecutionMode.EXECUTE_WITH_PAUSE_POINT if pause else ExecutionMode.DIRECT_EXECUTE,
        required_capabilities=required,
        missing_capabilities=(),
        visual_beats=beats,
        rationale="Standing personal-use authorization is active and required Android capabilities are granted.",
        owner_authorized=True,
        pause_reason=pause,
    )
