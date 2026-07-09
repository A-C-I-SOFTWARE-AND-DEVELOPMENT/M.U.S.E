"""Standard muse WorkPacket model.

Structured descriptor for a single JARVIS unit of work. The shipped
runtime (``runtime.py``, ``router.py``, ``gates.py``) already speaks
its own internal shapes; this module adds a canonical, JSON-friendly
packet schema that mode classifiers, gates, owner-auth, and
verification layers can pass around without re-deriving fields from
free-form prose.

Design constraints:

* Stdlib-only at import time (Termux-friendly, slim-CI-friendly).
* No network, filesystem, or subprocess calls.
* Owner-gated actions are recorded as data only; this module never
  executes them.
* Confidence is clamped to ``[0.0, 1.0]``; invalid risk classes are
  surfaced through :meth:`WorkPacket.validate`, not raised, so callers
  can show findings to the owner instead of crashing.
* Authorization phrase comes from
  :mod:`hermes_cli.jarvis_prime.owner_auth` so this module and the
  shipped runtime agree on the exact canonical string.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from typing import Any, Iterable

from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


VALID_RISK_CLASSES: tuple[str, ...] = ("RC0", "RC1", "RC2", "RC3", "RC4")

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


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _clamp_confidence(value: Any) -> float:
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return 0.0
    if as_float < 0.0:
        return 0.0
    if as_float > 1.0:
        return 1.0
    return as_float


@dataclass
class WorkPacketValidationFinding:
    """A single structured validation finding for a :class:`WorkPacket`."""

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass
class WorkPacket:
    """Standard muse unit-of-work descriptor.

    All fields are data-only. Construction never performs IO. Owner-gated
    actions are stored verbatim and require the owner to reply with the
    canonical :data:`hermes_cli.jarvis_prime.owner_auth.AUTHORIZATION_PHRASE`
    before any downstream executor acts on them.
    """

    mission: str = ""
    repo_root: str = ""
    branch: str = ""
    risk_class: str = ""
    # Identity of the AGENT that authored/acted on the change under review, in
    # the same namespace as a review's ``reviewer_id`` (see
    # ``guardrail_collectors.collect_review_evidence``). Optional and empty by
    # default: guardrail collectors thread it into
    # ``collect_git_diff_evidence(author_id=...)`` so the strict review gate's
    # Clause C19 builder != reviewer check can fire. Left blank, C19 fails open.
    acting_agent_id: str = ""
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
    owner_authorization_phrase: str = AUTHORIZATION_PHRASE
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = field(default_factory=_utcnow_iso)

    def __post_init__(self) -> None:
        self.allowed_files = _coerce_str_list(self.allowed_files)
        self.protected_files = _coerce_str_list(self.protected_files)
        self.non_goals = _coerce_str_list(self.non_goals)
        self.acceptance_criteria = _coerce_str_list(self.acceptance_criteria)
        self.files_changed = _coerce_str_list(self.files_changed)
        self.tests_run = _coerce_str_list(self.tests_run)
        self.tests_failed = _coerce_str_list(self.tests_failed)
        self.owner_gated_actions = _coerce_str_list(self.owner_gated_actions)
        self.citations = _coerce_str_list(self.citations)
        self.confidence = _clamp_confidence(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPacket":
        """Construct a :class:`WorkPacket` from a plain dictionary.

        Unknown keys are ignored so callers can safely round-trip
        packets produced by newer versions of the schema.
        """
        if not isinstance(data, dict):
            raise TypeError("WorkPacket.from_dict requires a dict")
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return structured findings; an empty list means the packet is valid.

        Never raises. The router, gates, and owner UI can surface
        findings and decide whether to proceed.
        """
        findings: list[WorkPacketValidationFinding] = []

        for name in REQUIRED_FIELDS:
            value = getattr(self, name, None)
            if isinstance(value, str):
                if not value.strip():
                    findings.append(
                        WorkPacketValidationFinding(
                            field=name,
                            code="missing",
                            message=f"{name} is required and must be non-empty",
                        )
                    )
            elif isinstance(value, list):
                if not value:
                    findings.append(
                        WorkPacketValidationFinding(
                            field=name,
                            code="missing",
                            message=f"{name} is required and must contain at least one entry",
                        )
                    )
            elif value is None:
                findings.append(
                    WorkPacketValidationFinding(
                        field=name,
                        code="missing",
                        message=f"{name} is required",
                    )
                )

        if self.risk_class and self.risk_class not in VALID_RISK_CLASSES:
            findings.append(
                WorkPacketValidationFinding(
                    field="risk_class",
                    code="invalid_value",
                    message=(
                        f"risk_class={self.risk_class!r} is not one of "
                        f"{VALID_RISK_CLASSES}"
                    ),
                )
            )

        if not isinstance(self.confidence, (int, float)):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="invalid_type",
                    message="confidence must be a float between 0.0 and 1.0",
                )
            )
        else:
            if self.confidence < 0.0 or self.confidence > 1.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field="confidence",
                        code="out_of_range",
                        message="confidence must be between 0.0 and 1.0",
                    )
                )

        if self.owner_gated_actions and not self.owner_authorization_phrase:
            findings.append(
                WorkPacketValidationFinding(
                    field="owner_authorization_phrase",
                    code="missing",
                    message=(
                        "owner_gated_actions are present but no "
                        "owner_authorization_phrase is set"
                    ),
                )
            )

        return findings

    def is_valid(self) -> bool:
        return not self.validate()


__all__ = [
    "REQUIRED_FIELDS",
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
