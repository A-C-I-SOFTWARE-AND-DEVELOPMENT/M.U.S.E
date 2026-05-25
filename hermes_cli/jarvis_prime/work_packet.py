"""Standard JARVIS Prime WorkPacket model.

Wave 0 foundation. Stdlib-only on purpose: this module must be
importable in a minimal Termux environment without pulling in pydantic,
attrs, or any other third-party dependency, and without performing
network I/O or importing heavy Hermes subsystems at import time.

A WorkPacket is the unit of work JARVIS Prime hands to a builder
(Claude Code, Codex, a worker, or itself). It carries enough context
for the builder to act safely and enough metadata for the owner to
audit what happened.

This module is data + validation only. It does **not** execute owner-
gated actions; it preserves them as data so the runtime layer can
prompt for the explicit authorization phrase before doing anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional, Sequence


# Risk classes JARVIS Prime understands. Kept as a tuple of strings
# (not an Enum) so this module stays trivial to serialize / round-trip
# through to_dict / from_dict without custom encoders.
RISK_CLASSES: tuple[str, ...] = ("RC0", "RC1", "RC2", "RC3", "RC4")

# The exact phrase the owner must type to authorize an owner-gated
# action. WorkPackets only record the phrase as data; they never
# execute on it.
OWNER_AUTHORIZATION_PHRASE: str = "Yes, with authorization."

# Required fields for a packet to be considered well-formed. Missing or
# empty values for any of these produce a validation finding.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "mission",
    "repo_root",
    "branch",
    "risk_class",
    "acceptance_criteria",
    "rollback_plan",
)


def _utc_now_iso() -> str:
    """Timezone-aware UTC timestamp in ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """A single problem discovered by ``WorkPacket.validate()``.

    Frozen so findings can be safely passed around and de-duplicated.
    """

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass
class WorkPacket:
    """Standard JARVIS Prime work packet.

    All fields default to safe empty values so a packet can be built
    incrementally (e.g. mission first, acceptance criteria later) and
    then validated before dispatch.
    """

    mission: str = ""
    repo_root: str = ""
    branch: str = ""
    risk_class: str = ""
    allowed_files: List[str] = field(default_factory=list)
    protected_files: List[str] = field(default_factory=list)
    non_goals: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    tests_run: List[str] = field(default_factory=list)
    tests_failed: List[str] = field(default_factory=list)
    verification_summary: str = ""
    rollback_plan: str = ""
    owner_gated_actions: List[str] = field(default_factory=list)
    owner_authorization_phrase: str = OWNER_AUTHORIZATION_PHRASE
    citations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = field(default_factory=_utc_now_iso)

    # ── serialization ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation suitable for JSON.

        Lists are copied so mutating the returned dict cannot mutate
        the packet's internal state.
        """
        data = asdict(self)
        for key, value in list(data.items()):
            if isinstance(value, list):
                data[key] = list(value)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkPacket":
        """Rebuild a packet from a ``to_dict()``-shaped mapping.

        Unknown keys are ignored rather than raising, so a packet
        serialized by a newer version can still be partially loaded by
        an older one without crashing. Missing keys fall back to the
        dataclass defaults.
        """
        if not isinstance(data, Mapping):
            raise TypeError("WorkPacket.from_dict requires a mapping")

        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for key in known:
            if key not in data:
                continue
            value = data[key]
            if key in _LIST_FIELDS:
                kwargs[key] = _coerce_string_list(value)
            elif key == "confidence":
                kwargs[key] = _coerce_confidence(value)
            else:
                kwargs[key] = value
        return cls(**kwargs)

    # ── validation ────────────────────────────────────────────────

    def validate(self) -> List[WorkPacketValidationFinding]:
        """Return validation findings; empty list means valid.

        Findings cover:

        - missing required fields (mission, repo_root, branch,
          risk_class, acceptance_criteria, rollback_plan)
        - unknown ``risk_class`` values
        - ``confidence`` outside the [0.0, 1.0] range or non-numeric
        - ``owner_gated_actions`` present without the canonical
          authorization phrase recorded on the packet (the phrase is
          data; this is not authorization, only consistency)
        """
        findings: List[WorkPacketValidationFinding] = []

        for name in _REQUIRED_FIELDS:
            value = getattr(self, name)
            if _is_missing(value):
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        code="missing",
                        message=f"required field '{name}' is missing or empty",
                    )
                )

        if self.risk_class and self.risk_class not in RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="invalid_value",
                    message=(
                        f"risk_class '{self.risk_class}' is not one of "
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
                    code="invalid_type",
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        else:
            if self.confidence < 0.0 or self.confidence > 1.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field="confidence",
                        code="out_of_range",
                        message=(
                            f"confidence {self.confidence} is outside the "
                            "valid range [0.0, 1.0]"
                        ),
                    )
                )

        if self.owner_gated_actions and (
            self.owner_authorization_phrase != OWNER_AUTHORIZATION_PHRASE
        ):
            findings.append(
                WorkPacketValidationFinding(
                    field="owner_authorization_phrase",
                    code="phrase_mismatch",
                    message=(
                        "owner_gated_actions present but "
                        "owner_authorization_phrase does not match the "
                        "canonical phrase; gated actions remain unexecuted"
                    ),
                )
            )

        return findings

    def is_valid(self) -> bool:
        """Convenience predicate: True iff ``validate()`` finds nothing."""
        return not self.validate()

    def missing_required_fields(self) -> List[str]:
        """Subset of ``_REQUIRED_FIELDS`` currently missing on this packet."""
        return [
            f.field for f in self.validate() if f.code == "missing"
        ]


# ── helpers ────────────────────────────────────────────────────────

_LIST_FIELDS: frozenset[str] = frozenset(
    {
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
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _coerce_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # A bare string is almost certainly a mistake on the caller's
        # side, but we accept it as a single-element list rather than
        # silently iterating its characters.
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _coerce_confidence(value: Any) -> float:
    """Best-effort coerce confidence into a float without clamping.

    Clamping would hide bad inputs; we want ``validate()`` to surface
    out-of-range values so the caller knows to fix them. Non-numeric
    inputs that cannot be coerced fall through as 0.0 so the packet
    still validates structurally (the validator will flag the type).
    """
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "OWNER_AUTHORIZATION_PHRASE",
    "RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
