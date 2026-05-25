"""Standard JARVIS Prime WorkPacket — the canonical handoff envelope.

A WorkPacket is the structured handoff used when JARVIS Prime dispatches
work to Claude Code (primary builder), Codex (reviewer / bounded fix
worker), or any specialist agent. It captures mission, scope, gates,
and verification evidence in one place so the eight verification gates
in ``hermes_cli.jarvis_prime.gates`` can evaluate it.

Design rules:

- Stdlib only at import time (no pydantic, no network).
- Plain ``dataclasses`` — works on Termux and CI with no extras.
- ``datetime`` defaults are timezone-aware UTC.
- ``owner_gated_actions`` are *data* — this module never executes them.
- ``confidence`` is clamped to [0.0, 1.0] in ``validate()``.
- ``risk_class`` is restricted to the spec set ``{RC0..RC4}`` and
  validated, not enforced at construction time (so callers can build
  a partially-filled draft and ask ``validate()`` what is missing).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional


VALID_RISK_CLASSES: frozenset[str] = frozenset({"RC0", "RC1", "RC2", "RC3", "RC4"})

REQUIRED_FIELDS: tuple[str, ...] = (
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
    """One structured validation finding from ``WorkPacket.validate``."""

    field: str
    severity: FindingSeverity
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "severity": self.severity.value,
            "message": self.message,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkPacket:
    """Canonical JARVIS Prime work-packet.

    Fields are intentionally permissive at construction so callers can
    build a draft incrementally; missing/invalid required fields are
    reported by :meth:`validate`.
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
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkPacket":
        """Reconstruct a packet from a mapping produced by :meth:`to_dict`.

        Unknown keys are ignored so the schema can evolve without
        breaking historical packets in the decision ledger.
        """

        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            if key == "created_at" and isinstance(value, str):
                try:
                    kwargs[key] = datetime.fromisoformat(value)
                except ValueError:
                    kwargs[key] = _utc_now()
                continue
            kwargs[key] = value
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return structured findings; empty list means the packet is valid.

        Findings are *data*. ``validate`` never raises and never executes
        any owner-gated actions listed on the packet.
        """

        findings: list[WorkPacketValidationFinding] = []

        for name in REQUIRED_FIELDS:
            value = getattr(self, name, None)
            if value is None:
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        severity=FindingSeverity.ERROR,
                        message=f"{name} is required",
                    )
                )
                continue
            if isinstance(value, str) and not value.strip():
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        severity=FindingSeverity.ERROR,
                        message=f"{name} is required (empty string)",
                    )
                )
                continue
            if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        severity=FindingSeverity.ERROR,
                        message=f"{name} is required (empty collection)",
                    )
                )

        if self.risk_class and self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"risk_class {self.risk_class!r} is not one of "
                        f"{sorted(VALID_RISK_CLASSES)}"
                    ),
                )
            )

        if not isinstance(self.confidence, (int, float)):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    severity=FindingSeverity.ERROR,
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        else:
            if self.confidence < 0.0 or self.confidence > 1.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field="confidence",
                        severity=FindingSeverity.WARNING,
                        message=(
                            f"confidence {self.confidence!r} outside [0.0, 1.0]; "
                            "will be clamped"
                        ),
                    )
                )

        return findings

    def is_valid(self) -> bool:
        """True when ``validate`` reports no ERROR-severity findings."""

        return not any(
            f.severity is FindingSeverity.ERROR for f in self.validate()
        )

    def clamped_confidence(self) -> float:
        """Return ``confidence`` safely clamped to [0.0, 1.0]."""

        try:
            value = float(self.confidence)
        except (TypeError, ValueError):
            return 0.0
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value
