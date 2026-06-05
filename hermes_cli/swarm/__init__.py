"""Swarm Grainler Parallel — auditable, non-overlapping, self-improving code work.

Every code-producing task can run as a *swarm*: a goal is decomposed into
**grains** (bounded units that each own a *disjoint file-domain*), each grain
becomes its own **specialized LLM** (own model lane, toolset, iteration budget,
token-juice context pack, and a dedicated JARVIS Memory Tree namespace), and the
grains run **in parallel** in isolated git worktrees so they never overlap on
each other's work. Every step is dated, traceable, and recorded in a Decision
Ledger, and a self-update loop auto-applies the safe/reversible learnings.

Public API:

* :class:`~hermes_cli.swarm.grain.Grain`, :class:`~hermes_cli.swarm.grain.FileDomain`,
  :class:`~hermes_cli.swarm.grain.SwarmPlan`, :class:`~hermes_cli.swarm.grain.OverlapError`
* :func:`~hermes_cli.swarm.grainler.partition`,
  :func:`~hermes_cli.swarm.grainler.to_execution_plan`
* :func:`~hermes_cli.swarm.specialist.build_grain_agent_spec`,
  :func:`~hermes_cli.swarm.specialist.claim_grain`
* :func:`~hermes_cli.swarm.coordinator.run_swarm`
"""

from __future__ import annotations

from hermes_cli.swarm.grain import (
    FileDomain,
    Grain,
    OverlapError,
    SwarmPlan,
)
from hermes_cli.swarm.grainler import partition, to_execution_plan
from hermes_cli.swarm.specialist import (
    DomainClaimError,
    GrainAgentSpec,
    build_grain_agent_spec,
    claim_grain,
    release_grain,
)
from hermes_cli.swarm.coordinator import (
    SwarmGrainResult,
    SwarmResult,
    run_swarm,
)

__all__ = [
    "FileDomain",
    "Grain",
    "OverlapError",
    "SwarmPlan",
    "partition",
    "to_execution_plan",
    "GrainAgentSpec",
    "DomainClaimError",
    "build_grain_agent_spec",
    "claim_grain",
    "release_grain",
    "SwarmGrainResult",
    "SwarmResult",
    "run_swarm",
]
