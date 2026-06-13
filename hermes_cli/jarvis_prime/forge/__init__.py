"""The Expert Forge at scale (MUSE Unbound Volume VI, Part 5).

Diversity-seeded tournaments over a **content-addressed candidate registry**
(resolve-or-fail lookup — the L1 pattern), Glicko-2 matchmaking, a MAP-Elites
diversity grid, Merkle-anchored attested leaderboards, and winner distillation
routed through the federation poison filter (one intake path, no side door).

The verifier is the only judge: a duel is decided by
``research_fabric.verifier.algorithms`` execution (correctness hard-gates,
then deterministic op-count), never by self-reports. Every duel, rating
update, elite replacement, and leaderboard anchor is appended to the
hash-chained guardrail ledger.

stdlib-only; persistent state lives under ``hermes_home()/jarvis_prime/forge``.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.guardrail_evidence import hermes_home

KIND_FORGE_REGISTER = "forge_candidate_register"
KIND_FORGE_DUEL = "forge_duel"
KIND_FORGE_RATING = "forge_rating_update"
KIND_FORGE_ELITE = "forge_elites_update"
KIND_FORGE_ANCHOR = "forge_leaderboard_anchor"
ARTIFACT_LEADERBOARD = "forge_leaderboard_attestation"


class ForgeError(RuntimeError):
    """A Forge invariant was violated (unresolved reference, lookalike, …)."""


def forge_dir() -> Path:
    """Per-node Forge state directory (created on demand)."""

    path = hermes_home() / "jarvis_prime" / "forge"
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "KIND_FORGE_REGISTER",
    "KIND_FORGE_DUEL",
    "KIND_FORGE_RATING",
    "KIND_FORGE_ELITE",
    "KIND_FORGE_ANCHOR",
    "ARTIFACT_LEADERBOARD",
    "ForgeError",
    "forge_dir",
]
