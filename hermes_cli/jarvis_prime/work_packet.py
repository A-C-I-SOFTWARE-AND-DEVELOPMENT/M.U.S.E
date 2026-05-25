"""Standard WorkPacket data contract for JARVIS Prime.

This is foundation-only (Wave 0): a stdlib-only dataclass model that
captures what JARVIS Prime hands to a worker, what the worker is
allowed to do, and what evidence the worker must return before the
work can be called done.

Design rules (Wave 0):

- stdlib-only: no pydantic, no third-party imports.
- no network access at import time or in any method here.
- no heavy Hermes subsystems imported at module import time.
- Termux-compatible: pure Python, no platform-specific paths.
- Owner-gated actions are preserved as data, never executed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, asdict
from datetime import datetime, timezone
from typing import Any


# Risk classes recognised by the JARVIS Prime runtime contract.
# RC0 = read-only / docs / no runtime impact.
# RC1 = local code change, reversible, no shared-state effect.
# RC2 = shared runtime files or cross-lane impact.
# RC3 = owner-gated by policy (deploy adjacent, credential adjacent, public-facing).
# RC4 = destructive / irreversible / regulated surface.
VALID_RISK_CLASSES = ("RC0", "RC1", "RC2", "RC3", "RC4")


def _utcnow_iso() -> str:
    """Timezone-aware UTC timestamp in ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkPacketValidationFinding:
    """One validation issue against a WorkPacket.

    `field` is the packet field name (or "" for whole-packet findings).
    `code` is a short machine-readable tag (e.g. "missing", "invalid",
    "out_of_range"). `message` is a human-readable explanation.
    """

    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass
class WorkPacket:
    """Standard work packet handed to a JARVIS Prime worker.

    The packet is data, not behaviour. Owner-gated actions named in
    `owner_gated_actions` are recorded here so an owner can review them;
    nothing in this module executes them.
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
    created_at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict representation of the packet."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPacket":
        """Build a WorkPacket from a dict, ignoring unknown keys.

        Missing keys fall back to dataclass defaults. Confidence is
        clamped into [0.0, 1.0] here so a round-trip from a noisy source
        cannot smuggle an out-of-range value past validate().
        """
        if not isinstance(data, dict):
            raise TypeError("WorkPacket.from_dict expects a dict")

        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for name in known:
            if name in data:
                kwargs[name] = data[name]

        if "confidence" in kwargs:
            try:
                conf = float(kwargs["confidence"])
            except (TypeError, ValueError):
                conf = 0.0
            kwargs["confidence"] = max(0.0, min(1.0, conf))

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
            if list_field in kwargs and kwargs[list_field] is None:
                kwargs[list_field] = []

        return cls(**kwargs)

    def validate(self) -> list[WorkPacketValidationFinding]:
        """Return a list of validation findings. Empty list means valid.

        Required-but-missing fields, invalid risk class, and an
        out-of-range confidence are all reported as findings. The packet
        is not mutated.
        """
        findings: list[WorkPacketValidationFinding] = []

        required_string_fields = (
            ("mission", "mission is required"),
            ("repo_root", "repo_root is required"),
            ("branch", "branch is required"),
            ("risk_class", "risk_class is required"),
            ("rollback_plan", "rollback_plan is required"),
        )
        for name, message in required_string_fields:
            value = getattr(self, name, "")
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    WorkPacketValidationFinding(
                        field=name, code="missing", message=message
                    )
                )

        if not isinstance(self.acceptance_criteria, list) or not self.acceptance_criteria:
            findings.append(
                WorkPacketValidationFinding(
                    field="acceptance_criteria",
                    code="missing",
                    message="acceptance_criteria must contain at least one item",
                )
            )

        if isinstance(self.risk_class, str) and self.risk_class.strip():
            if self.risk_class not in VALID_RISK_CLASSES:
                findings.append(
                    WorkPacketValidationFinding(
                        field="risk_class",
                        code="invalid",
                        message=(
                            "risk_class must be one of "
                            + ", ".join(VALID_RISK_CLASSES)
                        ),
                    )
                )

        try:
            conf = float(self.confidence)
        except (TypeError, ValueError):
            findings.append(
                WorkPacketValidationFinding(
                    field="confidence",
                    code="invalid",
                    message="confidence must be a number between 0.0 and 1.0",
                )
            )
        else:
            if conf < 0.0 or conf > 1.0:
                findings.append(
                    WorkPacketValidationFinding(
                        field="confidence",
                        code="out_of_range",
                        message="confidence must be between 0.0 and 1.0 inclusive",
                    )
                )

        if self.owner_gated_actions and not self.owner_authorization_phrase.strip():
            findings.append(
                WorkPacketValidationFinding(
                    field="owner_authorization_phrase",
                    code="missing",
                    message=(
                        "owner_gated_actions present but owner_authorization_phrase "
                        "is empty; the exact phrase 'Yes, with authorization.' is required"
                    ),
                )
            )

        return findings


__all__ = [
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
