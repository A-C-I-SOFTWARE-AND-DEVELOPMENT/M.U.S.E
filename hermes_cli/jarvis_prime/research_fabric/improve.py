"""Top-level improvement orchestration — ties the planes together.

Selects an autonomy-eligible domain (Plane 4), picks a proposer (a live LLM
mutator when a provider is supplied, else the deterministic reference), runs the
verifier-gated evolutionary ratchet (Plane 2), and records lineage to the
diversity archive (Plane 3). Promotion/auto-apply beyond this still flows through
the charter-gated controller (Plane 0) — this function only produces *verified
candidates*, it does not mutate the live tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from .archive.store import ArchiveStore
from .domains import admit_for_autonomy
from .selfplay.evolve import EvolveResult, VariantProposer, evolve
from .selfplay.llm import LLMMutator, Provider
from .selfplay.tasks import (
    DEMO_BASELINE_CODE,
    DEMO_EVOLVE_TASK,
    demo_variant_proposer,
)


@dataclass
class ImprovementRun:
    domain: str
    used_llm: bool
    result: EvolveResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "used_llm": self.used_llm,
            "result": self.result.to_dict(),
        }


def run_algorithms_improvement(
    *,
    provider: Optional[Provider] = None,
    generations: int = 5,
    ledger: Optional[GuardrailLedger] = None,
    archive: Optional[ArchiveStore] = None,
) -> ImprovementRun:
    """Run a verifier-gated improvement on the algorithms domain.

    With ``provider`` set, a live :class:`LLMMutator` proposes variants; otherwise
    the deterministic reference proposer is used. Either way the executable
    verifier + op-count ratchet decide what is kept — the model is never trusted.
    """

    admit_for_autonomy("algorithms")  # fail-closed if the domain lacks a verifier
    proposer: VariantProposer = (
        LLMMutator(provider) if provider is not None else demo_variant_proposer
    )
    result = evolve(
        DEMO_EVOLVE_TASK,
        DEMO_BASELINE_CODE,
        proposer,
        generations=generations,
        ledger=ledger,
        archive=archive,
    )
    return ImprovementRun(domain="algorithms", used_llm=provider is not None, result=result)


__all__ = ["ImprovementRun", "run_algorithms_improvement"]
