"""The propose_change flow: blast-radius profile + risk-tiered auth
(Phase 5.2/5.3; the owner gate, mechanized).

Authorization tiers map to risk:
  LOW  -> silent      (ledger only; proceed)
  MED  -> lightweight (an approver callback must return truthy)
  HIGH -> ceremonial  (the approver must return the EXACT phrase
                       "Yes, with authorization." — nothing else,
                       not case-folded, not trimmed of its period)

Every gate result is ledgered; a denial is ledgered as change_denied.
A HIGH change without the phrase is never executed — by control flow,
not by convention.
"""

from __future__ import annotations

from typing import Any, Callable

from ..core.ledger import Ledger
from .gates import Change, GATE_PROFILES, RISK_HIGH, RISK_LOW, RISK_MED, classify

AUTH_SILENT = "silent"
AUTH_LIGHTWEIGHT = "lightweight"
AUTH_CEREMONIAL = "ceremonial"

AUTH_FOR_RISK = {
    RISK_LOW: AUTH_SILENT,
    RISK_MED: AUTH_LIGHTWEIGHT,
    RISK_HIGH: AUTH_CEREMONIAL,
}

CEREMONIAL_PHRASE = "Yes, with authorization."


def _authorized(
    auth: str,
    change: Change,
    approver: Callable[[Change], Any] | None,
) -> bool:
    if auth == AUTH_SILENT:
        return True
    if approver is None:
        return False  # no approver: deny by default, every tier above LOW
    answer = approver(change)
    if auth == AUTH_LIGHTWEIGHT:
        return bool(answer)
    # Ceremonial: the exact phrase, or nothing.
    return answer == CEREMONIAL_PHRASE


def propose_change(
    change: Change,
    plan: Callable[[], Any],
    ledger: Ledger,
    checks: dict[str, Callable[[Change], bool]] | None = None,
    approver: Callable[[Change], Any] | None = None,
) -> dict:
    """Classify, authorize, gate, and (only then) execute *plan*."""
    risk = classify(change)
    auth = AUTH_FOR_RISK[risk]
    ledger.append(
        "change_proposed",
        {"description": change.description, "risk": risk, "auth": auth},
    )

    approved = _authorized(auth, change, approver)

    # Wire the owner decision into the OwnerApproval gate and run the
    # risk profile, ledgering every gate result (fail-fast).
    gate_checks = dict(checks or {})
    gate_checks["OwnerApproval"] = lambda _c: approved
    all_passed = True
    for gate in GATE_PROFILES[risk]:
        if gate in gate_checks:
            passed = bool(gate_checks[gate](change))
        else:
            passed = gate != "OwnerApproval"  # owner gate never defaults open
        ledger.append(
            "gate_result",
            {"gate": gate, "passed": passed, "risk": risk,
             "description": change.description},
        )
        if not passed:
            all_passed = False
            break  # fail-fast

    if not (approved if auth != AUTH_SILENT else True) or not all_passed:
        ledger.append(
            "change_denied",
            {"description": change.description, "risk": risk, "auth": auth},
        )
        return {"executed": False, "risk": risk, "auth": auth}

    result = plan()
    ledger.append(
        "change_executed",
        {"description": change.description, "risk": risk, "auth": auth},
    )
    return {"executed": True, "risk": risk, "auth": auth, "result": result}
