"""Standard JARVIS Prime ``WorkPacket`` model.

A ``WorkPacket`` is the canonical handoff record JARVIS Prime uses when
routing a mission to a worker (Claude Code, Codex, a local runner, the
owner). It captures intent, scope, gates, verification, and provenance
in one stdlib-only dataclass so any layer can produce, inspect, log, or
serialize one without pulling in heavy dependencies.

Wave 0 scope: data model only. Nothing in this module dispatches work,
talks to the network, or imports Hermes subsystems at module load time.
Owner-gated actions are preserved as *data* and never executed here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

# Risk classes the WorkPacket validator recognizes. Ordered low → high.
RISK_CLASSES: tuple[str, ...] = ("RC0", "RC1", "RC2", "RC3", "RC4")

# Fields that must be populated for a packet to be considered valid for
# downstream routing. ``confidence`` and ``risk_class`` get value-shape
# checks in addition to presence.
REQUIRED_FIELDS: tuple[str, ...] = (
    "mission",
    "repo_root",
    "branch",
    "risk_class",
    "acceptance_criteria",
    "rollback_plan",
)


def _utc_now_iso() -> str:
    """Timezone-aware UTC timestamp in ISO 8601 form."""
    return datetime.now(timezone.utc).isoformat()


def _clamp_confidence(value: Any) -> float | None:
    """Coerce ``value`` to a float in [0.0, 1.0] or return None.

    ``None`` means "no usable confidence value"; ``validate()`` reports
    that as a finding rather than silently inventing one.
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """Single structured validation finding.

    ``field`` is the WorkPacket attribute name, ``code`` is a short
    machine-friendly tag, ``message`` is the human-readable reason.
    """

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass
class WorkPacket:
    """Canonical JARVIS Prime work packet.

    All collection fields default to empty containers, never ``None``,
    so callers can append without first reassigning. ``created_at``
    defaults to the construction-time UTC instant in ISO 8601.
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
    owner_authorization_phrase: str = ""
    citations: list[str] = field(default_factory=list)
    confidence: float | None = None
    created_at: str = field(default_factory=_utc_now_iso)

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict snapshot suitable for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPacket":
        """Reconstruct a ``WorkPacket`` from a plain dict.

        Unknown keys are ignored rather than rejected — packets evolve
        and we don't want a forward-compatible producer to break an
        older reader. Missing keys fall back to dataclass defaults.
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"WorkPacket.from_dict expected dict, got {type(data).__name__}"
            )
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}

        # Defensive copies for list fields so the caller's dict can't
        # mutate the packet later.
        for key, value in list(filtered.items()):
            if isinstance(value, list):
                filtered[key] = list(value)

        # Confidence gets clamped on ingest the same way construction
        # would clamp it. We do not raise here — validate() reports.
        if "confidence" in filtered:
            filtered["confidence"] = _clamp_confidence(filtered["confidence"])

        return cls(**filtered)

    # ── Validation ───────────────────────────────────────────────────

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return structured findings; empty list means the packet is valid.

        The checks intentionally cover only the Wave 0 surface:
        required-field presence, risk-class membership, confidence
        range. Higher-level invariants (gate ordering, owner
        authorization shape, file allowlist enforcement) belong to
        later waves.
        """
        findings: list[WorkPacketValidationFinding] = []

        for name in REQUIRED_FIELDS:
            value = getattr(self, name)
            if _is_blank(value):
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        code="missing",
                        message=f"required field {name!r} is missing or empty",
                    )
                )

        # risk_class must be one of the recognized classes when present.
        if self.risk_class and self.risk_class not in RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="invalid_value",
                    message=(
                        f"risk_class {self.risk_class!r} is not one of "
                        f"{', '.join(RISK_CLASSES)}"
                    ),
                )
            )

        # confidence: None is allowed but flagged; out-of-range is
        # reported even though construction may have already clamped.
        if self.confidence is None:
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="missing",
                    message="confidence is not set",
                )
            )
        else:
            try:
                c = float(self.confidence)
            except (TypeError, ValueError):
                findings.append(
                    WorkPacketValidationFinding(
                        field="confidence",
                        code="invalid_type",
                        message="confidence must be a number in [0.0, 1.0]",
                    )
                )
            else:
                if c < 0.0 or c > 1.0:
                    findings.append(
                        WorkPacketValidationFinding(
                            field="confidence",
                            code="out_of_range",
                            message="confidence must be within [0.0, 1.0]",
                        )
                    )

        return findings

    def is_valid(self) -> bool:
        """Convenience: ``True`` when ``validate()`` returns no findings."""
        return not self.validate()


def _is_blank(value: Any) -> bool:
    """True when a required field is effectively empty.

    Treats ``None``, empty string, and empty collection as blank.
    Whitespace-only strings are also blank — those slip past required
    checks too easily otherwise.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    if isinstance(value, Iterable):
        # Generic iterables: treat as non-blank if they have any item.
        for _ in value:
            return False
        return True
    return False
