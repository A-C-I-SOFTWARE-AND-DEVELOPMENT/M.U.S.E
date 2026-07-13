"""Natural-language coding router for JARVIS Prime.

Converts plain English requests into bounded implementation packets that keep
Hermes safe: localize first, branch scope first, tests or explicit skip reason,
reviewer separated from builder, and owner-gated actions isolated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class CodingIntent(Enum):
    RESEARCH = "research"
    LOCALIZE = "localize"
    IMPLEMENT = "implement"
    REVIEW = "review"
    TEST = "test"
    DOCUMENT = "document"
    DEVICE_ACTION = "device_action"
    AVATAR_PRESENCE = "avatar_presence"


@dataclass(frozen=True)
class CodingRoute:
    intent: CodingIntent
    risk_class: str
    primary_worker: str
    reviewer_worker: str
    requires_localization: bool
    requires_owner_approval: bool
    rationale: str


@dataclass(frozen=True)
class CodingWorkPacket:
    mission: str
    intent: CodingIntent
    repo_root: str
    branch: str
    risk_class: str
    allowed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    verification_plan: tuple[str, ...]
    rollback_plan: str
    primary_worker: str
    reviewer_worker: str
    owner_gated_actions: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "mission": self.mission,
            "intent": self.intent.value,
            "repo_root": self.repo_root,
            "branch": self.branch,
            "risk_class": self.risk_class,
            "allowed_files": list(self.allowed_files),
            "forbidden_files": list(self.forbidden_files),
            "acceptance_criteria": list(self.acceptance_criteria),
            "verification_plan": list(self.verification_plan),
            "rollback_plan": self.rollback_plan,
            "primary_worker": self.primary_worker,
            "reviewer_worker": self.reviewer_worker,
            "owner_gated_actions": list(self.owner_gated_actions),
            "notes": list(self.notes),
        }


def classify_coding_request(prompt: str) -> CodingRoute:
    text = prompt.lower()
    owner_gated = _has_any(
        text,
        (
            "merge",
            "deploy",
            "publish",
            "oauth",
            "credential",
            "token",
            "delete",
            "wipe",
            "factory reset",
            "post publicly",
            "buy",
            "spend",
        ),
    )
    if _has_any(text, ("avatar", "mini version", "floating", "on screen", "living")):
        return CodingRoute(
            intent=CodingIntent.AVATAR_PRESENCE,
            risk_class="RC3" if _has_any(text, ("overlay", "click", "tap", "accessibility")) else "RC2",
            primary_worker="claude-code-windows",
            reviewer_worker="codex",
            requires_localization=True,
            requires_owner_approval=True,
            rationale="Avatar presence touches privacy, permissions, and user trust.",
        )
    if _has_any(text, ("facebook", "click", "tap", "open app", "control phone", "screen")):
        return CodingRoute(
            intent=CodingIntent.DEVICE_ACTION,
            risk_class="RC3",
            primary_worker="claude-code-windows",
            reviewer_worker="codex",
            requires_localization=True,
            requires_owner_approval=True,
            rationale="Device control requires accessibility/overlay gates and explicit owner approval.",
        )
    if _has_any(text, ("audit", "research", "compare", "deep search")):
        return CodingRoute(
            intent=CodingIntent.RESEARCH,
            risk_class="RC1",
            primary_worker="hermes-local",
            reviewer_worker="codex",
            requires_localization=False,
            requires_owner_approval=False,
            rationale="Research can run read-only and produce a cited dossier.",
        )
    if _has_any(text, ("review", "critique", "inspect")):
        return CodingRoute(
            intent=CodingIntent.REVIEW,
            risk_class="RC1",
            primary_worker="codex",
            reviewer_worker="hermes-local",
            requires_localization=True,
            requires_owner_approval=False,
            rationale="Independent review should be read-only unless a fix packet is approved.",
        )
    if _has_any(text, ("test", "verify", "failing")):
        return CodingRoute(
            intent=CodingIntent.TEST,
            risk_class="RC1",
            primary_worker="hermes-local",
            reviewer_worker="codex",
            requires_localization=True,
            requires_owner_approval=False,
            rationale="Verification is low-risk but must capture exact commands and results.",
        )
    if _has_any(text, ("doc", "readme", "guide", "explain")):
        return CodingRoute(
            intent=CodingIntent.DOCUMENT,
            risk_class="RC1",
            primary_worker="claude-code-windows",
            reviewer_worker="codex",
            requires_localization=True,
            requires_owner_approval=False,
            rationale="Documentation edits are safe when scoped and cited.",
        )
    return CodingRoute(
        intent=CodingIntent.IMPLEMENT,
        risk_class="RC2" if owner_gated else "RC1",
        primary_worker="claude-code-windows",
        reviewer_worker="codex",
        requires_localization=True,
        requires_owner_approval=owner_gated,
        rationale="Default coding route: localize, implement on a branch, verify, review.",
    )


def build_work_packet(
    prompt: str,
    *,
    repo_root: str = ".",
    branch_prefix: str = "jarvis",
    allowed_files: Iterable[str] = (),
) -> CodingWorkPacket:
    route = classify_coding_request(prompt)
    branch = f"{branch_prefix}/{_slug(prompt)}"
    allowed = tuple(allowed_files) or _default_allowed_files(route.intent)
    forbidden = (
        ".env",
        ".env.*",
        "**/*secret*",
        "**/*credential*",
        "**/build/**",
        "**/.gradle/**",
        "**/__pycache__/**",
    )
    criteria = _acceptance_for(route.intent)
    verification = _verification_for(route.intent)
    gated = ("owner_approval",) if route.requires_owner_approval else ()
    notes = (
        "No serious code edit without localization first.",
        "Claude Code is the primary builder; Codex is independent reviewer/bounded fixer.",
        "Do not merge, deploy, publish, create accounts, or change credentials without exact owner authorization.",
    )
    return CodingWorkPacket(
        mission=prompt.strip(),
        intent=route.intent,
        repo_root=repo_root,
        branch=branch,
        risk_class=route.risk_class,
        allowed_files=allowed,
        forbidden_files=forbidden,
        acceptance_criteria=criteria,
        verification_plan=verification,
        rollback_plan="Revert the branch or remove the files listed in files_changed; do not touch main.",
        primary_worker=route.primary_worker,
        reviewer_worker=route.reviewer_worker,
        owner_gated_actions=gated,
        notes=notes,
    )


def _default_allowed_files(intent: CodingIntent) -> tuple[str, ...]:
    if intent == CodingIntent.AVATAR_PRESENCE:
        return (
            "apps/android/**",
            "docs/jarvis_architecture/**",
            "docs/implementation-packets/**",
            "hermes_cli/jarvis_prime/companion_presence.py",
            "tests/test_jarvis_prime_companion_presence.py",
        )
    if intent == CodingIntent.DEVICE_ACTION:
        return (
            "apps/android/**",
            "docs/implementation-packets/**",
            "hermes_cli/jarvis_prime/companion_presence.py",
        )
    if intent == CodingIntent.RESEARCH:
        return ("docs/jarvis_research/**",)
    return ("hermes_cli/**", "tests/**", "docs/**")


def _acceptance_for(intent: CodingIntent) -> tuple[str, ...]:
    common = (
        "Files changed stay inside allowed_files.",
        "Every claim has source/provenance or is marked as an assumption.",
        "Tests run or a clear skip reason is recorded.",
    )
    if intent == CodingIntent.AVATAR_PRESENCE:
        return common + (
            "Avatar presence is opt-in and permission-educated.",
            "No background camera, microphone, overlay, or accessibility action runs without owner approval.",
            "Animation is separated from actual device control so it can never spoof an action.",
        )
    if intent == CodingIntent.DEVICE_ACTION:
        return common + (
            "Device action uses Accessibility APIs only after explicit enablement and confirmation.",
            "Every tap/gesture is previewed with target app, target node, and rollback/stop path.",
        )
    return common


def _verification_for(intent: CodingIntent) -> tuple[str, ...]:
    if intent in (CodingIntent.AVATAR_PRESENCE, CodingIntent.DEVICE_ACTION):
        return (
            "Run focused Python/JARVIS tests.",
            "Run Android unit tests for permission invariants when Android toolchain is available.",
            "Manual privacy review: overlay, camera, microphone, accessibility, notifications.",
        )
    return ("Run focused tests for touched modules.", "Run lint/typecheck when environment allows.")


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:8]
    return "-".join(words) or "task"


def _has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)
