"""W6 refinement for the muse NL compiler.

Two capabilities, both deterministic and safe:

1. **Ambiguity repair** (:func:`apply_clarifications`) — fold a caller's
   answers to clarifying questions back into the prompt and re-parse. No
   LLM, no IO; the same answers always produce the same graph.

2. **Execution-guided refinement** (:func:`run_execution_refinement`) — an
   *opt-in*, SAFE way to back a compiled repo work-packet with observed
   evidence. It uses only the read-only / allowlisted guardrail collectors
   (test, git-diff, secret-scan) and never performs an owner-gated or
   destructive action. With the default ``run=False`` it executes nothing —
   it merely records the *planned* verification commands as evidence.

Both functions are additive: they reuse the existing semantic frontend,
guardrail collectors, evidence bundle, and gate engine rather than
reimplementing any of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime import semantic_frontend as sf
from hermes_cli.jarvis_prime.guardrail_collectors import (
    collect_git_diff_evidence,
    collect_reviewer_assignment_evidence,
    collect_secret_scan_evidence,
    collect_test_evidence,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailEvidenceBundle
from hermes_cli.jarvis_prime.gates import run_gate_summary

# Backend-choice vocabulary -> the canonical hint phrase to append so that the
# re-parse emits the matching ``BACKEND_HINT`` node.
_WORKFLOW_CHOICES = frozenset({"workflow", "automation", "automation_flow", "flow"})
_REPO_CHOICES = frozenset({"repo", "work-packet", "work_packet", "code", "codebase"})

# Read-only / allowlisted verification commands. Each is accepted by
# ``collect_test_evidence``'s safety allowlist; with ``run=False`` none execute.
SAFE_COMMANDS = (
    "python -m compileall -q .",
    "ruff check .",
    "pytest -q",
)


@dataclass(frozen=True)
class RefinementSignal:
    """Result of an execution-guided refinement pass."""

    gate_summary: dict
    ran: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_summary": dict(self.gate_summary),
            "ran": self.ran,
            "notes": list(self.notes),
        }


def apply_clarifications(
    parse_result: sf.ParseResult,
    answers: Mapping[str, str],
) -> sf.ParseResult:
    """Fold clarification ``answers`` into the prompt and re-parse.

    Builds an augmented prompt from the original ``raw_text`` plus one
    appended clause per answer (``"; <key> is <value>"``). When an answer
    value names a backend choice, a deterministic backend-hint phrase is also
    appended so the re-parse emits a ``BACKEND_HINT`` node. Returns a fresh
    :class:`~semantic_frontend.ParseResult`. Deterministic: the same inputs
    always yield the same graph.
    """

    base = parse_result.graph.raw_text or ""
    clauses: list[str] = []
    hint_phrases: list[str] = []
    for key, value in answers.items():
        key_s = str(key).strip()
        value_s = str(value).strip()
        if not value_s:
            continue
        clauses.append(f"; {key_s} is {value_s}" if key_s else f"; {value_s}")
        normalized = value_s.lower()
        if normalized in _WORKFLOW_CHOICES:
            hint_phrases.append(" as a workflow")
        elif normalized in _REPO_CHOICES:
            hint_phrases.append(" edit the repo")

    augmented = base + "".join(clauses) + "".join(hint_phrases)
    return sf.parse(augmented)


def run_execution_refinement(
    compile_result: Any,
    *,
    repo_root: str = ".",
    enabled: bool = False,
    run: bool = False,
) -> Optional[RefinementSignal]:
    """Opt-in, SAFE execution-guided refinement of a compiled work packet.

    Returns ``None`` unless ``enabled`` is set. When enabled but the backend
    produced no gate packet (e.g. the PYTHON / automation backends), returns a
    non-running :class:`RefinementSignal` noting that. Otherwise it gathers
    observed evidence using only read-only / allowlisted collectors, runs the
    strict, evidence-bound gate summary, and returns the result.

    The default ``run=False`` keeps the pass non-executing: ``collect_test_
    evidence`` records each safe command as *planned* rather than running it.
    No owner-gated or destructive action is ever performed.
    """

    if not enabled:
        return None

    packet = getattr(compile_result, "gate_packet", None)
    if packet is None:
        return RefinementSignal(
            gate_summary={},
            ran=False,
            notes=("no gate packet for this backend",),
        )

    allowed_files = tuple(packet.get("allowed_files", ()) or ())
    # Acting agent that authored the change, if the packet carries it (same
    # namespace as a review's reviewer_id, for the C19 builder ≠ reviewer check).
    # Absent ⇒ C19 fails open with a logged warning (see strict_review_gate);
    # threading it from the orchestrator is a documented follow-up.
    author_id = str(packet.get("acting_agent_id") or packet.get("author_id") or "").strip()
    # Planned reviewer identity (an ASSIGNMENT, not a verdict — no review has run
    # at refinement time). Same identity namespace as author_id, for the C19
    # builder ≠ reviewer check.
    reviewer_id = str(
        packet.get("reviewer_worker") or packet.get("reviewer_id") or ""
    ).strip()
    bundle = GuardrailEvidenceBundle(packet_id=packet.get("packet_id", ""))
    for artifact in collect_test_evidence(repo_root, SAFE_COMMANDS, run=run):
        bundle.add(artifact)
    diff_art = collect_git_diff_evidence(repo_root, allowed_files, author_id=author_id)
    bundle.add(diff_art)
    bundle.add(collect_secret_scan_evidence(repo_root, allowed_files))
    # When a reviewer is genuinely assigned, record a NON-approving reviewer-
    # assignment artifact so the strict review gate's Clause C19 identity check
    # (builder ≠ reviewer) is reachable. It cannot fabricate an approval — the
    # verdict is fixed to ``needs_owner``, which never passes the review gate. No
    # reviewer assigned ⇒ nothing is added and behavior is unchanged.
    review_art = collect_reviewer_assignment_evidence(
        reviewer_id, diff_hash=str(diff_art.payload.get("head_commit") or "")
    )
    if review_art is not None:
        bundle.add(review_art)

    summary = run_gate_summary(packet, evidence_bundle=bundle, strict_evidence=True)
    return RefinementSignal(
        gate_summary=summary.to_dict(),
        ran=True,
        notes=(f"ran={run}",),
    )


__all__ = [
    "SAFE_COMMANDS",
    "RefinementSignal",
    "apply_clarifications",
    "run_execution_refinement",
]
