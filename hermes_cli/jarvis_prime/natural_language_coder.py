"""Minimal natural-language coding packetizer for JARVIS Prime.

Turns a plain-English request into a bounded work packet. It does not execute
anything; it only describes scope, verification, reviewer separation, and owner
gates for downstream workers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CodingIntent(Enum):
    RESEARCH = "research"
    IMPLEMENT = "implement"
    REVIEW = "review"
    TEST = "test"
    DOCUMENT = "document"
    DEVICE_ACTION = "device_action"
    AVATAR_PRESENCE = "avatar_presence"


@dataclass(frozen=True)
class CodingWorkPacket:
    mission: str
    intent: CodingIntent
    branch: str
    risk_class: str
    allowed_files: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    verification_plan: tuple[str, ...]
    primary_worker: str = "claude-code-windows"
    reviewer_worker: str = "codex"
    owner_gated_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "mission": self.mission,
            "intent": self.intent.value,
            "branch": self.branch,
            "risk_class": self.risk_class,
            "allowed_files": list(self.allowed_files),
            "acceptance_criteria": list(self.acceptance_criteria),
            "verification_plan": list(self.verification_plan),
            "primary_worker": self.primary_worker,
            "reviewer_worker": self.reviewer_worker,
            "owner_gated_actions": list(self.owner_gated_actions),
        }


def build_work_packet(prompt: str, *, branch_prefix: str = "jarvis") -> CodingWorkPacket:
    intent = classify_intent(prompt)
    gated = requires_owner_gate(prompt, intent)
    return CodingWorkPacket(
        mission=prompt.strip(),
        intent=intent,
        branch=f"{branch_prefix}/{_slug(prompt)}",
        risk_class="RC3" if gated else "RC1",
        allowed_files=allowed_files_for(intent),
        acceptance_criteria=acceptance_for(intent),
        verification_plan=verification_for(intent),
        owner_gated_actions=("owner_approval",) if gated else (),
    )


def classify_intent(prompt: str) -> CodingIntent:
    text = prompt.lower()
    if any(word in text for word in ("avatar", "floating", "mini version", "living")):
        return CodingIntent.AVATAR_PRESENCE
    if any(word in text for word in ("tap", "click", "open app", "control phone", "facebook")):
        return CodingIntent.DEVICE_ACTION
    if any(word in text for word in ("audit", "research", "compare", "deep search")):
        return CodingIntent.RESEARCH
    if any(word in text for word in ("review", "critique", "inspect")):
        return CodingIntent.REVIEW
    if any(word in text for word in ("test", "verify", "failing")):
        return CodingIntent.TEST
    if any(word in text for word in ("doc", "readme", "guide", "explain")):
        return CodingIntent.DOCUMENT
    return CodingIntent.IMPLEMENT


def requires_owner_gate(prompt: str, intent: CodingIntent) -> bool:
    text = prompt.lower()
    if intent in (CodingIntent.DEVICE_ACTION, CodingIntent.AVATAR_PRESENCE):
        return True
    return any(word in text for word in ("merge", "deploy", "publish", "oauth", "spend", "delete"))


def allowed_files_for(intent: CodingIntent) -> tuple[str, ...]:
    if intent == CodingIntent.AVATAR_PRESENCE:
        return (
            "apps/android/**",
            "hermes_cli/jarvis_prime/companion_presence.py",
            "tests/test_jarvis_prime_companion_presence.py",
            "docs/jarvis_architecture/**",
        )
    if intent == CodingIntent.DEVICE_ACTION:
        return ("apps/android/**", "docs/implementation-packets/**")
    if intent == CodingIntent.RESEARCH:
        return ("docs/jarvis_research/**",)
    return ("hermes_cli/**", "tests/**", "docs/**")


def acceptance_for(intent: CodingIntent) -> tuple[str, ...]:
    base = (
        "changes stay inside allowed files",
        "builder and reviewer are separate workers",
        "tests run or skip reason is recorded",
    )
    if intent in (CodingIntent.AVATAR_PRESENCE, CodingIntent.DEVICE_ACTION):
        return base + ("real device actions stay behind explicit owner gates",)
    return base


def verification_for(intent: CodingIntent) -> tuple[str, ...]:
    if intent in (CodingIntent.AVATAR_PRESENCE, CodingIntent.DEVICE_ACTION):
        return (
            "run focused JARVIS tests",
            "run Android unit tests when Android toolchain is available",
            "review privacy and permission boundaries",
        )
    return ("run focused tests for touched modules",)


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:8]
    return "-".join(words) or "task"
