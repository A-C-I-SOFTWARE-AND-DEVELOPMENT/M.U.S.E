"""M-of-N threshold authorization — the owner phrase, generalized (Vol VI).

When the owner is no longer a single person, the single ceremonial phrase
generalizes to a quorum: M of N named signers must each answer their **own**
nonce-bound challenge with the exact phrase. Every per-signer challenge is
minted by ``owner_auth.create_challenge``, so the exact-phrase + nonce contract
(C10/C11) is inherited verbatim and a 1-of-1 ``QuorumPolicy.solo()`` flow is
byte-identical to today's single-owner challenge.

The multi-sig kill switch is the one action outside ``OWNER_GATED_ACTIONS``
admitted here: ``emergency_stop`` (via ``extra_actions``). It only ever *stops*
the runtime — wiring it to ``JarvisPrime.stop`` is the CLI's job, and only
after the quorum is satisfied.

Expiry fails closed; a signer can answer only their own nonce; duplicate
responses never double-count.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import EvidenceArtifact, GuardrailLedger
from hermes_cli.jarvis_prime.owner_auth import (
    AUTHORIZATION_PHRASE,
    OWNER_GATED_ACTIONS,
    OwnerAuthorizationChallenge,
    OwnerAuthorizationGrant,
    authorize_challenge,
    create_challenge,
)

from . import ARTIFACT_QUORUM_GRANT, KIND_QUORUM_GRANT

KILL_SWITCH_ACTION = "emergency_stop"
# Actions admitted in addition to OWNER_GATED_ACTIONS. emergency_stop is not an
# owner-gated *grant* category (stopping must never require authorization in
# the solo flow); it appears here only so a multi-operator deployment can bind
# the kill switch to a quorum. The owner_auth frozenset is never mutated.
DEFAULT_EXTRA_ACTIONS: frozenset[str] = frozenset({KILL_SWITCH_ACTION})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QuorumPolicy:
    """M-of-N policy: ``threshold`` of the named ``signers`` must grant."""

    threshold: int
    signers: tuple[str, ...]

    @classmethod
    def solo(cls) -> "QuorumPolicy":
        return cls(threshold=1, signers=("owner",))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.threshold < 1:
            errors.append("threshold must be >= 1")
        if not self.signers:
            errors.append("at least one signer is required")
        if any(not s.strip() for s in self.signers):
            errors.append("signer ids must be non-empty")
        if len(set(self.signers)) != len(self.signers):
            errors.append("signer ids must be unique")
        if self.threshold > len(self.signers):
            errors.append("threshold cannot exceed the number of signers")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {"threshold": self.threshold, "signers": list(self.signers)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuorumPolicy":
        return cls(
            threshold=int(data.get("threshold", 1)),
            signers=tuple(str(s) for s in data.get("signers", ())),
        )


@dataclass
class QuorumChallenge:
    """One in-flight quorum: a nonce-bound challenge per signer, plus grants."""

    quorum_id: str
    action: str
    risk_class: str
    subject: str
    rationale: str
    policy: QuorumPolicy
    per_signer: dict[str, OwnerAuthorizationChallenge]
    grants: dict[str, OwnerAuthorizationGrant] = field(default_factory=dict)
    created_at: str = ""
    expires_at: str = ""

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        ref = now or _utc_now()
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        return ref >= expiry

    def to_dict(self) -> dict[str, Any]:
        return {
            "quorum_id": self.quorum_id,
            "action": self.action,
            "risk_class": self.risk_class,
            "subject": self.subject,
            "rationale": self.rationale,
            "policy": self.policy.to_dict(),
            "per_signer": {s: c.to_dict() for s, c in self.per_signer.items()},
            "grants": {s: g.to_dict() for s, g in self.grants.items()},
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QuorumChallenge":
        grants: dict[str, OwnerAuthorizationGrant] = {}
        for signer, g in dict(data.get("grants", {})).items():
            grants[str(signer)] = OwnerAuthorizationGrant(
                challenge_id=str(g["challenge_id"]),
                action=str(g["action"]),
                subject=str(g.get("subject", "")),
                risk_class=str(g.get("risk_class", "RC3")),
                granted_at=str(g.get("granted_at", "")),
            )
        return cls(
            quorum_id=str(data["quorum_id"]),
            action=str(data["action"]),
            risk_class=str(data.get("risk_class", "RC3")),
            subject=str(data.get("subject", "")),
            rationale=str(data.get("rationale", "")),
            policy=QuorumPolicy.from_dict(dict(data.get("policy", {}))),
            per_signer={
                str(s): OwnerAuthorizationChallenge.from_dict(c)
                for s, c in dict(data.get("per_signer", {})).items()
            },
            grants=grants,
            created_at=str(data.get("created_at", "")),
            expires_at=str(data.get("expires_at", "")),
        )


@dataclass(frozen=True)
class QuorumGrant:
    """Proof that the quorum threshold was met with nonce-bound responses."""

    quorum_id: str
    action: str
    subject: str
    risk_class: str
    threshold: int
    signer_ids: tuple[str, ...]
    granted_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "quorum_id": self.quorum_id,
            "action": self.action,
            "subject": self.subject,
            "risk_class": self.risk_class,
            "threshold": self.threshold,
            "signer_ids": list(self.signer_ids),
            "granted_at": self.granted_at,
        }

    def to_artifact(self) -> EvidenceArtifact:
        return EvidenceArtifact.make(
            ARTIFACT_QUORUM_GRANT,
            producer="quorum_auth",
            subject=self.subject or self.action,
            payload=self.to_dict(),
        )


def _mint_extra_challenge(
    action: str,
    *,
    risk_class: str,
    rationale: str,
    subject: str,
    ttl_seconds: int,
    now: Optional[datetime],
) -> OwnerAuthorizationChallenge:
    """Mint a challenge for an ``extra_actions`` entry (same shape/contract)."""

    import secrets

    created = now or _utc_now()
    expires = created + timedelta(seconds=max(1, ttl_seconds))
    nonce = f"{secrets.randbelow(1_000_000):06d}"
    return OwnerAuthorizationChallenge(
        challenge_id=f"chal_{uuid.uuid4().hex[:16]}",
        action=action,
        risk_class=risk_class,
        rationale=rationale,
        subject=subject,
        nonce=nonce,
        created_at=created.isoformat(),
        expires_at=expires.isoformat(),
        required_phrase=f"{AUTHORIZATION_PHRASE} Code: {nonce}",
    )


def create_quorum_challenge(
    action: str,
    *,
    policy: Optional[QuorumPolicy] = None,
    risk_class: str = "RC3",
    rationale: str = "",
    subject: Optional[str] = None,
    ttl_seconds: int = 600,
    now: Optional[datetime] = None,
    extra_actions: frozenset[str] = DEFAULT_EXTRA_ACTIONS,
) -> QuorumChallenge:
    """Mint one nonce-bound challenge per signer for ``action``.

    Raises ``ValueError`` if the action is outside ``OWNER_GATED_ACTIONS`` and
    not explicitly admitted via ``extra_actions``, or if the policy is invalid.
    """

    if action not in OWNER_GATED_ACTIONS and action not in extra_actions:
        raise ValueError(
            f"{action!r} is not in OWNER_GATED_ACTIONS — extend the spec first"
        )
    quorum_policy = policy or QuorumPolicy.solo()
    errors = quorum_policy.validate()
    if errors:
        raise ValueError("invalid quorum policy: " + "; ".join(errors))

    per_signer: dict[str, OwnerAuthorizationChallenge] = {}
    for signer in quorum_policy.signers:
        if action in OWNER_GATED_ACTIONS:
            challenge = create_challenge(
                action,
                risk_class=risk_class,
                rationale=rationale,
                subject=subject,
                ttl_seconds=ttl_seconds,
                now=now,
            )
        else:
            challenge = _mint_extra_challenge(
                action,
                risk_class=risk_class,
                rationale=rationale,
                subject=subject or "",
                ttl_seconds=ttl_seconds,
                now=now,
            )
        per_signer[signer] = challenge

    created = now or _utc_now()
    expires = created + timedelta(seconds=max(1, ttl_seconds))
    return QuorumChallenge(
        quorum_id=f"quorum_{uuid.uuid4().hex[:16]}",
        action=action,
        risk_class=risk_class,
        subject=subject or "",
        rationale=rationale,
        policy=quorum_policy,
        per_signer=per_signer,
        created_at=created.isoformat(),
        expires_at=expires.isoformat(),
    )


def respond(
    challenge: QuorumChallenge,
    signer_id: str,
    phrase: str,
    now: Optional[datetime] = None,
) -> Optional[OwnerAuthorizationGrant]:
    """Validate one signer's phrase against *their own* nonce challenge."""

    if challenge.is_expired(now):
        return None
    signer_challenge = challenge.per_signer.get(signer_id)
    if signer_challenge is None:
        return None
    grant = authorize_challenge(signer_challenge, phrase, now=now)
    if grant is not None:
        challenge.grants[signer_id] = grant
    return grant


