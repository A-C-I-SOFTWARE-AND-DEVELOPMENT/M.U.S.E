"""Standard WorkPacket model for JARVIS Prime.

A ``WorkPacket`` is the canonical hand-off object passed between
JARVIS Prime, the AOS Council, and downstream workers (Claude Code as
primary builder, Codex as reviewer / bounded-fix worker, local test
runners). It carries the mission, the scope rules, the verification
results, and — critically — the owner-gated actions as **data**, not
as commands to execute.

Wave 0 constraints honored here:

* stdlib only (no ``pydantic``, no network);
* no heavy Hermes subsystem imports at module load;
* timezone-aware UTC timestamps;
* dataclass-based, so it is trivial to ``to_dict`` / ``from_dict`` for
  JSON transport between processes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


VALID_RISK_CLASSES: tuple[str, ...] = ("RC0", "RC1", "RC2", "RC3", "RC4")
"""Allowed risk-class identifiers for a WorkPacket.

* ``RC0`` — read-only / inspection.
* ``RC1`` — local file edits, no shared state.
* ``RC2`` — local edits that touch shared runtime files.
* ``RC3`` — actions affecting integration / shared branches.
* ``RC4`` — owner-gated actions (merges, deploys, releases, DNS,
  credentials, public posting, spending, destructive operations).
"""

OWNER_AUTHORIZATION_PHRASE: str = "Yes, with authorization."
"""The exact phrase the owner must supply to authorize an RC4 action.

WorkPackets carry this phrase as data only; nothing in this module
executes owner-gated actions on the basis of seeing it.
"""

REQUIRED_FIELDS: tuple[str, ...] = (
    "mission",
    "repo_root",
    "branch",
    "risk_class",
    "acceptance_criteria",
    "rollback_plan",
)


def _utc_now() -> datetime:
    """Return a timezone-aware UTC ``datetime`` for ``created_at``."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """A single structured finding from :meth:`WorkPacket.validate`.

    ``field`` is the WorkPacket field name the finding applies to (or
    ``"<packet>"`` for whole-packet findings). ``code`` is a short
    machine-readable identifier. ``message`` is the human-readable
    explanation. ``severity`` is one of ``"error"`` or ``"warning"``.
    """

    field: str
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class WorkPacket:
    """Canonical JARVIS Prime work packet.

    All list fields default to empty lists so callers can build a
    packet incrementally without tripping over ``None``. ``confidence``
    is clamped into ``[0.0, 1.0]`` by :meth:`__post_init__`; values
    outside the range are surfaced by :meth:`validate` as warnings so
    the caller knows their input was adjusted.
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
    confidence: float = 0.0

    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        try:
            conf = float(self.confidence)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < 0.0:
            conf = 0.0
        elif conf > 1.0:
            conf = 1.0
        self.confidence = conf

        if self.created_at is None:
            self.created_at = _utc_now()
        elif isinstance(self.created_at, datetime) and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    # ── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict representation of the packet.

        ``created_at`` is emitted as an ISO-8601 string with timezone
        offset. List fields are returned as plain lists so the result
        round-trips through ``json.dumps`` / ``json.loads`` without
        further conversion.
        """

        data = asdict(self)
        created_at = self.created_at
        if isinstance(created_at, datetime):
            data["created_at"] = created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPacket":
        """Rebuild a :class:`WorkPacket` from its ``to_dict`` form.

        Unknown keys are ignored (forward compatibility). ``created_at``
        accepts an ISO-8601 string or an existing ``datetime``. Missing
        fields fall back to dataclass defaults; this means
        :meth:`from_dict` followed by :meth:`validate` is the right
        pattern when reading packets from external sources.
        """

        if not isinstance(data, dict):
            raise TypeError("WorkPacket.from_dict requires a dict")

        known = {f for f in cls.__dataclass_fields__}
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            kwargs[key] = value

        list_fields = (
            "allowed_files",
            "protected_files",
            "non_goals",
            "acceptance_criteria",
            "files_changed",
            "tests_run",
            "tests_failed",
            "owner_gated_actions",
            "citations",
        )
        for name in list_fields:
            value = kwargs.get(name)
            if value is None:
                kwargs[name] = []
            elif isinstance(value, list):
                kwargs[name] = list(value)
            else:
                kwargs[name] = list(_as_iterable(value))

        created_at = kwargs.get("created_at")
        if isinstance(created_at, str):
            kwargs["created_at"] = _parse_iso_datetime(created_at)
        elif created_at is None and "created_at" in kwargs:
            kwargs.pop("created_at")

        return cls(**kwargs)

    # ── Validation ────────────────────────────────────────────────

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return structured findings; an empty list means the packet
        is valid.

        Findings cover:

        * missing required fields (mission, repo_root, branch,
          risk_class, acceptance_criteria, rollback_plan);
        * unknown ``risk_class`` values;
        * confidence outside ``[0.0, 1.0]`` (a warning — the value is
          clamped in ``__post_init__``, but the caller's input is
          surfaced);
        * RC4 packets that list ``owner_gated_actions`` but ship the
          wrong (or missing) authorization phrase.
        """

        findings: list[WorkPacketValidationFinding] = []

        for required in REQUIRED_FIELDS:
            value = getattr(self, required, None)
            if _is_empty(value):
                findings.append(
                    WorkPacketValidationFinding(
                        field=required,
                        code="missing_required_field",
                        message=f"{required} is required",
                    )
                )

        if self.risk_class and self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="invalid_risk_class",
                    message=(
                        f"risk_class {self.risk_class!r} is not one of "
                        f"{', '.join(VALID_RISK_CLASSES)}"
                    ),
                )
            )

        if not (0.0 <= self.confidence <= 1.0):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="confidence_out_of_range",
                    message="confidence must be between 0.0 and 1.0",
                    severity="warning",
                )
            )

        if self.risk_class == "RC4" and self.owner_gated_actions:
            if self.owner_authorization_phrase != OWNER_AUTHORIZATION_PHRASE:
                findings.append(
                    WorkPacketValidationFinding(
                        field="owner_authorization_phrase",
                        code="missing_owner_authorization",
                        message=(
                            "RC4 packets with owner_gated_actions must "
                            "carry the exact owner authorization phrase"
                        ),
                    )
                )

        return findings

    def is_valid(self) -> bool:
        """Convenience: ``True`` iff :meth:`validate` returns no
        error-severity findings. Warnings do not fail the packet.
        """

        return not any(f.severity == "error" for f in self.validate())


# ── Helpers ──────────────────────────────────────────────────────


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _as_iterable(value: Any) -> Iterable[Any]:
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return iter(value)
    except TypeError:
        return [value]


def _parse_iso_datetime(text: str) -> datetime:
    candidate = text
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return _utc_now()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    "OWNER_AUTHORIZATION_PHRASE",
    "REQUIRED_FIELDS",
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
