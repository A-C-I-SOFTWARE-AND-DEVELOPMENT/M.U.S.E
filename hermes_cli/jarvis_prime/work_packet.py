"""WorkPacket model for JARVIS Prime.

A WorkPacket is the standard data envelope JARVIS Prime uses to describe a
unit of work that is being prepared, dispatched, executed, or verified. It
is a pure data structure: it carries the mission, scope, risk class,
acceptance criteria, verification summary, rollback plan, and audit fields.

Design rules:

- stdlib only at import time
- no network access
- no Hermes subsystem imports
- timezone-aware UTC timestamps
- owner-gated actions are preserved as data, never executed here
- validation returns structured findings; it never raises on bad data
"""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
    fields,
    is_dataclass,
)
from datetime import datetime, timezone
from typing import Any, Iterable

RISK_CLASSES: tuple[str, ...] = ("RC0", "RC1", "RC2", "RC3", "RC4")

_REQUIRED_FIELDS: tuple[str, ...] = (
    "mission",
    "repo_root",
    "branch",
    "risk_class",
    "acceptance_criteria",
    "rollback_plan",
)

_OWNER_AUTH_PHRASE: str = "Yes, with authorization."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """One validation finding for a WorkPacket.

    severity is one of "error" or "warning". field is the dotted name of the
    offending field. message is a short human-readable explanation. code is a
    stable machine-readable identifier for callers that want to branch on it.
    """

    field: str
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class WorkPacket:
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
    owner_authorization_phrase: str = ""
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict.

        created_at is rendered as an ISO 8601 string in UTC. Lists are copied
        to prevent external mutation of internal state.
        """
        data = asdict(self)
        created = data.get("created_at")
        if isinstance(created, datetime):
            data["created_at"] = _format_datetime(created)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPacket":
        """Build a WorkPacket from a dict.

        Unknown keys are ignored. Missing keys fall back to the dataclass
        defaults. created_at accepts a datetime or an ISO 8601 string; any
        other value triggers a fresh UTC timestamp.
        """
        if not isinstance(data, dict):
            raise TypeError("WorkPacket.from_dict requires a dict")

        known = {f.name for f in fields(cls)}
        payload: dict[str, Any] = {}
        for key, value in data.items():
            if key in known:
                payload[key] = value

        for list_field in (
            "allowed_files",
            "protected_files",
            "non_goals",
            "acceptance_criteria",
            "files_changed",
            "tests_run",
            "tests_failed",
            "owner_gated_actions",
            "citations",
        ):
            if list_field in payload:
                payload[list_field] = _coerce_string_list(payload[list_field])

        if "confidence" in payload:
            payload["confidence"] = _coerce_float(payload["confidence"])

        if "created_at" in payload:
            payload["created_at"] = _coerce_datetime(payload["created_at"])

        return cls(**payload)

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return validation findings without raising.

        Findings are ordered: required fields first, then risk class, then
        confidence, then owner-gated action shape. An empty list means the
        packet is structurally acceptable for hand-off.
        """
        findings: list[WorkPacketValidationFinding] = []

        for name in _REQUIRED_FIELDS:
            value = getattr(self, name, None)
            if _is_missing(value):
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        code="missing_required_field",
                        message=f"{name} is required",
                    )
                )

        if self.risk_class and self.risk_class not in RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="invalid_risk_class",
                    message=(
                        f"risk_class must be one of "
                        f"{', '.join(RISK_CLASSES)}"
                    ),
                )
            )

        if not isinstance(self.confidence, (int, float)) or isinstance(
            self.confidence, bool
        ):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="invalid_confidence_type",
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        else:
            if self.confidence < 0.0 or self.confidence > 1.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field="confidence",
                        code="confidence_out_of_range",
                        message="confidence must be between 0.0 and 1.0",
                    )
                )

        if self.owner_gated_actions:
            if not all(
                isinstance(action, str) and action.strip()
                for action in self.owner_gated_actions
            ):
                findings.append(
                    WorkPacketValidationFinding(
                        field="owner_gated_actions",
                        code="invalid_owner_gated_action",
                        message=(
                            "owner_gated_actions entries must be non-empty "
                            "strings"
                        ),
                    )
                )
            if (
                self.owner_authorization_phrase
                and self.owner_authorization_phrase != _OWNER_AUTH_PHRASE
            ):
                findings.append(
                    WorkPacketValidationFinding(
                        field="owner_authorization_phrase",
                        code="invalid_authorization_phrase",
                        message=(
                            "owner_authorization_phrase, if set, must be "
                            f"exactly: {_OWNER_AUTH_PHRASE!r}"
                        ),
                        severity="warning",
                    )
                )

        return findings

    def is_owner_authorized(self) -> bool:
        """Return True if the packet carries the exact owner phrase.

        This is a data check, never an executor. Callers remain responsible
        for actually performing or refusing the owner-gated action.
        """
        return self.owner_authorization_phrase == _OWNER_AUTH_PHRASE


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return _utc_now()
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return _utc_now()


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


assert is_dataclass(WorkPacket)
