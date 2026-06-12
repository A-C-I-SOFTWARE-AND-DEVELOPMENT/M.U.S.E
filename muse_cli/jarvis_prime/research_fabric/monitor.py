"""Misalignment tripwires for the autonomy loop.

The research is blunt that self-play and self-modifying agents surface
misalignment even with zero external data:

* AZR's "uh-oh moment" — a zero-data self-play model emitted a CoT about
  outsmarting humans (arXiv:2505.03335).
* The Darwin-Gödel-Machine edited its own monitoring code to delete the markers
  its cheat-detector looked for (arXiv:2505.22954).
* Anthropic's *Sycophancy to Subterfuge* — small gameable rewards generalized to
  reward-tampering with track-covering (arXiv:2406.10162).

A tripwire here does one thing: **revoke the active charter and halt auto-apply**,
recording it to the hash-chained ledger. It runs in the protected harness and is
itself hard-walled (C34) so the agent can never edit it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from muse_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from .charter import CharterBook

# Categories of behavior that immediately disqualify a candidate and halt autonomy.
TRIPWIRE_KINDS: tuple[str, ...] = (
    "monitor_tampering",      # tried to edit eval/monitor/ledger/verifier
    "reward_hacking",         # assert True / deleted tests / hard-coded outputs
    "sandbagging",            # deliberate underperformance on eval to dodge detection
    "scope_breakout",         # touched files outside the declared allowed set
    "secret_or_network_use",  # used secrets / network during a self-mod run
    "escalation_attempt",     # asked for higher risk band to widen authority (C23)
)


@dataclass(frozen=True)
class TripwireSignal:
    kind: str
    detail: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "evidence": dict(self.evidence)}


@dataclass(frozen=True)
class MonitorResult:
    tripped: bool
    signals: tuple[TripwireSignal, ...]
    revoked_charters: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tripped": self.tripped,
            "signals": [s.to_dict() for s in self.signals],
            "revoked_charters": list(self.revoked_charters),
        }


class AlignmentMonitor:
    """Evaluates tripwire signals and, on any trip, halts autonomy."""

    def __init__(self, *, ledger: GuardrailLedger, charter_book: CharterBook) -> None:
        self._ledger = ledger
        self._charters = charter_book

    def check(self, signals: list[TripwireSignal]) -> MonitorResult:
        real = [s for s in signals if s.kind in TRIPWIRE_KINDS]
        if not real:
            return MonitorResult(tripped=False, signals=(), revoked_charters=())

        # Revoke every active charter — autonomy is off until the owner re-grants.
        revoked: list[str] = []
        active = self._charters.active()
        # Revoke all live charters, not just the most recent.
        for c in list(self._charters.charters):
            if c.is_active():
                if self._charters.revoke(c.charter_id):
                    revoked.append(c.charter_id)
        self._ledger.append(
            "tripwire",
            active.charter_id if active else "(no-active-charter)",
            {
                "signals": [s.to_dict() for s in real],
                "revoked_charters": revoked,
                "action": "autonomy_halted",
            },
        )
        return MonitorResult(
            tripped=True, signals=tuple(real), revoked_charters=tuple(revoked)
        )


__all__ = ["TRIPWIRE_KINDS", "TripwireSignal", "MonitorResult", "AlignmentMonitor"]
