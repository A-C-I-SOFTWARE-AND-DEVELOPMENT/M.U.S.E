"""Owner-authorization gate for JARVIS Prime.

Owner-gated actions require an exact phrase before execution per
``docs/jarvis-prime-operating-system.md`` § Owner Gates and
``skills/jarvis-prime/SKILL.md``. This module enforces the phrase
literally — minor variations ("yes with authorization", "yes - with
authorization") do not authorize.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


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
