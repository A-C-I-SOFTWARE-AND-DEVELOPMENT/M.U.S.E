"""Tests for muse_cli.jarvis_prime.sia_self_improve and the router branch.

A promotable candidate must become an owner-gated proposal and NEVER be
applied or written to the live target. A non-improving candidate must
produce no proposal. SIA is faked — no binary, no network.
"""

from __future__ import annotations

from muse_cli.jarvis_prime.gates import GateOutcome
from muse_cli.jarvis_prime.modes import Mode
from muse_cli.jarvis_prime.router import RouteTarget, Router
from muse_cli.jarvis_prime.self_update import (
    ProposalBook,
    ProposalKind,
    ProposalStatus,
)
from muse_cli.jarvis_prime.sia_self_improve import SiaJob, run_self_improvement
from muse_cli.workers.base import (
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)


class FakeSiaWorker:
    """Duck-typed stand-in for SiaWorker (no SIA binary needed)."""

    def __init__(self, candidate: float, *, available: bool = True, ok: bool = True):
        self._candidate = candidate
        self._available = available
        self._ok = ok

    def detect(self):
        return WorkerDetection(available=self._available, reason="fake")

    def prepare_prompt(self, job):
        return WorkerPrompt(text=getattr(job, "objective", ""))

    def run(self, job):
        return WorkerRunResult(ok=self._ok)

    def collect(self, job):
        return WorkerArtifacts(
            workspace_path="/sandbox/x",
            details={
                "best_gen": 2,
                "generations": [
                    {
                        "gen": 2,
                        "target_agent": "/sandbox/x/runs/run_1/gen_2/target_agent.py",
                        "improvement": "",
                        "execution": "",
                        "score": self._candidate,
                    }
                ],
            },
        )

    def score(self, artifacts):
        return WorkerScore(value=self._candidate, confidence=1.0, rationale="fake")


# ── glue: promotable → owner-gated proposal ──────────────────────────────


def test_improvement_yields_owner_gated_proposal():
    book = ProposalBook()
    job = SiaJob(objective="improve", target_path="skills/foo/SKILL.md", task="foo")
    out = run_self_improvement(
        job, book=book, baseline_score=0.4, worker=FakeSiaWorker(0.8)
    )

    assert out.improved is True
    assert out.gate.outcome is GateOutcome.PASS
    assert out.proposal is not None
    assert out.proposal.kind is ProposalKind.SKILL_UPDATE
    # The whole point: it is held for the owner, not applied.
    assert out.proposal.status is ProposalStatus.NEEDS_OWNER_APPROVAL
    assert out.proposal.status is not ProposalStatus.APPLIED
    assert out.proposal.requires_owner_approval is True
    assert book.pending(), "proposal must be surfaced to the owner"


def test_runtime_target_uses_self_runtime_kind_and_rc4():
    book = ProposalBook()
    job = SiaJob(
        objective="improve",
        target_path="muse_cli/jarvis_prime/router.py",
        task="route-bench",
    )
    out = run_self_improvement(
        job, book=book, baseline_score=0.4, worker=FakeSiaWorker(0.9)
    )
    assert out.proposal is not None
    assert out.proposal.kind is ProposalKind.SELF_RUNTIME_UPDATE
    assert out.proposal.risk_class == "RC4"
    assert out.proposal.status is ProposalStatus.NEEDS_OWNER_APPROVAL


def test_no_improvement_yields_no_proposal():
    book = ProposalBook()
    job = SiaJob(objective="x", target_path="skills/foo/SKILL.md", task="foo")
    out = run_self_improvement(
        job, book=book, baseline_score=0.9, worker=FakeSiaWorker(0.3)
    )
    assert out.improved is False
    assert out.proposal is None
    assert out.gate.outcome is GateOutcome.FAIL
    assert not book.pending()


def test_unavailable_worker_is_graceful():
    book = ProposalBook()
    out = run_self_improvement(
        SiaJob(objective="x"),
        book=book,
        worker=FakeSiaWorker(0.9, available=False),
    )
    assert out.available is False
    assert out.proposal is None


def test_never_edits_the_live_target(tmp_path):
    target = tmp_path / "skills" / "foo" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("BASELINE", encoding="utf-8")

    book = ProposalBook()
    job = SiaJob(objective="improve", target_path=str(target), task="foo")
    out = run_self_improvement(
        job, book=book, baseline_score=0.4, worker=FakeSiaWorker(0.8)
    )

    assert out.proposal is not None  # promotable
    # ...but the live file is untouched — promotion happens only via PR.
    assert target.read_text(encoding="utf-8") == "BASELINE"


# ── router branch ─────────────────────────────────────────────────────────


def test_router_self_improve_intent_is_owner_gated_skill():
    # Self-improvement now routes to the research-fabric skill — the unified,
    # verifier-gated engine (SIA runs inside it as the sandboxed iterator).
    # Promotion/auto-apply remains owner-gated (charter), so the route still
    # requires owner authorization.
    decision = Router().route(Mode.BUILDER, "please self-improve the planner skill")
    assert decision.target is RouteTarget.SKILL
    assert decision.delegate_to == "research-fabric"
    assert decision.requires_owner_authorization is True


def test_router_fabric_intent_routes_to_research_fabric():
    for intent in (
        "evolve a faster implementation",
        "grant the autonomy charter",
        "run the benchmark wall",
        "use the research fabric",
    ):
        decision = Router().route(Mode.BUILDER, intent)
        assert decision.delegate_to == "research-fabric", intent
        assert decision.requires_owner_authorization is True


def test_router_normal_build_intent_unchanged():
    decision = Router().route(Mode.BUILDER, "build a login form")
    assert decision.target is RouteTarget.CLAUDE_CODE_BUILDER
