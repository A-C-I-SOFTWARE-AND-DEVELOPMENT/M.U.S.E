"""Lightweight model-router stub used by the orchestrator controller.

The orchestrator asks the router *"which profile/model should handle
this phase for a job in mode X?"* and the router returns a decision
record.  The real router will look at config, cost budgets, latency
requirements, and recent ledger entries; the stub here returns a
deterministic mapping good enough for tests and for the safe-by-default
controller.

TODO:
    * Read routing rules from ``~/.hermes/config.yaml`` under
      ``orchestration.routing``.
    * Honor per-job budget overrides written by the planning phase.
    * Surface a ``/model-router explain`` integration (currently lives
      in ``hermes_cli.orchestrator``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoutingDecision:
    """One routing choice — returned per (job, phase) lookup."""

    profile: str
    model: str
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "model": self.model,
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }


# Conservative defaults: per phase, what kind of profile do we ask for.
# These names match the profile vocabulary used elsewhere in Hermes
# (``planner``, ``builder``, ``reviewer``, ``architect``).
_PHASE_PROFILE: dict[str, str] = {
    "intake":         "planner",
    "research":       "planner",
    "planning":       "architect",
    "implementation": "builder",
    "validation":     "reviewer",
    "publish":        "builder",
    "retrospective":  "planner",
}


# Mode-level overrides — review/audit jobs should bias toward reviewer
# profiles even for the planning phase, etc.
_MODE_OVERRIDES: dict[str, dict[str, str]] = {
    "review":  {"planning": "reviewer", "implementation": "reviewer"},
    "audit":   {"planning": "reviewer", "implementation": "reviewer"},
    "research": {"implementation": "planner"},
}


_DEFAULT_MODEL = "default-profile-model"


def route_for(
    *,
    phase: str,
    mode: str | None = None,
    trusted_local: bool = False,
) -> RoutingDecision:
    """Return the routing decision for a given (phase, mode) pair.

    Stub-quality but stable: tests and the controller can depend on the
    mapping above.  Real config-driven routing is a TODO.
    """
    mode_key = (mode or "").strip().lower()
    profile = _PHASE_PROFILE.get(phase, "planner")
    rationale = f"phase '{phase}' defaults to profile '{profile}'"
    if mode_key in _MODE_OVERRIDES and phase in _MODE_OVERRIDES[mode_key]:
        profile = _MODE_OVERRIDES[mode_key][phase]
        rationale = (
            f"mode '{mode_key}' overrides phase '{phase}' to profile "
            f"'{profile}'"
        )
    metadata: dict[str, Any] = {"trusted_local": bool(trusted_local)}
    if not trusted_local and phase in {"implementation", "publish"}:
        # Untrusted jobs get the most conservative shape.  The
        # orchestrator separately enforces approval gates; this is a
        # routing hint, not a security control.
        metadata["conservative"] = True
    return RoutingDecision(
        profile=profile,
        model=_DEFAULT_MODEL,
        rationale=rationale,
        metadata=metadata,
    )


__all__ = [
    "RoutingDecision",
    "route_for",
]
