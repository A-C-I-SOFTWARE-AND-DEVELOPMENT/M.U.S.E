"""Standard WorkPacket model for JARVIS Prime.

A WorkPacket is the canonical hand-off envelope between JARVIS Prime, the
AOS Council, and worker layers (Claude Code, Codex, local test runners).
The packet records what the work is, where it runs, what may and may not
change, how risk is classified, what acceptance looks like, what has
already been verified, and which actions are owner-gated.

Design constraints (Wave 0):

- Standard-library only. No pydantic, no third-party validation.
- No network access at import or at validation time.
- No imports of heavier Hermes subsystems at module import time.
- Termux-safe: no platform-specific imports at top level.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Iterable


VALID_RISK_CLASSES: frozenset[str] = frozenset({"RC0", "RC1", "RC2", "RC3", "RC4"})

OWNER_AUTHORIZATION_PHRASE: str = "Yes, with authorization."

REQUIRED_FIELDS: tuple[str, ...] = (
    "mission",
    "repo_root",
    "branch",
    "risk_class",
    "acceptance_criteria",
    "rollback_plan",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_confidence(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """A single validation finding on a WorkPacket.

    `field` is the dotted path to the offending value (e.g. "confidence" or
    "risk_class"). `code` is a short machine-readable token. `message` is a
    human-readable explanation.
    """

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass
class WorkPacket:
    """Canonical JARVIS Prime work packet."""

    mission: str = ""
    repo_root: str = ""
    branch: str = ""
    risk_class: str = ""
    allowed_files: list[str] = field(default_factory=list)
    protected_files: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    tests_failed: list[str] = field(default_factory=list)
    verification_summary: str = ""
    rollback_plan: str = ""
    owner_gated_actions: list[str] = field(default_factory=list)
    owner_authorization_phrase: str = OWNER_AUTHORIZATION_PHRASE
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = field(default_factory=_utcnow_iso)

    def __post_init__(self) -> None:
        self.confidence = _clamp_confidence(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict snapshot of the packet."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPacket":
        """Build a WorkPacket from a dict, ignoring unknown keys.

        Missing keys fall back to dataclass defaults. List fields receive a
        defensive copy so the caller's input is not aliased.
        """
        if not isinstance(data, dict):
            raise TypeError("WorkPacket.from_dict expects a dict")

        list_fields = {
            "allowed_files",
            "protected_files",
            "non_goals",
            "acceptance_criteria",
            "files_changed",
            "tests_run",
            "tests_failed",
            "owner_gated_actions",
            "citations",
        }
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs: dict[str, Any] = {}
        for key in known:
            if key not in data:
                continue
            value = data[key]
            if key in list_fields:
                kwargs[key] = list(value) if isinstance(value, Iterable) and not isinstance(value, (str, bytes)) else []
            else:
                kwargs[key] = value
        return cls(**kwargs)

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return validation findings; empty list means the packet is valid.

        Findings cover:
        - missing required scalar fields,
        - empty required list fields (acceptance_criteria),
        - invalid risk_class,
        - confidence outside [0.0, 1.0] before clamping (already clamped at
          construction, but a wildly out-of-range raw input is still worth
          flagging by checking type compatibility),
        - non-list values for list-typed fields.
        """
        findings: list[WorkPacketValidationFinding] = []

        for name in ("mission", "repo_root", "branch", "rollback_plan"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        code="missing_required",
                        message=f"{name} is required and must be a non-empty string",
                    )
                )

        if not isinstance(self.risk_class, str) or not self.risk_class.strip():
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="missing_required",
                    message="risk_class is required",
                )
            )
        elif self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="invalid_value",
                    message=(
                        f"risk_class must be one of {sorted(VALID_RISK_CLASSES)}; "
                        f"got {self.risk_class!r}"
                    ),
                )
            )

        if not isinstance(self.acceptance_criteria, list) or not self.acceptance_criteria:
            findings.append(
                WorkPacketValidationFinding(
                    field="acceptance_criteria",
                    code="missing_required",
                    message="acceptance_criteria is required and must contain at least one item",
                )
            )

        for name in (
            "allowed_files",
            "protected_files",
            "non_goals",
            "files_changed",
            "tests_run",
            "tests_failed",
            "owner_gated_actions",
            "citations",
        ):
            value = getattr(self, name)
            if not isinstance(value, list):
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        code="invalid_type",
                        message=f"{name} must be a list",
                    )
                )

        if not isinstance(self.confidence, (int, float)):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="invalid_type",
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        elif self.confidence < 0.0 or self.confidence > 1.0:
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="out_of_range",
                    message="confidence must be between 0.0 and 1.0",
                )
            )

        return findings

    def is_valid(self) -> bool:
        return not self.validate()


__all__ = [
    "WorkPacket",
    "WorkPacketValidationFinding",
    "VALID_RISK_CLASSES",
    "OWNER_AUTHORIZATION_PHRASE",
    "REQUIRED_FIELDS",
]
