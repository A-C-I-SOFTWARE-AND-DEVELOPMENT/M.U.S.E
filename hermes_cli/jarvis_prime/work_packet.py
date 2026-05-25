"""Standard JARVIS Prime WorkPacket.

A WorkPacket is the canonical, stdlib-only data envelope JARVIS Prime
uses to describe a unit of work before it is dispatched to a builder
(Claude Code) or reviewer (Codex), and before it is checked by the
eight verification gates from ``docs/jarvis-verification-gates.md``.

This module is import-time stdlib-only — no pydantic, no network, no
heavy Hermes subsystems. It loads cleanly in Termux and slim CI
images. Owner-gated actions are preserved as data; this module never
executes them.

Public API:

- ``RiskClass`` — RC0..RC4 enum (lower = lower blast radius).
- ``WorkPacket`` — the dataclass.
- ``WorkPacketValidationFinding`` — one validation issue.
- ``ValidationSeverity`` — info / warning / error.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Optional


class RiskClass(Enum):
    """Risk class bands from the JARVIS Prime spec.

    RC0 — trivial, fully reversible, local-only.
    RC1 — low risk, reversible.
    RC2 — medium risk, may touch shared runtime files.
    RC3 — high risk, owner-gated review recommended.
    RC4 — critical, owner-gated (deploys, DNS, secrets, public posts).
    """

    RC0 = "RC0"
    RC1 = "RC1"
    RC2 = "RC2"
    RC3 = "RC3"
    RC4 = "RC4"


VALID_RISK_CLASSES: frozenset[str] = frozenset(rc.value for rc in RiskClass)


class ValidationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """One structured validation finding for a WorkPacket field."""

    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkPacket:
    """A JARVIS Prime unit-of-work envelope.

    All collection fields default to empty so a partially-populated
    packet is still constructable; ``validate()`` reports the gaps.
    The dataclass does not enforce risk_class or confidence at
    construction time — enforcement is surfaced via ``validate()`` so
    callers can collect every issue in one pass instead of failing on
    the first.
    """

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
    owner_authorization_phrase: Optional[str] = None
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=_utc_now)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict representation.

        ``created_at`` is rendered as an ISO-8601 string with timezone.
        Owner-gated actions are preserved as data — they are never
        executed by this module.
        """

        data: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, datetime):
                data[f.name] = value.isoformat()
            elif isinstance(value, list):
                data[f.name] = list(value)
            else:
                data[f.name] = value
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkPacket":
        """Reconstruct a WorkPacket from ``to_dict()`` output.

        Unknown keys are ignored. Missing keys fall back to the
        dataclass defaults. ``created_at`` accepts ISO-8601 strings or
        ``datetime`` instances; naive datetimes are assumed UTC. Lists
        are shallow-copied. Non-numeric ``confidence`` falls back to
        0.0 — ``validate()`` will then surface it.
        """

        if not isinstance(data, Mapping):
            raise TypeError("WorkPacket.from_dict requires a mapping")

        known: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if f.name == "created_at":
                known[f.name] = _coerce_datetime(value)
            elif f.name == "confidence":
                known[f.name] = _coerce_float(value, default=0.0)
            elif f.name in {
                "allowed_files",
                "protected_files",
                "non_goals",
                "acceptance_criteria",
                "files_changed",
                "tests_run",
                "tests_failed",
                "owner_gated_actions",
                "citations",
            }:
                known[f.name] = _coerce_str_list(value)
            else:
                known[f.name] = value
        return cls(**known)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return all validation findings; empty list means the packet is OK.

        Findings cover:

        - missing required fields (mission, repo_root, branch,
          risk_class, acceptance_criteria, rollback_plan)
        - invalid risk_class (must be RC0..RC4)
        - confidence outside [0.0, 1.0]
        - confidence that is not a real number
        - owner_gated_actions present without an authorization phrase
          (reported as a warning — the dispatcher is expected to
          prompt the owner)
        """

        findings: list[WorkPacketValidationFinding] = []

        for required in (
            "mission",
            "repo_root",
            "branch",
            "risk_class",
            "acceptance_criteria",
            "rollback_plan",
        ):
            if not _has_value(getattr(self, required)):
                findings.append(
                    WorkPacketValidationFinding(
                        field=required,
                        message=f"required field {required!r} is missing or empty",
                    )
                )

        if self.risk_class and self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    message=(
                        f"invalid risk_class {self.risk_class!r}; "
                        f"expected one of {sorted(VALID_RISK_CLASSES)}"
                    ),
                )
            )

        if not _is_real_number(self.confidence):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    message=(
                        f"confidence must be a real number between 0.0 and 1.0; "
                        f"got {self.confidence!r}"
                    ),
                )
            )
        elif not 0.0 <= float(self.confidence) <= 1.0:
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    message=(
                        f"confidence must be between 0.0 and 1.0; "
                        f"got {self.confidence}"
                    ),
                )
            )

        if self.owner_gated_actions and not self.owner_authorization_phrase:
            findings.append(
                WorkPacketValidationFinding(
                    field="owner_authorization_phrase",
                    message=(
                        "owner_gated_actions present without an "
                        "owner_authorization_phrase; dispatcher must "
                        "request the exact phrase before execution"
                    ),
                    severity=ValidationSeverity.WARNING,
                )
            )

        return findings

    def missing_required_fields(self) -> list[str]:
        """Convenience helper: just the names of missing required fields."""

        return [
            f.field
            for f in self.validate()
            if f.severity == ValidationSeverity.ERROR
            and f.message.startswith("required field")
        ]

    def is_valid(self) -> bool:
        return not any(
            f.severity == ValidationSeverity.ERROR for f in self.validate()
        )


# ---------------------------------------------------------------------------
# Internal coercion helpers
# ---------------------------------------------------------------------------


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _is_real_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == value and value not in (float("inf"), float("-inf"))
    return False


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid ISO-8601 datetime: {value!r}") from exc
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    raise TypeError(f"created_at must be datetime or ISO-8601 string; got {type(value).__name__}")


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


__all__ = [
    "RiskClass",
    "VALID_RISK_CLASSES",
    "ValidationSeverity",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
