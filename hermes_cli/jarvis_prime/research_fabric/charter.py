"""The Autonomy Charter — the bounded envelope that makes auto-apply legal.

Auto-apply collides with Constitution **C28** (no silent self-rewrite) unless it
happens inside an owner-signed, revocable, budgeted **charter** — the narrow
exception carved by **C33**, walled by **C34**. This module owns:

* :data:`HARD_WALL_KINDS` / :data:`PROTECTED_PATH_MARKERS` — changes that may
  **never** auto-apply regardless of any charter (C34). Critically, per the
  Darwin-Gödel-Machine finding (arXiv:2505.22954), this includes the entire
  verifier / eval / monitor / ledger harness — the agent must never gain write
  access to the thing that judges it.
* :class:`AutonomyCharter` — a scoped grant (allowed kinds, risk-band ceiling,
  per-window budget, expiry, revocation), bound to the owner grant that minted it.
* :class:`CharterBook` — JSONL persistence + active-charter lookup + budget count.

A charter can only be minted from an :class:`OwnerAuthorizationGrant` for the
``grant_autonomy_charter`` owner-gated action (nonce-bound challenge in
``owner_auth``). The agent cannot mint its own charter (blocks C23 escalation).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger, hermes_home
from hermes_cli.jarvis_prime.owner_auth import OwnerAuthorizationGrant
from hermes_cli.jarvis_prime.self_update import ProposalKind

# ---------------------------------------------------------------------------
# The inviolable hard wall (C34)
# ---------------------------------------------------------------------------

# Proposal kinds that may NEVER auto-apply, even with an active charter.
HARD_WALL_KINDS: frozenset[ProposalKind] = frozenset(
    {
        ProposalKind.SELF_RUNTIME_UPDATE,
        ProposalKind.GATE_UPDATE,
        ProposalKind.MODEL_REGISTRY_UPDATE,
        ProposalKind.ROUTING_RULE_UPDATE,
        ProposalKind.AGENT_UPDATE,
        ProposalKind.NEW_AGENT,
    }
)

# Path substrings that are off-limits to auto-apply. owner-auth / constitution /
# the verifier-eval-monitor-ledger harness are NOT ProposalKinds, so a kind-only
# wall would miss them — this catches them by path.
PROTECTED_PATH_MARKERS: tuple[str, ...] = (
    "hermes_cli/jarvis_prime/owner_auth.py",
    "hermes_cli/jarvis_prime/gates.py",
    "hermes_cli/jarvis_prime/constitution.py",
    "hermes_cli/jarvis_prime/capability_wall.py",
    "hermes_cli/jarvis_prime/guardrail_evidence.py",
    "hermes_cli/jarvis_prime/self_update.py",
    "hermes_cli/jarvis_prime/research_fabric/validators.py",
    "hermes_cli/jarvis_prime/research_fabric/charter.py",
    "hermes_cli/jarvis_prime/research_fabric/controller.py",
    "hermes_cli/jarvis_prime/research_fabric/monitor.py",
    "hermes_cli/jarvis_prime/research_fabric/verifier",
    "docs/jarvis-constitution.md",
    "config/model-catalog.yaml",
    "model-routing-policy",
)

# Kinds that the default envelope is allowed to auto-apply (RC0-RC1 text).
DEFAULT_ALLOWED_KINDS: tuple[str, ...] = (
    ProposalKind.SKILL_UPDATE.value,
    ProposalKind.NEW_SKILL.value,
)

# Risk-band ceiling order; RC4 is never permitted for auto-apply.
_RC_ORDER = ("RC0", "RC1", "RC2", "RC3", "RC4")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_hard_walled(kind: ProposalKind, target_path: str) -> tuple[bool, str]:
    """Return (blocked, reason). True ⇒ may never auto-apply (C34)."""

    if kind in HARD_WALL_KINDS:
        return True, f"kind {kind.value} is hard-walled (C34)"
    norm = (target_path or "").replace("\\", "/")
    for marker in PROTECTED_PATH_MARKERS:
        if marker in norm:
            return True, f"path matches protected marker {marker!r} (C34)"
    return False, ""


def _rc_le(a: str, b: str) -> bool:
    """Return True if risk band ``a`` <= ceiling ``b``."""

    try:
        return _RC_ORDER.index(a) <= _RC_ORDER.index(b)
    except ValueError:
        return False


@dataclass(frozen=True)
class AutonomyCharter:
    charter_id: str
    allowed_kinds: tuple[str, ...]
    risk_band_ceiling: str
    per_window_budget: int
    window_seconds: int
    created_at: str
    expires_at: str
    owner_grant_id: str
    revoked_at: Optional[str] = None

    def is_active(self, now: Optional[datetime] = None) -> bool:
        ref = now or _utc_now()
        if self.revoked_at:
            return False
        try:
            return ref < datetime.fromisoformat(self.expires_at)
        except ValueError:
            return False

    def permits(self, kind: ProposalKind, risk_class: str) -> tuple[bool, str]:
        """Whether this charter's scope covers ``(kind, risk_class)``."""

        if kind in HARD_WALL_KINDS:
            return False, f"kind {kind.value} is hard-walled"
        if risk_class == "RC4" or self.risk_band_ceiling == "RC4":
            return False, "RC4 is never auto-appliable"
        if not _rc_le(risk_class, self.risk_band_ceiling):
            return False, f"risk {risk_class} exceeds ceiling {self.risk_band_ceiling}"
        if kind.value not in self.allowed_kinds:
            return False, f"kind {kind.value} not in charter scope {self.allowed_kinds}"
        return True, "within charter scope"

    def to_dict(self) -> dict[str, Any]:
        return {
            "charter_id": self.charter_id,
            "allowed_kinds": list(self.allowed_kinds),
            "risk_band_ceiling": self.risk_band_ceiling,
            "per_window_budget": self.per_window_budget,
            "window_seconds": self.window_seconds,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "owner_grant_id": self.owner_grant_id,
            "revoked_at": self.revoked_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutonomyCharter":
        return cls(
            charter_id=str(data["charter_id"]),
            allowed_kinds=tuple(data.get("allowed_kinds", ())),
            risk_band_ceiling=str(data.get("risk_band_ceiling", "RC1")),
            per_window_budget=int(data.get("per_window_budget", 0)),
            window_seconds=int(data.get("window_seconds", 86400)),
            created_at=str(data.get("created_at", "")),
            expires_at=str(data.get("expires_at", "")),
            owner_grant_id=str(data.get("owner_grant_id", "")),
            revoked_at=data.get("revoked_at"),
        )


class CharterRejected(ValueError):
    """Raised when a charter grant request violates the hard wall."""


@dataclass
class CharterBook:
    path: Optional[Path] = None
    charters: list[AutonomyCharter] = field(default_factory=list)

    @staticmethod
    def default_path() -> Path:
        return hermes_home() / "jarvis_prime" / "autonomy_charters.jsonl"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "CharterBook":
        p = Path(path) if path is not None else cls.default_path()
        charters: list[AutonomyCharter] = []
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    charters.append(AutonomyCharter.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        return cls(path=p, charters=charters)

    def save(self) -> Path:
        p = self.path or self.default_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for c in self.charters:
                fh.write(json.dumps(c.to_dict(), sort_keys=True))
                fh.write("\n")
        os.replace(tmp, p)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        return p

    def grant(
        self,
        *,
        allowed_kinds: tuple[str, ...],
        risk_band_ceiling: str,
        per_window_budget: int,
        window_seconds: int,
        ttl_seconds: int,
        grant: OwnerAuthorizationGrant,
        now: Optional[datetime] = None,
        persist: bool = True,
    ) -> AutonomyCharter:
        """Mint a charter from a verified owner grant. Rejects hard-wall kinds."""

        if grant.action != "grant_autonomy_charter":
            raise CharterRejected(
                f"owner grant is for {grant.action!r}, not grant_autonomy_charter"
            )
        if risk_band_ceiling == "RC4":
            raise CharterRejected("RC4 ceiling is never permitted")
        # Reject any hard-walled kind up front.
        for kv in allowed_kinds:
            try:
                kind = ProposalKind(kv)
            except ValueError as exc:
                raise CharterRejected(f"unknown proposal kind {kv!r}") from exc
            if kind in HARD_WALL_KINDS:
                raise CharterRejected(
                    f"kind {kv!r} is hard-walled and cannot be chartered (C34)"
                )
        created = now or _utc_now()
        charter = AutonomyCharter(
            charter_id=f"charter_{uuid.uuid4().hex[:16]}",
            allowed_kinds=tuple(allowed_kinds),
            risk_band_ceiling=risk_band_ceiling,
            per_window_budget=int(per_window_budget),
            window_seconds=int(window_seconds),
            created_at=created.isoformat(),
            expires_at=(created + timedelta(seconds=max(1, ttl_seconds))).isoformat(),
            owner_grant_id=grant.challenge_id,
        )
        self.charters.append(charter)
        if persist:
            self.save()
        return charter

    def revoke(self, charter_id: str, *, persist: bool = True) -> bool:
        now = _utc_now().isoformat()
        changed = False
        for i, c in enumerate(self.charters):
            if c.charter_id == charter_id and c.revoked_at is None:
                self.charters[i] = AutonomyCharter(
                    **{**c.to_dict(), "revoked_at": now}  # ty: ignore[invalid-argument-type]  # round-trip of to_dict
                )
                changed = True
        if changed and persist:
            self.save()
        return changed

    def active(self, now: Optional[datetime] = None) -> Optional[AutonomyCharter]:
        ref = now or _utc_now()
        live = [c for c in self.charters if c.is_active(ref)]
        if not live:
            return None
        # Most recently created active charter wins.
        return sorted(live, key=lambda c: c.created_at)[-1]

    def auto_applies_in_window(
        self,
        charter: AutonomyCharter,
        ledger: GuardrailLedger,
        now: Optional[datetime] = None,
    ) -> int:
        """Count ``auto_apply`` ledger records for this charter in its window."""

        ref = now or _utc_now()
        window_start = ref - timedelta(seconds=charter.window_seconds)
        count = 0
        for rec in ledger.read_all():
            if rec.kind != "auto_apply":
                continue
            if rec.payload.get("charter_id") != charter.charter_id:
                continue
            try:
                ts = datetime.fromisoformat(rec.created_at)
            except ValueError:
                continue
            if ts >= window_start:
                count += 1
        return count


__all__ = [
    "HARD_WALL_KINDS",
    "PROTECTED_PATH_MARKERS",
    "DEFAULT_ALLOWED_KINDS",
    "is_hard_walled",
    "AutonomyCharter",
    "CharterBook",
    "CharterRejected",
]
