"""Owner-gated SIA self-improvement glue for JARVIS Prime.

Connects the sandboxed SIA worker (autonomous scaffold-rewriting) to
JARVIS's owner-gated proposal flow. SIA iterates freely on a *copy* of
a target inside the isolation sandbox; this module scores the best
generation against a baseline with the benchmark gate and, **only when
the candidate genuinely beats baseline**, emits a
:class:`~hermes_cli.jarvis_prime.self_update.Proposal` that requires the
owner's exact authorization phrase.

Invariants (enforced by tests):

* It NEVER edits the live target and NEVER applies a change itself.
* A promotable candidate produces a proposal whose status is
  ``NEEDS_OWNER_APPROVAL`` — promotion happens via the standard PR flow
  (Claude builder + Codex reviewer), consistent with ``self_update`` and
  ``docs/jarvis-prime-operating-system.md``.
* A non-improving candidate produces **no** proposal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from hermes_cli.jarvis_prime.benchmark_gate import evaluate_improvement
from hermes_cli.jarvis_prime.gates import GateOutcome, GateResult
from hermes_cli.jarvis_prime.self_update import (
    Proposal,
    ProposalBook,
    ProposalEvidence,
    ProposalKind,
)


@dataclass
class SiaJob:
    """A self-improvement request handed to the SIA worker."""

    objective: str
    target_path: str = ""
    task: str = "custom"
    job_id: str = "sia-self-improve"
    repo_root: str = ""
    acceptance_criteria: tuple[str, ...] = ()
    # ``prompt`` is the attribute the worker reads first; mirror objective.
    prompt: str = ""

    def __post_init__(self) -> None:
        if not self.prompt:
            self.prompt = self.objective


@dataclass
class SiaImprovementOutcome:
    """Result of one self-improvement attempt."""

    target_path: str
    task: str
    available: bool
    improved: bool
    baseline_score: float
    candidate_score: Optional[float]
    best_gen: Optional[int]
    gate: GateResult
    proposal: Optional[Proposal]
    workspace_path: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_path": self.target_path,
            "task": self.task,
            "available": self.available,
            "improved": self.improved,
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "best_gen": self.best_gen,
            "gate": self.gate.to_dict(),
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "workspace_path": self.workspace_path,
            "rationale": self.rationale,
        }


def _kind_for_target(target_path: str) -> ProposalKind:
    p = (target_path or "").replace("\\", "/")
    if "/skills/" in p or p.startswith("skills/"):
        return ProposalKind.SKILL_UPDATE
    if "/.claude/agents/" in p or "/agents/" in p or "/dotclaude/agents/" in p:
        return ProposalKind.AGENT_UPDATE
    if "/hermes_cli/" in p or p.startswith("hermes_cli/"):
        return ProposalKind.SELF_RUNTIME_UPDATE
    return ProposalKind.SELF_RUNTIME_UPDATE


def _gen_field(artifacts: Any, best_gen: Optional[int], field_name: str) -> str:
    if best_gen is None:
        return ""
    for g in (getattr(artifacts, "details", {}) or {}).get("generations", []):
        if g.get("gen") == best_gen:
            return str(g.get(field_name) or "")
    return ""


def _improvement_excerpt(path: str, *, limit: int = 800) -> str:
    if not path:
        return ""
    try:
        text = open(path, encoding="utf-8").read().strip()
    except OSError:
        return ""
    return text[:limit]


def run_self_improvement(
    job: SiaJob,
    *,
    book: ProposalBook,
    baseline_score: float = 0.0,
    min_margin: float = 0.0,
    worker: Optional[Any] = None,
) -> SiaImprovementOutcome:
    """Run SIA in a sandbox and, if it beats baseline, propose (owner-gated).

    ``worker`` may be injected (recommended — bound to the repo root); when
    omitted the registered ``"sia"`` worker is used.
    """

    if worker is None:
        from hermes_cli.workers import load_builtins
        from hermes_cli.workers import registry as _wr

        load_builtins()
        worker = _wr.get("sia")

    detection = worker.detect()
    if not detection.available:
        return SiaImprovementOutcome(
            target_path=job.target_path,
            task=job.task,
            available=False,
            improved=False,
            baseline_score=baseline_score,
            candidate_score=None,
            best_gen=None,
            gate=GateResult(
                name="benchmark",
                outcome=GateOutcome.SKIPPED,
                reason="SIA worker unavailable",
            ),
            proposal=None,
            workspace_path="",
            rationale=detection.reason or "SIA worker unavailable",
        )

    worker.prepare_prompt(job)
    run = worker.run(job)
    artifacts = worker.collect(job)
    score = worker.score(artifacts)

    workspace_path = artifacts.workspace_path
    best_gen = (getattr(artifacts, "details", {}) or {}).get("best_gen")
    candidate = score.value if run.ok else None

    if candidate is None:
        return SiaImprovementOutcome(
            target_path=job.target_path,
            task=job.task,
            available=True,
            improved=False,
            baseline_score=baseline_score,
            candidate_score=None,
            best_gen=best_gen,
            gate=GateResult(
                name="benchmark",
                outcome=GateOutcome.SKIPPED,
                reason=run.error or "no candidate produced",
            ),
            proposal=None,
            workspace_path=workspace_path,
            rationale=run.error or "SIA produced no scorable candidate",
        )

    gate = evaluate_improvement(
        baseline_score, candidate, task=job.task, min_margin=min_margin
    )

    if gate.outcome is not GateOutcome.PASS:
        return SiaImprovementOutcome(
            target_path=job.target_path,
            task=job.task,
            available=True,
            improved=False,
            baseline_score=baseline_score,
            candidate_score=candidate,
            best_gen=best_gen,
            gate=gate,
            proposal=None,
            workspace_path=workspace_path,
            rationale=f"not promoted: {gate.reason}",
        )

    # PASS → build an owner-gated proposal. We never apply it here.
    kind = _kind_for_target(job.target_path)
    risk_class = "RC4" if kind is ProposalKind.SELF_RUNTIME_UPDATE else "RC3"

    winning_agent = _gen_field(artifacts, best_gen, "target_agent")
    improvement_path = _gen_field(artifacts, best_gen, "improvement")

    evidence: tuple[ProposalEvidence, ...] = (
        ProposalEvidence(
            kind="benchmark",
            text=(
                f"SIA generation {best_gen}: baseline {baseline_score:.4f} → "
                f"candidate {candidate:.4f} on task '{job.task}' "
                f"(+{candidate - baseline_score:.4f})"
            ),
            citation=workspace_path,
            confidence=score.confidence,
        ),
    )
    excerpt = _improvement_excerpt(improvement_path)
    if excerpt:
        evidence += (
            ProposalEvidence(kind="retro", text=excerpt, citation=improvement_path),
        )

    diff_intent = (
        f"Adopt the SIA-improved scaffold from {winning_agent or '(sandbox)'} "
        f"which beat the baseline by {candidate - baseline_score:+.4f} on task "
        f"'{job.task}'. Apply via PR (Claude builder + Codex reviewer); do not "
        f"auto-merge. Sandbox: {workspace_path}."
    )

    proposal = book.propose(
        kind=kind,
        target_path=job.target_path or "(unspecified target)",
        rationale=(
            f"SIA self-improvement produced a candidate that beats the baseline "
            f"on '{job.task}'. Owner approval required before any live change."
        ),
        diff_intent=diff_intent,
        evidence=evidence,
        risk_class=risk_class,
    )

    return SiaImprovementOutcome(
        target_path=job.target_path,
        task=job.task,
        available=True,
        improved=True,
        baseline_score=baseline_score,
        candidate_score=candidate,
        best_gen=best_gen,
        gate=gate,
        proposal=proposal,
        workspace_path=workspace_path,
        rationale=f"promotable (owner-gated): {gate.reason}",
    )


__all__ = [
    "SiaJob",
    "SiaImprovementOutcome",
    "run_self_improvement",
]
