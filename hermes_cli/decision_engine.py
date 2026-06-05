"""Unified decision engine — the single ``auto`` / ``ask`` / ``refuse`` verdict.

Sprint 2 of the Hermes 10/10 program. Today, safety decisions are spread
across several surfaces:

* :class:`hermes_cli.approval_policy.Decision` (``ALLOW`` / ``CONFIRM`` / ``DENY``)
* :class:`enterprise.policy.Risk` (``LOW`` / ``MEDIUM`` / ``HIGH``)
* :class:`enterprise.judge.JudgeVerdict` (schema / policy / jury checks)
* merge-time gates in :mod:`hermes_cli.merge_engine`

The phone cockpit cannot render *the* verdict because there is no single
verdict. This module supplies the canonical :class:`DecisionVerdict`,
:class:`DecisionInput`, the eight :class:`ReasonCode` values, and one
:func:`merge_decision_inputs` coalescer with explicit tier-merge rules.

**This module is additive.** It does not replace or weaken any existing gate.
Call sites (orchestrator, publisher, approval API) adopt it incrementally by
mapping their existing signals into :class:`DecisionInput` collectors and
calling :func:`merge_decision_inputs`. The merge rules below are the contract:

* Any ``refuse`` input makes the verdict ``refuse``.
* Any ``ask`` input makes the verdict ``ask`` unless a ``refuse`` exists.
* ``auto`` is valid only if **every** input is ``auto`` *and* no required
  collector is missing.
* No inputs at all → ``ask`` (fail-safe; the engine refuses to assume ``auto``).
* A missing required collector → ``ask`` (``UNKNOWN_RISK``).
* Secrets detected → ``refuse`` until redacted (``SECRET_DETECTED``).
* Remote execution is never ``auto`` (``REMOTE_EXECUTION``).
* Live publish is never ``auto``; without both allowlists it is ``refuse``
  (``LIVE_PUBLISH``).
* Protected-path mutation is ``ask`` or ``refuse`` by path (``PROTECTED_PATH``).
* Failed validation is ``refuse`` unless an override is explicitly allowed,
  in which case ``ask`` (``VALIDATION_FAILED``).

Verdicts serialize through :meth:`DecisionVerdict.to_redacted_dict`, which
runs every human-readable string through :func:`hermes_cli.secrets_policy.redact`
so a verdict can be persisted to the audit ledger or sent to the cockpit
without leaking credentials.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

__all__ = [
    "DecisionTier",
    "ReasonCode",
    "DecisionInput",
    "DecisionVerdict",
    "merge_decision_inputs",
    "secret_input",
    "protected_path_input",
    "validation_input",
    "remote_execution_input",
    "live_publish_input",
    "owner_gate_input",
    "policy_input",
    "from_approval_decision",
]


class DecisionTier(str, enum.Enum):
    """The single verdict the cockpit renders. Ordered by severity."""

    AUTO = "auto"
    ASK = "ask"
    REFUSE = "refuse"


# Severity order for coalescing — higher index wins.
_TIER_RANK: dict[DecisionTier, int] = {
    DecisionTier.AUTO: 0,
    DecisionTier.ASK: 1,
    DecisionTier.REFUSE: 2,
}


class ReasonCode(str, enum.Enum):
    """The canonical reasons a verdict is not ``auto``.

    Exactly the eight codes named in the Sprint 2 specification.
    """

    PROTECTED_PATH = "protected_path"
    SECRET_DETECTED = "secret_detected"
    REMOTE_EXECUTION = "remote_execution"
    LIVE_PUBLISH = "live_publish"
    VALIDATION_FAILED = "validation_failed"
    UNKNOWN_RISK = "unknown_risk"
    OWNER_REQUIRED = "owner_required"
    POLICY_REFUSAL = "policy_refusal"


# Reasons that, on an ``ask`` verdict, require the exact owner phrase rather
# than a one-tap confirmation. These are the irreversible / external / remote
# surfaces called out in the plan's owner-gate policy.
_OWNER_PHRASE_REASONS: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.OWNER_REQUIRED,
        ReasonCode.LIVE_PUBLISH,
        ReasonCode.REMOTE_EXECUTION,
        ReasonCode.PROTECTED_PATH,
    }
)


@dataclass(frozen=True)
class DecisionInput:
    """One signal feeding the engine.

    ``reason`` is ``None`` for a neutral / ``auto`` input. ``detail`` is a
    short human string; it is redacted at the serialization boundary, never
    stored raw in a sink.
    """

    source: str
    tier: DecisionTier
    reason: Optional[ReasonCode] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.tier, DecisionTier):  # pragma: no cover - guard
            raise TypeError(f"tier must be DecisionTier, got {type(self.tier)!r}")
        if self.tier is not DecisionTier.AUTO and self.reason is None:
            raise ValueError(
                f"non-auto input from {self.source!r} must carry a ReasonCode"
            )


@dataclass(frozen=True)
class DecisionVerdict:
    """The single verdict. Mirrors the Sprint 1 ``DecisionVerdict`` contract."""

    id: str
    tier: DecisionTier
    action_type: str
    rationale: str
    inputs: tuple[DecisionInput, ...]
    reason_codes: tuple[ReasonCode, ...]
    required_owner_phrase: Optional[str] = None
    allowed_until: Optional[datetime] = None
    audit_id: Optional[str] = None

    @property
    def is_auto(self) -> bool:
        return self.tier is DecisionTier.AUTO

    @property
    def is_refuse(self) -> bool:
        return self.tier is DecisionTier.REFUSE

    @property
    def needs_owner_phrase(self) -> bool:
        return bool(self.required_owner_phrase)

    def to_redacted_dict(self) -> dict[str, object]:
        """Serialize with every human string passed through the redactor.

        Imported lazily so the engine stays cheap to import and free of any
        import cycle through the secrets module.
        """

        from hermes_cli.secrets_policy import redact

        return {
            "id": self.id,
            "tier": self.tier.value,
            "action_type": self.action_type,
            "rationale": redact(self.rationale),
            "reason_codes": [r.value for r in self.reason_codes],
            "inputs": [
                {
                    "source": i.source,
                    "tier": i.tier.value,
                    "reason": i.reason.value if i.reason else None,
                    "detail": redact(i.detail),
                }
                for i in self.inputs
            ],
            "required_owner_phrase": self.required_owner_phrase,
            "allowed_until": (
                self.allowed_until.isoformat() if self.allowed_until else None
            ),
            "audit_id": self.audit_id,
        }

    def __str__(self) -> str:  # pragma: no cover - convenience
        from hermes_cli.secrets_policy import redact

        return f"<DecisionVerdict {self.id} {self.tier.value} {self.action_type}: {redact(self.rationale)}>"


def _coalesce_tier(inputs: Sequence[DecisionInput]) -> DecisionTier:
    """``refuse`` wins, then ``ask``; ``auto`` only when all inputs are auto."""

    if not inputs:
        return DecisionTier.ASK  # fail-safe: never assume auto with no evidence
    return max((i.tier for i in inputs), key=lambda t: _TIER_RANK[t])


def merge_decision_inputs(
    action_type: str,
    inputs: Iterable[DecisionInput],
    *,
    required_sources: Iterable[str] = (),
    owner_phrase: str = AUTHORIZATION_PHRASE,
    allowed_until: Optional[datetime] = None,
    audit_id: Optional[str] = None,
) -> DecisionVerdict:
    """Coalesce ``inputs`` into a single :class:`DecisionVerdict`.

    Any ``source`` named in ``required_sources`` that is not present among
    ``inputs`` becomes an injected ``ask`` input with ``UNKNOWN_RISK`` — a
    missing required collector is never silently treated as ``auto``.
    """

    collected: list[DecisionInput] = list(inputs)

    present = {i.source for i in collected}
    for source in required_sources:
        if source not in present:
            collected.append(
                DecisionInput(
                    source=source,
                    tier=DecisionTier.ASK,
                    reason=ReasonCode.UNKNOWN_RISK,
                    detail=f"required decision input {source!r} was not provided",
                )
            )

    tier = _coalesce_tier(collected)

    # The inputs that actually drove the verdict (those at the final tier).
    dominant = [i for i in collected if i.tier is tier]

    # Reason codes: unique, ordered by tier severity then first appearance.
    reason_codes: list[ReasonCode] = []
    for i in sorted(collected, key=lambda x: -_TIER_RANK[x.tier]):
        if i.reason is not None and i.reason not in reason_codes:
            reason_codes.append(i.reason)

    if dominant:
        rationale = "; ".join(
            f"{i.source}: {i.detail or (i.reason.value if i.reason else 'ok')}"
            for i in dominant
        )
    else:  # all-auto, no detail
        rationale = f"{action_type}: all inputs auto"

    required_owner_phrase: Optional[str] = None
    if tier is DecisionTier.ASK and any(
        i.reason in _OWNER_PHRASE_REASONS for i in collected
    ):
        required_owner_phrase = owner_phrase

    return DecisionVerdict(
        id=f"dv_{uuid.uuid4().hex[:12]}",
        tier=tier,
        action_type=action_type,
        rationale=rationale,
        inputs=tuple(collected),
        reason_codes=tuple(reason_codes),
        required_owner_phrase=required_owner_phrase,
        allowed_until=allowed_until,
        audit_id=audit_id,
    )


# ---------------------------------------------------------------------------
# Collectors — encode the plan's per-signal rules so call sites can't get
# the tiering wrong. Each returns a single DecisionInput.
# ---------------------------------------------------------------------------


def secret_input(findings: Sequence[object], *, source: str = "secrets") -> DecisionInput:
    """``refuse`` if any secret finding exists, else ``auto``.

    ``findings`` is any sequence (e.g. ``secrets_policy.scan_diff`` output);
    only its emptiness is read here, so no secret value is copied in.
    """

    if findings:
        return DecisionInput(
            source=source,
            tier=DecisionTier.REFUSE,
            reason=ReasonCode.SECRET_DETECTED,
            detail=f"{len(findings)} secret finding(s) must be redacted before proceeding",
        )
    return DecisionInput(source=source, tier=DecisionTier.AUTO, detail="no secrets detected")


def protected_path_input(
    paths: Sequence[str], *, hard: bool = False, source: str = "protected_paths"
) -> DecisionInput:
    """``auto`` when ``paths`` is empty; otherwise ``refuse`` if ``hard`` else ``ask``."""

    if not paths:
        return DecisionInput(source=source, tier=DecisionTier.AUTO, detail="no protected paths touched")
    tier = DecisionTier.REFUSE if hard else DecisionTier.ASK
    return DecisionInput(
        source=source,
        tier=tier,
        reason=ReasonCode.PROTECTED_PATH,
        detail=f"protected paths touched: {', '.join(paths[:8])}",
    )


def validation_input(
    passed: bool, *, override_allowed: bool = False, source: str = "validation"
) -> DecisionInput:
    """``auto`` when passed; failed → ``refuse`` (or ``ask`` if override allowed)."""

    if passed:
        return DecisionInput(source=source, tier=DecisionTier.AUTO, detail="validation passed")
    tier = DecisionTier.ASK if override_allowed else DecisionTier.REFUSE
    return DecisionInput(
        source=source,
        tier=tier,
        reason=ReasonCode.VALIDATION_FAILED,
        detail="validation gate failed",
    )


def remote_execution_input(requested: bool, *, source: str = "remote_execution") -> DecisionInput:
    """Remote execution is never ``auto``. ``auto`` only when not requested."""

    if not requested:
        return DecisionInput(source=source, tier=DecisionTier.AUTO, detail="no remote execution")
    return DecisionInput(
        source=source,
        tier=DecisionTier.ASK,
        reason=ReasonCode.REMOTE_EXECUTION,
        detail="remote execution requires owner authorization",
    )


def live_publish_input(
    *, repo_allowlisted: bool, action_allowlisted: bool, source: str = "live_publish"
) -> DecisionInput:
    """Live publish is never ``auto``; ``refuse`` unless both allowlists pass, else ``ask``."""

    if not (repo_allowlisted and action_allowlisted):
        missing = []
        if not repo_allowlisted:
            missing.append("repo not allowlisted")
        if not action_allowlisted:
            missing.append("action not allowlisted")
        return DecisionInput(
            source=source,
            tier=DecisionTier.REFUSE,
            reason=ReasonCode.LIVE_PUBLISH,
            detail="; ".join(missing),
        )
    return DecisionInput(
        source=source,
        tier=DecisionTier.ASK,
        reason=ReasonCode.LIVE_PUBLISH,
        detail="live publish allowlisted; owner approval required",
    )


def owner_gate_input(required: bool, *, action: str = "", source: str = "owner_gate") -> DecisionInput:
    """``ask`` (owner phrase) when an owner-gated action is requested, else ``auto``."""

    if not required:
        return DecisionInput(source=source, tier=DecisionTier.AUTO, detail="not owner-gated")
    return DecisionInput(
        source=source,
        tier=DecisionTier.ASK,
        reason=ReasonCode.OWNER_REQUIRED,
        detail=f"owner-gated action{f': {action}' if action else ''}",
    )


def policy_input(
    tier: DecisionTier, detail: str, *, source: str = "policy"
) -> DecisionInput:
    """Passthrough for an upstream policy/judge result already mapped to a tier."""

    reason = None if tier is DecisionTier.AUTO else ReasonCode.POLICY_REFUSAL
    return DecisionInput(source=source, tier=tier, reason=reason, detail=detail)


# Map the legacy approval_policy.Decision values onto the canonical tier so
# existing call sites can feed the engine without rewriting their logic.
_APPROVAL_DECISION_TO_TIER: dict[str, DecisionTier] = {
    "allow": DecisionTier.AUTO,
    "confirm": DecisionTier.ASK,
    "deny": DecisionTier.REFUSE,
}


def from_approval_decision(
    decision: object, reason: str = "", *, source: str = "approval_policy"
) -> DecisionInput:
    """Adapt an ``approval_policy.Decision`` (or its ``.value``) to a DecisionInput."""

    value = getattr(decision, "value", decision)
    tier = _APPROVAL_DECISION_TO_TIER.get(str(value).lower())
    if tier is None:  # pragma: no cover - defensive
        tier = DecisionTier.ASK
    reason_code = None if tier is DecisionTier.AUTO else ReasonCode.POLICY_REFUSAL
    return DecisionInput(source=source, tier=tier, reason=reason_code, detail=reason)