def is_satisfied(challenge: QuorumChallenge) -> bool:
    granting = set(challenge.grants) & set(challenge.policy.signers)
    return len(granting) >= challenge.policy.threshold


def finalize(
    challenge: QuorumChallenge,
    *,
    ledger: Optional[GuardrailLedger] = None,
    now: Optional[datetime] = None,
) -> Optional[QuorumGrant]:
    """Return a :class:`QuorumGrant` iff the quorum is satisfied and live."""

    if challenge.is_expired(now) or not is_satisfied(challenge):
        return None
    grant = QuorumGrant(
        quorum_id=challenge.quorum_id,
        action=challenge.action,
        subject=challenge.subject,
        risk_class=challenge.risk_class,
        threshold=challenge.policy.threshold,
        signer_ids=tuple(sorted(set(challenge.grants) & set(challenge.policy.signers))),
        granted_at=(now or _utc_now()).isoformat(),
    )
    if ledger is not None:
        ledger.append(KIND_QUORUM_GRANT, challenge.quorum_id, grant.to_dict())
    return grant


__all__ = [
    "KILL_SWITCH_ACTION",
    "DEFAULT_EXTRA_ACTIONS",
    "QuorumPolicy",
    "QuorumChallenge",
    "QuorumGrant",
    "create_quorum_challenge",
    "respond",
    "is_satisfied",
    "finalize",
]
