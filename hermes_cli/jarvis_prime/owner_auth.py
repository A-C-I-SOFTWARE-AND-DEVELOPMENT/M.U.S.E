"""Owner-authorization gate for muse

Owner-gated actions require an exact phrase before execution per
``docs/jarvis-prime-operating-system.md`` § Owner Gates and
``skills/jarvis-prime/SKILL.md``. This module enforces the phrase
literally — minor variations ("yes with authorization", "yes - with
authorization") do not authorize.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


# Exact phrase from the spec. Do not change without editing the docs.
AUTHORIZATION_PHRASE: str = "Yes, with authorization."


# Canonical set of owner-gated action categories — kept in sync with
# the spec doc § Owner Gates. The set is used by the owner_approval
# gate and ``OwnerAuth.is_gated_action``.
#
# Repository merge approval (``main_branch_merge``) is NOT in this set:
# it is governed by the automated LaunchGate policy — see
# ``docs/launch/AUTOMATED_MERGE_POLICY.md``.
OWNER_GATED_ACTIONS: frozenset[str] = frozenset({
    "spend_money",
    "post_publicly",
    "create_third_party_account",
    "oauth_change",
    "credential_change",
    "production_deploy",
    "dns_change",
    "force_push",
    "package_publish",
    "app_store_submission",
    "delete_recovered_sources",
    "modify_secrets",
    "change_default_active_agents",
    "registry_mutation",
    "regulated_claim",  # legal, compliance, security, health, financial
    # Grant a standing, scoped, revocable autonomy charter to the research
    # fabric (see hermes_cli/jarvis_prime/research_fabric/charter.py). The
    # agent can never mint its own charter — only the owner, via the
    # nonce-bound challenge, can. This is the sole gate that unlocks the
    # bounded-autonomy exception (Constitution C33).
    "grant_autonomy_charter",
})


@dataclass
class OwnerGate:
    """One pending owner-gated action awaiting authorization."""

    action: str
    risk_class: str  # RC0..RC4
    rationale: str
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    authorized_at: Optional[datetime] = None
    authorization_text: Optional[str] = None

    @property
    def authorized(self) -> bool:
        return self.authorized_at is not None


@dataclass
class OwnerAuth:
    """Captures and validates owner authorization for gated actions.

    The instance keeps a small audit trail of authorization grants
    that the runtime can persist to memory (``MemoryRecord`` API) or
    to the decision ledger.
    """

    pending: list[OwnerGate] = field(default_factory=list)
    history: list[OwnerGate] = field(default_factory=list)

    @staticmethod
    def is_gated_action(action: str) -> bool:
        return action in OWNER_GATED_ACTIONS

    def request(self, action: str, risk_class: str = "RC2", rationale: str = "") -> OwnerGate:
        if action not in OWNER_GATED_ACTIONS:
            raise ValueError(f"{action!r} is not in OWNER_GATED_ACTIONS — extend the spec first")
        gate = OwnerGate(action=action, risk_class=risk_class, rationale=rationale)
        self.pending.append(gate)
        return gate

    def authorize(self, phrase: str, action: Optional[str] = None) -> list[OwnerGate]:
        """Authorize one or all pending gates with the exact phrase.

        Returns the list of gates that just became authorized.
        Approximate phrases ("yes with authorization", "approved",
        "go ahead") do NOT authorize — the contract requires the
        exact constant.
        """

        if phrase.strip() != AUTHORIZATION_PHRASE:
            return []

        granted: list[OwnerGate] = []
        remaining: list[OwnerGate] = []
        now = datetime.now(timezone.utc)
        for gate in self.pending:
            if action is None or gate.action == action:
                gate.authorized_at = now
                gate.authorization_text = phrase.strip()
                granted.append(gate)
                self.history.append(gate)
            else:
                remaining.append(gate)
        self.pending = remaining
        return granted

    def pending_actions(self) -> list[str]:
        return [g.action for g in self.pending]

    def revoke(self, action: str) -> int:
        """Revoke a previously-granted authorization. Returns count revoked."""

        revoked = 0
        for gate in list(self.history):
            if gate.action == action and gate.authorized:
                gate.authorized_at = None
                gate.authorization_text = None
                revoked += 1
        return revoked

    # ------------------------------------------------------------------
    # Challenge-bound authorization (strict evidence mode)
    #
    # The static phrase above is necessary but not sufficient for strict
    # guardrails: a replayed "Yes, with authorization." carries no binding to
    # *which* action the owner approved or *when*. A challenge mints a one-time
    # nonce; the owner must echo the phrase *with that nonce*, and a successful
    # response yields a content-addressed grant artifact.
    # ------------------------------------------------------------------

    challenges: dict[str, "OwnerAuthorizationChallenge"] = field(default_factory=dict)

    def create_challenge(
        self,
        action: str,
        risk_class: str = "RC3",
        rationale: str = "",
        subject: Optional[str] = None,
        ttl_seconds: int = 600,
        now: Optional[datetime] = None,
    ) -> "OwnerAuthorizationChallenge":
        challenge = create_challenge(
            action,
            risk_class=risk_class,
            rationale=rationale,
            subject=subject,
            ttl_seconds=ttl_seconds,
            now=now,
        )
        self.challenges[challenge.challenge_id] = challenge
        return challenge

    def authorize_challenge(
        self,
        challenge_id: str,
        phrase: str,
        now: Optional[datetime] = None,
    ) -> Optional["OwnerAuthorizationGrant"]:
        challenge = self.challenges.get(challenge_id)
        if challenge is None:
            return None
        grant = authorize_challenge(challenge, phrase, now=now)
        if grant is not None:
            # Record a legacy gate in history for audit parity.
            gate = OwnerGate(
                action=challenge.action,
                risk_class=challenge.risk_class,
                rationale=challenge.rationale,
            )
            gate.authorized_at = datetime.now(timezone.utc)
            gate.authorization_text = challenge.required_phrase
            self.history.append(gate)
            self.pending = [g for g in self.pending if g.action != challenge.action]
            self.challenges.pop(challenge_id, None)
        return grant


# ---------------------------------------------------------------------------
# Challenge / response primitives (also usable statelessly by the CLI)
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class OwnerAuthorizationChallenge:
    """A one-time, nonce-bound owner-authorization challenge."""

    challenge_id: str
    action: str
    risk_class: str
    rationale: str
    subject: str
    nonce: str
    created_at: str
    expires_at: str
    required_phrase: str

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        ref = now or _utc_now()
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        return ref >= expiry

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "action": self.action,
            "risk_class": self.risk_class,
            "rationale": self.rationale,
            "subject": self.subject,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "required_phrase": self.required_phrase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OwnerAuthorizationChallenge":
        return cls(
            challenge_id=str(data["challenge_id"]),
            action=str(data["action"]),
            risk_class=str(data.get("risk_class", "RC3")),
            rationale=str(data.get("rationale", "")),
            subject=str(data.get("subject", "")),
            nonce=str(data["nonce"]),
            created_at=str(data.get("created_at", "")),
            expires_at=str(data.get("expires_at", "")),
            required_phrase=str(data["required_phrase"]),
        )


@dataclass(frozen=True)
class OwnerAuthorizationGrant:
    """Proof that a specific challenge was answered with the exact phrase."""

    challenge_id: str
    action: str
    subject: str
    risk_class: str
    granted_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "action": self.action,
            "subject": self.subject,
            "risk_class": self.risk_class,
            "granted_at": self.granted_at,
        }

    def to_artifact(self):  # type: ignore[no-untyped-def]
        """Emit a content-addressed owner-authorization evidence artifact."""

        from hermes_cli.jarvis_prime.guardrail_evidence import (
            ARTIFACT_OWNER_GRANT,
            EvidenceArtifact,
        )

        return EvidenceArtifact.make(
            ARTIFACT_OWNER_GRANT,
            producer="owner_auth",
            subject=self.subject or self.action,
            payload=self.to_dict(),
        )


def create_challenge(
    action: str,
    risk_class: str = "RC3",
    rationale: str = "",
    subject: Optional[str] = None,
    ttl_seconds: int = 600,
    now: Optional[datetime] = None,
) -> OwnerAuthorizationChallenge:
    """Mint a nonce-bound owner-authorization challenge for ``action``.

    Raises ``ValueError`` if ``action`` is not an owner-gated category, so a
    caller cannot manufacture a challenge for an action outside the spec.
    """

    if action not in OWNER_GATED_ACTIONS:
        raise ValueError(
            f"{action!r} is not in OWNER_GATED_ACTIONS — extend the spec first"
        )
    created = now or _utc_now()
    expires = created + timedelta(seconds=max(1, ttl_seconds))
    # 6-digit zero-padded code, cryptographically random.
    nonce = f"{secrets.randbelow(1_000_000):06d}"
    return OwnerAuthorizationChallenge(
        challenge_id=f"chal_{uuid.uuid4().hex[:16]}",
        action=action,
        risk_class=risk_class,
        rationale=rationale,
        subject=subject or "",
        nonce=nonce,
        created_at=created.isoformat(),
        expires_at=expires.isoformat(),
        required_phrase=f"{AUTHORIZATION_PHRASE} Code: {nonce}",
    )


def authorize_challenge(
    challenge: OwnerAuthorizationChallenge,
    phrase: str,
    now: Optional[datetime] = None,
) -> Optional[OwnerAuthorizationGrant]:
    """Validate ``phrase`` against ``challenge``; return a grant or ``None``.

    The bare static phrase alone never satisfies a challenge — the response must
    echo the exact ``required_phrase`` including the nonce. Expired challenges
    fail closed.
    """

    if challenge.is_expired(now):
        return None
    if phrase.strip() != challenge.required_phrase:
        return None
    return OwnerAuthorizationGrant(
        challenge_id=challenge.challenge_id,
        action=challenge.action,
        subject=challenge.subject,
        risk_class=challenge.risk_class,
        granted_at=(now or _utc_now()).isoformat(),
    )
