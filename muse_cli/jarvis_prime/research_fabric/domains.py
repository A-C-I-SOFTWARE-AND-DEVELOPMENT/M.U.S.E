"""Plane 4 — cross-domain generalization registry.

The "fit any role" north star with an honest gate: a domain may be admitted for
*autonomous* improvement **only if it brings a cheap, hard-to-game verifier**
(the lesson of the entire AlphaZero/AlphaFold research base). Domains without a
real verifier may be registered for *supervised, owner-gated* work only — never
autonomous auto-apply.

This keeps "fit any role" truthful: autonomy expands exactly as fast as
trustworthy verifiers appear, not faster.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Domain:
    key: str
    description: str
    # "executable" verifier (tests/op-count) | "none" (supervised + owner-gated only)
    verifier_kind: str
    lane: str

    @property
    def has_verifier(self) -> bool:
        return self.verifier_kind != "none"

    @property
    def autonomy_eligible(self) -> bool:
        """Autonomous auto-apply is permitted only with a real verifier."""

        return self.has_verifier


_DOMAINS: tuple[Domain, ...] = (
    Domain(
        key="algorithms",
        description="Single-function algorithm tasks; op-count + held-out correctness.",
        verifier_kind="executable",
        lane="algorithms",
    ),
    Domain(
        key="swe_local",
        description="Repo-level changes graded by the repo's real test command.",
        verifier_kind="executable",
        lane="software_development",
    ),
    Domain(
        key="prose",
        description="Docs/explanations — no executable ground truth.",
        verifier_kind="none",
        lane="communication",
    ),
)

_BY_KEY = {d.key: d for d in _DOMAINS}


def domains() -> tuple[Domain, ...]:
    return _DOMAINS


def get_domain(key: str) -> Optional[Domain]:
    return _BY_KEY.get(key)


class DomainNotAutonomous(ValueError):
    """Raised when autonomy is requested for a domain without a verifier."""


def admit_for_autonomy(key: str) -> Domain:
    """Return the domain if it is autonomy-eligible, else refuse (fail-closed)."""

    domain = _BY_KEY.get(key)
    if domain is None:
        raise DomainNotAutonomous(f"unknown domain {key!r}")
    if not domain.autonomy_eligible:
        raise DomainNotAutonomous(
            f"domain {key!r} has no executable verifier — supervised + owner-gated only"
        )
    return domain


__all__ = [
    "Domain",
    "domains",
    "get_domain",
    "admit_for_autonomy",
    "DomainNotAutonomous",
]
