"""Research fabric — bounded-autonomous, verifier-gated self-improvement.

A software-development-first self-learning layer for JARVIS Prime, modeled on the
AlphaGo-Zero evaluator gate (a challenger replaces the champion only after a
strict, statistically-margined, non-regression win) and the AZR/Darwin-Gödel
self-improvement engines — wrapped in an owner-gated safety harness the agent can
never reach (Constitution C33/C34).

Auto-apply is permitted ONLY inside an active owner-signed Autonomy Charter,
after the strict ratchet + the eight verification gates + the capability wall +
the >=0.55 evaluator gate all pass, with automatic canary rollback on regression.
Runtime, gates, owner-auth, model registry, routing, the verifier/monitor/ledger
harness, and the Constitution itself can never auto-apply (C34).
"""

from __future__ import annotations

from .ambition import AmbitionProfile, apply_ambition
from .apply import ApplyRefused, GitApplier, GitRollback, current_head
from .archive import Archive, ArchiveMember
from .archive.store import ArchiveStore
from .catalog import (
    ABSOLUTE_FLOOR,
    COMPOSITE_MARGIN,
    EVAL_WIN_MARGIN,
    REQUIRED_DOMAINS,
    SAFETY_DOMAINS,
)
from .champion import Champion, ChampionStore
from .charter import AutonomyCharter, CharterBook, HARD_WALL_KINDS, is_hard_walled
from .controller import AutoApplyOutcome, AutonomyController
from .domains import Domain, admit_for_autonomy, domains, get_domain
from .improve import ImprovementRun, run_algorithms_improvement
from .monitor import AlignmentMonitor, TripwireSignal
from .pipeline import FabricContext, open_context, report_payload
from .store import SnapshotStore
from .validators import RatchetVerdict, RatchetWall, evaluate_ratchet
from .verifier import Candidate, screen_for_reward_hacking

__all__ = [
    "REQUIRED_DOMAINS",
    "ABSOLUTE_FLOOR",
    "COMPOSITE_MARGIN",
    "EVAL_WIN_MARGIN",
    "SAFETY_DOMAINS",
    "AmbitionProfile",
    "apply_ambition",
    "Champion",
    "ChampionStore",
    "AutonomyCharter",
    "CharterBook",
    "HARD_WALL_KINDS",
    "is_hard_walled",
    "AutonomyController",
    "AutoApplyOutcome",
    "AlignmentMonitor",
    "TripwireSignal",
    "SnapshotStore",
    "RatchetVerdict",
    "RatchetWall",
    "evaluate_ratchet",
    "Candidate",
    "screen_for_reward_hacking",
    "FabricContext",
    "open_context",
    "report_payload",
    "GitApplier",
    "GitRollback",
    "ApplyRefused",
    "current_head",
    "Archive",
    "ArchiveMember",
    "ArchiveStore",
    "Domain",
    "domains",
    "get_domain",
    "admit_for_autonomy",
    "ImprovementRun",
    "run_algorithms_improvement",
    "cli_main",
]


def cli_main(argv: list[str] | None = None) -> int:
    from .main import cli_main as _cli

    return _cli(argv)
