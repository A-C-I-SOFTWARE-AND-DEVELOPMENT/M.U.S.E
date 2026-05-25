"""Standard WorkPacket model for JARVIS Prime jobs.

A ``WorkPacket`` is the canonical, repo-agnostic envelope every
JARVIS Prime job rides on. It carries the mission, the scope, the
acceptance criteria, the verification evidence, and the rollback
plan. It is the payload that flows from the orchestrator to a
builder (Claude Code) to a reviewer (Codex), and back to JARVIS for
gate evaluation.

Design constraints (matching the Wave 0 brief):

- **stdlib-only at import time.** No pydantic. No requests. No
  heavy Hermes subsystems imported at module load. This keeps
  Termux and slim CI images happy.
- **Network-free.** Construction, validation, and serialization
  never touch the network.
- **Risk classes.** ``risk_class`` is one of ``RC0``..``RC4``,
  matching the rest of the runtime.
- **Confidence.** ``confidence`` is a float clamped/validated into
  ``[0.0, 1.0]``.
- **Owner gates as data.** ``owner_gated_actions`` is preserved as
  a list of action names. **Nothing in this module executes them.**
  Execution is mediated by ``hermes_cli.jarvis_prime.owner_auth``.

The dataclass mirrors the field set that the eight verification
gates already read (see ``hermes_cli.jarvis_prime.gates``), so a
``WorkPacket`` can be passed straight to ``run_gate_summary``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional


VALID_RISK_CLASSES: frozenset[str] = frozenset({"RC0", "RC1", "RC2", "RC3", "RC4"})

# The exact phrase that authorizes an owner-gated action. Kept in
# sync with ``hermes_cli.jarvis_prime.owner_auth.AUTHORIZATION_PHRASE``
# but duplicated here so importing this module never requires a
# transitive load of ``owner_auth``.
AUTHORIZATION_PHRASE: str = "Yes, with authorization."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorkPacketValidationFinding:
    """One structured finding from ``WorkPacket.validate()``.

    ``severity`` is a short tag — ``"missing"``, ``"invalid"``,
    ``"out_of_range"`` — to let callers group findings without
    parsing free text. ``field`` is the WorkPacket field name the
    finding applies to (or ``""`` if the finding is packet-wide).
    """

    field: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "severity": self.severity, "message": self.message}


@dataclass
class WorkPacket:
    """A single unit of JARVIS Prime work.

    Required, in the sense that ``validate()`` reports them as
    findings when missing:

    - ``mission``
    - ``repo_root``
    - ``branch``
    - ``risk_class``
    - ``acceptance_criteria``
    - ``rollback_plan``

    The remaining fields are optional but recommended. They are
    preserved verbatim by ``to_dict``/``from_dict``.
    """

    # --- core identity -----------------------------------------------------
    mission: str = ""
    repo_root: str = ""
    branch: str = ""
    risk_class: str = ""

    # --- scope -------------------------------------------------------------
    allowed_files: list[str] = field(default_factory=list)
    protected_files: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)

    # --- execution evidence ------------------------------------------------
    files_changed: list[str] = field(default_factory=list)
    tests_run: list[str] = field(default_factory=list)
    tests_failed: list[str] = field(default_factory=list)
    verification_summary: str = ""

    # --- safety ------------------------------------------------------------
    rollback_plan: str = ""
    owner_gated_actions: list[str] = field(default_factory=list)
    owner_authorization_phrase: str = ""

    # --- epistemics --------------------------------------------------------
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0

    # --- bookkeeping -------------------------------------------------------
    created_at: datetime = field(default_factory=_utcnow)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe ``dict`` representation.

        ``created_at`` is serialized as an ISO-8601 string with
        timezone offset. ``confidence`` is preserved as a float.
        Lists are shallow-copied so callers cannot mutate internal
        state by mutating the returned dict.
        """

        data = asdict(self)
        # ``asdict`` keeps ``datetime`` objects as-is, which is not
        # JSON-safe. Normalize.
        created = data.get("created_at")
        if isinstance(created, datetime):
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            data["created_at"] = created.isoformat()
        # Defensive copies for list fields (asdict already copies,
        # but be explicit about the intent).
        for key, value in list(data.items()):
            if isinstance(value, list):
                data[key] = list(value)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkPacket":
        """Reconstruct a ``WorkPacket`` from a ``to_dict()`` payload.

        Unknown keys are ignored. Missing keys fall back to the
        dataclass default. ``created_at`` may be passed as a
        ``datetime`` or as an ISO-8601 string; naive strings are
        treated as UTC.
        """

        if not isinstance(data, Mapping):
            raise TypeError("WorkPacket.from_dict requires a mapping")

        kwargs: dict[str, Any] = {}
        for f in cls.__dataclass_fields__.values():
            if f.name not in data:
                continue
            value = data[f.name]
            if f.name == "created_at":
                value = _coerce_created_at(value)
            elif f.name == "confidence":
                value = _coerce_confidence(value)
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
                value = list(value) if isinstance(value, Iterable) and not isinstance(value, (str, bytes)) else []
            kwargs[f.name] = value
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return structured findings for missing/invalid fields.

        An empty list means the packet is well-formed enough to be
        handed to the verification gates. A non-empty list does not
        raise — callers decide whether to block, ask the owner,
        or proceed anyway.
        """

        findings: list[WorkPacketValidationFinding] = []

        for name in ("mission", "repo_root", "branch", "rollback_plan"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        severity="missing",
                        message=f"{name} is required",
                    )
                )

        if not self.risk_class:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    severity="missing",
                    message="risk_class is required (RC0..RC4)",
                )
            )
        elif self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    severity="invalid",
                    message=(
                        f"risk_class={self.risk_class!r} is not one of "
                        f"{sorted(VALID_RISK_CLASSES)}"
                    ),
                )
            )

        if not self.acceptance_criteria:
            findings.append(
                WorkPacketValidationFinding(
                    field="acceptance_criteria",
                    severity="missing",
                    message="acceptance_criteria must list at least one criterion",
                )
            )

        if not isinstance(self.confidence, (int, float)):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    severity="invalid",
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        elif self.confidence < 0.0 or self.confidence > 1.0:
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    severity="out_of_range",
                    message=(
                        f"confidence={self.confidence!r} is outside [0.0, 1.0]"
                    ),
                )
            )

        if self.owner_gated_actions and not self.owner_authorization_phrase:
            findings.append(
                WorkPacketValidationFinding(
                    field="owner_authorization_phrase",
                    severity="missing",
                    message=(
                        "owner_gated_actions present but no "
                        "owner_authorization_phrase recorded; actions remain "
                        "deferred"
                    ),
                )
            )
        elif (
            self.owner_gated_actions
            and self.owner_authorization_phrase
            and self.owner_authorization_phrase != AUTHORIZATION_PHRASE
        ):
            findings.append(
                WorkPacketValidationFinding(
                    field="owner_authorization_phrase",
                    severity="invalid",
                    message=(
                        "owner_authorization_phrase does not match the exact "
                        "owner-authorization phrase; actions remain deferred"
                    ),
                )
            )

        return findings

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def is_valid(self) -> bool:
        """Return ``True`` iff ``validate()`` reports no findings."""

        return not self.validate()

    def clamp_confidence(self) -> None:
        """Clamp ``confidence`` into ``[0.0, 1.0]`` in place.

        Useful when accepting a packet from an untrusted source. Not
        called automatically by ``validate()`` — validation reports
        the issue rather than silently rewriting the field.
        """

        if not isinstance(self.confidence, (int, float)):
            self.confidence = 0.0
            return
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _coerce_created_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return _utcnow()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return _utcnow()


def _coerce_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "AUTHORIZATION_PHRASE",
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
