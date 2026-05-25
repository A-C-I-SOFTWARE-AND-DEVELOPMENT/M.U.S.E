"""Standard JARVIS Prime WorkPacket — Wave 0 foundation model.

A WorkPacket is the canonical handoff envelope for any JARVIS Prime
unit of work routed to Claude Code, Codex, a worker, or returned as a
specialist plan. It is data-only: it records intent, scope, risk,
acceptance criteria, verification evidence, owner gates, and rollback.
It never executes.

Design constraints (mission Wave 0):

- stdlib-only at import time. No pydantic, no network, no Hermes
  subsystems pulled in eagerly.
- Termux-friendly (Python 3.11+, no platform-specific deps).
- Compatible with the eight gates in ``gates.py`` — the field names
  match what ``planning_gate``, ``build_gate``, etc. expect, so a
  WorkPacket can be passed straight to ``run_gate_summary``.
- Owner-gated actions are preserved as data, never executed.

Risk classes match the convention used elsewhere in JARVIS Prime
(see ``owner_auth.py``): RC0..RC4.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Optional


VALID_RISK_CLASSES: frozenset[str] = frozenset({"RC0", "RC1", "RC2", "RC3", "RC4"})


_REQUIRED_FIELDS: tuple[str, ...] = (
    "mission",
    "repo_root",
    "branch",
    "risk_class",
    "acceptance_criteria",
    "rollback_plan",
)


class FindingSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """One structured validation issue raised by ``WorkPacket.validate()``.

    Findings are data, not exceptions: the caller decides whether to
    block on errors or proceed with warnings.
    """

    field_name: str
    severity: FindingSeverity
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field_name,
            "severity": self.severity.value,
            "message": self.message,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_list() -> list[str]:
    return []


@dataclass
class WorkPacket:
    """Canonical JARVIS Prime work packet.

    Fields mirror what the eight gates and the mission spec expect. All
    list fields default to empty lists; ``created_at`` defaults to a
    timezone-aware UTC timestamp at construction time.

    Required-for-validation fields (surfaced by ``validate()`` when
    missing): mission, repo_root, branch, risk_class, acceptance_criteria,
    rollback_plan.
    """

    mission: str = ""
    repo_root: str = ""
    branch: str = ""
    risk_class: str = ""
    allowed_files: list[str] = field(default_factory=_empty_list)
    protected_files: list[str] = field(default_factory=_empty_list)
    non_goals: list[str] = field(default_factory=_empty_list)
    acceptance_criteria: list[str] = field(default_factory=_empty_list)
    files_changed: list[str] = field(default_factory=_empty_list)
    tests_run: list[str] = field(default_factory=_empty_list)
    tests_failed: list[str] = field(default_factory=_empty_list)
    verification_summary: str = ""
    rollback_plan: str = ""
    owner_gated_actions: list[str] = field(default_factory=_empty_list)
    owner_authorization_phrase: Optional[str] = None
    citations: list[str] = field(default_factory=_empty_list)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        # Clamp confidence to [0.0, 1.0] at construction so downstream
        # readers can trust the invariant. Out-of-range inputs are still
        # surfaced by validate() so the caller learns about the bad input.
        if isinstance(self.confidence, (int, float)):
            if self.confidence < 0.0:
                self.confidence = 0.0
            elif self.confidence > 1.0:
                self.confidence = 1.0

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict.

        ``datetime`` is serialized to ISO-8601 (with timezone). All other
        fields are plain primitives.
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
        """Reconstruct a WorkPacket from a dict produced by ``to_dict()``.

        Unknown keys are ignored. ``created_at`` is parsed from ISO-8601
        if a string is provided; if parsing fails or the field is absent,
        the default (utc-now at construction) is used.
        """
        known: dict[str, Any] = {f.name: getattr(cls, f.name, None) for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if f.name == "created_at" and isinstance(value, str):
                parsed = _parse_iso_datetime(value)
                if parsed is not None:
                    kwargs[f.name] = parsed
                continue
            if f.name == "created_at" and isinstance(value, datetime):
                kwargs[f.name] = value
                continue
            kwargs[f.name] = value
        # Suppress unused local for static checkers; kept for clarity above.
        del known
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return structured findings; empty list means valid.

        Required-field absence is reported as ERROR. Out-of-range
        confidence (before clamping) and unknown risk classes are also
        ERRORs. Empty optional list fields produce no finding.
        """
        findings: list[WorkPacketValidationFinding] = []

        for name in _REQUIRED_FIELDS:
            value = getattr(self, name, None)
            if _is_empty(value):
                findings.append(
                    WorkPacketValidationFinding(
                        field_name=name,
                        severity=FindingSeverity.ERROR,
                        message=f"{name} is required",
                    )
                )

        if self.risk_class and self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field_name="risk_class",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"risk_class {self.risk_class!r} not one of "
                        f"{sorted(VALID_RISK_CLASSES)}"
                    ),
                )
            )

        if not isinstance(self.confidence, (int, float)):
            findings.append(
                WorkPacketValidationFinding(
                    field_name="confidence",
                    severity=FindingSeverity.ERROR,
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        elif self.confidence <= 0.0 or self.confidence >= 1.0:
            # After __post_init__ clamping, values outside [0,1] become
            # exactly 0.0 or 1.0. Treat those endpoints as a signal that
            # the caller may have passed something invalid — surface a
            # warning so they notice without blocking on it.
            if self.confidence == 0.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field_name="confidence",
                        severity=FindingSeverity.WARNING,
                        message="confidence is 0.0 (unset or clamped from negative)",
                    )
                )
            elif self.confidence == 1.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field_name="confidence",
                        severity=FindingSeverity.WARNING,
                        message="confidence is 1.0 (clamped from >1.0 or asserts certainty)",
                    )
                )

        if (
            self.owner_authorization_phrase is not None
            and not isinstance(self.owner_authorization_phrase, str)
        ):
            findings.append(
                WorkPacketValidationFinding(
                    field_name="owner_authorization_phrase",
                    severity=FindingSeverity.ERROR,
                    message="owner_authorization_phrase must be a string or None",
                )
            )

        if not isinstance(self.created_at, datetime):
            findings.append(
                WorkPacketValidationFinding(
                    field_name="created_at",
                    severity=FindingSeverity.ERROR,
                    message="created_at must be a timezone-aware datetime",
                )
            )
        elif self.created_at.tzinfo is None:
            findings.append(
                WorkPacketValidationFinding(
                    field_name="created_at",
                    severity=FindingSeverity.ERROR,
                    message="created_at must be timezone-aware (UTC)",
                )
            )

        return findings

    def is_valid(self) -> bool:
        """Convenience: True when no ERROR-severity findings."""
        return not any(
            f.severity == FindingSeverity.ERROR for f in self.validate()
        )

    def missing_required_fields(self) -> list[str]:
        """Names of required fields that are missing/empty."""
        return [
            name for name in _REQUIRED_FIELDS
            if _is_empty(getattr(self, name, None))
        ]


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
        return True
    return False


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    """Parse ISO-8601 to a timezone-aware datetime, or None on failure."""
    try:
        # Python 3.11+ datetime.fromisoformat handles "Z" since 3.11.
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    "FindingSeverity",
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
