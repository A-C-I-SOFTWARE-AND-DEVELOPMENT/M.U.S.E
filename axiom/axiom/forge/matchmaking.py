"""Information-maximizing matchmaking (the ~34% duel-savings basis).

A duel is worth running when its outcome is uncertain (ratings close),
when our knowledge of the players is poor (high RD), and when the pair
hasn't been measured before (novelty). Pair value =
closeness x uncertainty x novelty, each in [0, 1].
"""

from __future__ import annotations

import math
from itertools import combinations

CLOSENESS_SCALE = 200.0  # rating gap at which a duel loses ~63% of its value
RD_NORM = 700.0  # max combined RD (350 + 350)


def closeness(r_a: float, r_b: float) -> float:
    """1.0 for equal ratings, decaying with the gap."""
    return math.exp(-abs(r_a - r_b) / CLOSENESS_SCALE)


def uncertainty(rd_a: float, rd_b: float) -> float:
    """Combined rating deviation, normalized to [0, 1]."""
    return min(1.0, max(-1.0, (rd_a + rd_b) / RD_NORM))


def novelty(times_played: int) -> float:
    """1.0 for a fresh pairing, halving per repeat."""
    return 1.0 / (1.0 + times_played)


def pair_value(
    a: dict, b: dict, history: dict[frozenset, int] | None = None
) -> float:
    """Score a candidate pair. *a*/*b* need rating + rd + an id key."""
    played = (history or {}).get(frozenset((a["id"], b["id"])), 0)
    return (
        closeness(a["rating"], b["rating"])
        * uncertainty(a["rd"], b["rd"])
        * novelty(played)
    )


def select_pairs(
    candidates: list[dict],
    n_pairs: int,
    history: dict[frozenset, int] | None = None,
) -> list[tuple[dict, dict]]:
    """Pick the *n_pairs* most informative duels, no candidate reuse
    within a round."""
    scored = sorted(
        combinations(candidates, 2),
        key=lambda p: pair_value(p[0], p[1], history),
        reverse=True,
    )
    chosen: list[tuple[dict, dict]] = []
    used: set = set()
    for a, b in scored:
        if len(chosen) >= n_pairs:
            break
        if a["id"] in used or b["id"] in used:
            continue
        chosen.append((a, b))
        used.update((a["id"], b["id"]))
    return chosen
