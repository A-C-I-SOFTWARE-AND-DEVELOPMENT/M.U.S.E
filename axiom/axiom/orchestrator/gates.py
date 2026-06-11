"""The eight verification gates with risk-adaptive profiles (replaces
always-all-eight with blast-radius-tiered gating).

A Change is classified LOW / MED / HIGH by a blast-radius score over
lines touched, files touched, effect surface, and whether it changes
default behavior. LOW runs the cheap gates; HIGH runs all eight,
including OwnerApproval. Gates run fail-fast: the first red gate stops
the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

GATES = (
    "Planning",
    "Build",
    "Review",
    "Test",
    "Security",
    "Release",
    "OwnerApproval",
    "Rollback",
)

RISK_LOW = "LOW"
RISK_MED = "MED"
RISK_HIGH = "HIGH"

# Blast-radius weights.
W_LOC = 0.3  # lines of change, saturating at LOC_NORM
W_FILES = 0.2  # breadth of files touched
W_EFFECTS = 0.4  # external effect surface
W_DEFAULT_BEHAVIOR = 0.65  # changing defaults is near-HIGH on its own
LOC_NORM = 20.0  # one "full" unit of LOC risk

MED_THRESHOLD = 0.3
HIGH_THRESHOLD = 0.65

GATE_PROFILES: dict[str, tuple[str, ...]] = {
    RISK_LOW: ("Build", "Test"),
    RISK_MED: ("Planning", "Build", "Review", "Test", "Security", "Rollback"),
    RISK_HIGH: GATES,
}


@dataclass(frozen=True)
class Change:
    description: str
    loc: int = 0
    files: int = 1
    effects: tuple[str, ...] = ()
    changes_default_behavior: bool = False


def blast_radius(change: Change) -> float:
    """Score in [0, ~1.55]; thresholds slice it into LOW/MED/HIGH."""
    loc_term = min(1.0, change.loc / LOC_NORM) * W_LOC
    files_term = min(1.0, (change.files - 1) / 5.0) * W_FILES
    effects_term = min(1.0, len(change.effects) / 2.0) * W_EFFECTS
    default_term = W_DEFAULT_BEHAVIOR if change.changes_default_behavior else 0.0
    return loc_term + files_term + effects_term + default_term


def classify(change: Change) -> str:
    score = blast_radius(change)
    if score >= HIGH_THRESHOLD:
        return RISK_HIGH
    if score >= MED_THRESHOLD:
        return RISK_MED
    return RISK_LOW


@dataclass
class GateResult:
    gate: str
    passed: bool
    detail: str = ""


def run_gates(
    change: Change,
    checks: dict[str, Callable[[Change], bool]],
    profile: str | None = None,
) -> tuple[bool, list[GateResult]]:
    """Run the gate profile for *change*, fail-fast.

    *checks* maps gate name -> predicate; a missing check passes by
    default except OwnerApproval, which denies by default.
    """
    risk = profile or classify(change)
    results: list[GateResult] = []
    for gate in GATE_PROFILES[risk]:
        if gate in checks:
            ok = bool(checks[gate](change))
        else:
            ok = gate != "OwnerApproval"  # owner approval never defaults open
        results.append(GateResult(gate=gate, passed=ok))
        if not ok:
            return False, results  # fail-fast
    return True, results
