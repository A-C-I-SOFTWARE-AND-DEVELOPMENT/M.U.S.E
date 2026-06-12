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

from muse_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from .archive.store import ArchiveStore
from .domains import admit_for_autonomy
from .selfplay.evolve import EvolveResult, VariantProposer, evolve
from .selfplay.llm import LLMMutator, Provider, extract_code
from .selfplay.swe_tasks import demo_swe_proposer
from .selfplay.tasks import (
    DEMO_BASELINE_CODE,
    DEMO_EVOLVE_TASK,
    demo_variant_proposer,
)
from .verifier.swe import SweTask, baseline_fails, score_swe_patch


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


@dataclass
class SweImprovementRun:
    domain: str
    used_llm: bool
    accepted: bool
    baseline_failed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "used_llm": self.used_llm,
            "accepted": self.accepted,
            "baseline_failed": self.baseline_failed,
            "detail": self.detail,
        }


def _swe_llm_proposer(provider: Provider, task: SweTask, current: str) -> list[str]:
    prompt = (
        f"The file `{task.target_path}` in a repo fails this test command:\n"
        f"  {' '.join(task.test_command)}\n\n"
        f"Current contents:\n```python\n{current}```\n\n"
        "Return ONLY the corrected file contents in a ```python code block."
    )
    return [extract_code(provider(prompt))]


def run_swe_improvement(
    task: SweTask,
    current_content: str,
    *,
    provider: Optional[Provider] = None,
    ledger: Optional[GuardrailLedger] = None,
) -> SweImprovementRun:
    """Repo-level improvement: propose a patch, accept iff the repo tests pass.

    The verifier runs the repo's *real* test command in an isolated copy, so an
    accepted patch is genuinely correct (not model-asserted). With ``provider``
    set, an LLM proposes the fix; otherwise the deterministic reference is used.
    """

    admit_for_autonomy("swe_local")  # fail-closed if the domain lacks a verifier
    baseline_failed = baseline_fails(task)
    if provider is not None:
        candidates = _swe_llm_proposer(provider, task, current_content)
        used_llm = True
    else:
        candidates = demo_swe_proposer(current_content)
        used_llm = False

    accepted = False
    detail = "no candidate accepted"
    for candidate in candidates:
        score = score_swe_patch(task, candidate)
        if ledger is not None:
            ledger.append(
                "swe_improve",
                task.task_id,
                {"accepted": score.accepted, "detail": score.detail},
            )
        if score.accepted:
            accepted = True
            detail = "patch passes the repo's real test command"
            break
        detail = score.detail

    return SweImprovementRun(
        domain="swe_local",
        used_llm=used_llm,
        accepted=accepted,
        baseline_failed=baseline_failed,
        detail=detail,
    )


__all__ = [
    "ImprovementRun",
    "run_algorithms_improvement",
    "SweImprovementRun",
    "run_swe_improvement",
]
