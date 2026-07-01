"""MUSE Prime effort-class (E0–E5) routing taxonomy.

Implements the vNext "effort budget" primitive (constitution clause
``Cn+2``): every routing decision is stamped with an ``EffortClass`` and
defaults to the *smallest sufficient* route. Escalation up the ladder is
auditable and justified.

This module is **deterministic and stdlib-only**. It performs no model
call. It maps signals that are already available at decision time — the
resolved :class:`~hermes_cli.jarvis_prime.router.RouteTarget`, whether the
decision is owner-gated, and the risk class — onto the smallest effort
class that can satisfy the route.

Taxonomy
--------

======  =====================================  =========================
class   meaning                                council / behavior
======  =====================================  =========================
``E0``  direct answer / no council             0 agents
``E1``  one specialist lens                    1 agent
``E2``  small council                          2–3 agents
``E3``  full council                           4–7 agents
``E4``  deep research / implementation run     build/review/test run
``E5``  owner-approved swarm only              parallel swarm (gated)
======  =====================================  =========================

The classifier never selects a *larger* council than the class allows, and
``E5`` always carries the existing owner-authorization requirement — this
module does **not** invent a new gate; it reuses the owner-approval signal
already present on the :class:`RouteDecision`.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_cli.jarvis_prime.router import RouteDecision


class EffortClass(Enum):
    """Bounded effort ladder. Default to the SMALLEST sufficient class.

    - ``E0`` — direct answer, no council (0 agents).
    - ``E1`` — one specialist lens (1 agent).
    - ``E2`` — small council (2–3 agents).
    - ``E3`` — full council (4–7 agents).
    - ``E4`` — deep research / implementation run (build → review → test).
    - ``E5`` — owner-approved swarm only (parallel grains; owner-gated).
    """

    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"
    E5 = "E5"

    @property
    def rank(self) -> int:
        """Ordinal position on the ladder (0..5), for cheap comparison."""
        return int(self.value[1:])


# Maximum council size each class permits. ``None`` means "not a council
# class" (E0 = no council; E4/E5 are execution runs, not councils). Used as a
# soft cap so a council is never sized above what its class allows.
_MAX_COUNCIL_SIZE: dict[EffortClass, int | None] = {
    EffortClass.E0: 0,
    EffortClass.E1: 1,
    EffortClass.E2: 3,
    EffortClass.E3: 7,
    EffortClass.E4: None,
    EffortClass.E5: None,
}


def max_council_size(effort: EffortClass) -> int | None:
    """Return the largest council this class permits.

    ``0`` for E0 (no council), ``1``/``3``/``7`` for E1/E2/E3, and ``None``
    for E4/E5 (execution runs, where "council size" does not apply).
    """
    return _MAX_COUNCIL_SIZE[effort]


def cap_council_size(effort: EffortClass, requested: int) -> int:
    """Clamp a requested council size to what ``effort`` permits.

    Returns ``requested`` unchanged when the class imposes no council cap
    (E4/E5) or when the request already fits. Never returns a negative
    number. This is the soft-cap primitive callers opt into; it does not
    change any dispatch outcome on its own.
    """
    ceiling = _MAX_COUNCIL_SIZE[effort]
    if ceiling is None:
        return max(0, requested)
    return max(0, min(requested, ceiling))


def classify_effort(decision: "RouteDecision") -> EffortClass:
    """Map a resolved :class:`RouteDecision` to the smallest sufficient class.

    Deterministic, no model call. The mapping keys off the resolved
    ``RouteTarget`` (the routing decision already made) plus the owner-gate
    signal — the same signals available at decision time. The result is the
    *smallest* class able to carry the route:

    - direct answer / defer / owner-decision → ``E0``
    - single specialist or skill lens        → ``E1``
    - full AOS council                       → ``E3``
    - build / review / fix / test / publish  → ``E4``
    - owner-gated self-improvement swarm      → ``E5``

    ``E2`` (small council) is not produced from a bare target here because
    the operator/strategy council paths dispatch the full council; ``E2`` is
    available for callers that resize a council downward (see
    :func:`cap_council_size`). Keeping the target→class map conservative is
    what makes stamping non-behavior-changing.
    """
    # Imported lazily to avoid a circular import (router imports this module).
    from hermes_cli.jarvis_prime.router import RouteTarget

    target = decision.target

    # E5 — owner-approved swarm only. The self-improvement / research-fabric
    # route is the swarm path and is *already* owner-gated; we assert that
    # invariant by requiring the owner-authorization signal to classify E5.
    if (
        target is RouteTarget.SKILL
        and decision.delegate_to == "research-fabric"
        and decision.requires_owner_authorization
    ):
        return EffortClass.E5

    # E4 — deep research / implementation run (build, review, bounded fix,
    # local test run, PR publish).
    if target in (
        RouteTarget.CLAUDE_CODE_BUILDER,
        RouteTarget.CODEX_REVIEWER,
        RouteTarget.CODEX_BOUNDED_FIX,
        RouteTarget.LOCAL_TEST_RUNNER,
        RouteTarget.GITHUB_PR_PUBLISHER,
    ):
        return EffortClass.E4

    # E3 — full AOS council (multi-perspective judgment, 4–7 agents).
    if target is RouteTarget.AOS_COUNCIL:
        return EffortClass.E3

    # E1 — one specialist lens (a single specialist or a single skill).
    if target in (RouteTarget.SPECIALIST, RouteTarget.SKILL):
        return EffortClass.E1

    # E0 — direct answer / defer to focused mode / owner decision (no council).
    return EffortClass.E0
