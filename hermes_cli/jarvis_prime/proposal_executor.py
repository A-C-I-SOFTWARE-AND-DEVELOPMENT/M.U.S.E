"""Approved-proposal executor for JARVIS Prime.

Bridges :mod:`self_update` proposals to bounded coding work packets. It
turns an *approved* proposal into an executable plan (branch name, exact
test commands, rollback plan, packet artifact) — but it **never merges,
deploys, or publishes**, and it never makes GitHub writes unless explicitly
invoked in a non-draft mode by the owner.

It integrates with :mod:`natural_language_coder`: the diff intent of the
proposal is packetized through the same gate-compatible pipeline used for
plain-English requests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingWorkPacket,
    build_work_packet,
    validate_work_packet,
)
from hermes_cli.jarvis_prime.self_update import Proposal, ProposalStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())[:8]
    return "-".join(words) or "proposal"


@dataclass(frozen=True)
class ExecutionPlan:
    """A bounded, owner-gated plan derived from an approved proposal."""

    proposal_kind: str
    target_path: str
    branch: str
    packet: CodingWorkPacket
    test_commands: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    owner_gates: tuple[str, ...]
    draft_only: bool = True
    generated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "proposal_kind": self.proposal_kind,
            "target_path": self.target_path,
            "branch": self.branch,
            "packet": self.packet.to_dict(),
            "test_commands": list(self.test_commands),
            "rollback_plan": list(self.rollback_plan),
            "owner_gates": list(self.owner_gates),
            "draft_only": self.draft_only,
            "generated_at": self.generated_at,
            "warning": (
                "Plan only — JARVIS does not merge, deploy, or publish. "
                "GitHub writes require explicit owner action."
            ),
        }

    def render(self) -> str:
        lines = [
            f"EXECUTION PLAN — {self.proposal_kind} @ {self.target_path}",
            f"branch: {self.branch}  (draft_only={self.draft_only})",
            "tests:",
            *[f"  - {c}" for c in self.test_commands],
            "rollback:",
            *[f"  - {c}" for c in self.rollback_plan],
        ]
        if self.owner_gates:
            lines.append("owner gates: " + ", ".join(self.owner_gates))
        return "\n".join(lines)

    def write_artifact(self, directory: Path) -> Path:
        """Write the plan as a JSON artifact (no GitHub interaction)."""

        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"plan-{self.branch.replace('/', '-')}.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return path


# Test command recommendations keyed by where the proposal lands.
_TEST_COMMANDS_BY_AREA: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "hermes_cli/jarvis_prime",
        (
            "python -m compileall -q hermes_cli/jarvis_prime",
            "pytest -q tests/test_jarvis_prime_*.py",
        ),
    ),
    (
        "gateway",
        (
            "python -m compileall -q gateway",
            "pytest -q tests/gateway/",
        ),
    ),
    ("apps/android", ("cd apps/android && ./gradlew test",)),
    ("skills/", ("python -m hermes_cli.jarvis_prime --help",)),
    ("docs/", ("verify documented commands run; verify links resolve",)),
)


def _test_commands_for(target_path: str) -> tuple[str, ...]:
    for prefix, cmds in _TEST_COMMANDS_BY_AREA:
        if target_path.startswith(prefix) or prefix in target_path:
            return cmds
    return ("python -m compileall -q hermes_cli", "pytest -q")


class ProposalNotApproved(ValueError):
    """Raised when a non-approved proposal is handed to the executor."""


def build_execution_plan(
    proposal: Proposal,
    *,
    repo_root: str = ".",
    branch_prefix: str = "jarvis",
    draft_only: bool = True,
    require_approved: bool = True,
) -> ExecutionPlan:
    """Turn an approved proposal into a bounded execution plan.

    Raises :class:`ProposalNotApproved` if ``require_approved`` and the
    proposal is not in the APPROVED state — JARVIS never plans execution of
    something the owner has not signed off on.
    """

    if require_approved and proposal.status != ProposalStatus.APPROVED:
        raise ProposalNotApproved(
            f"proposal status is {proposal.status.value}, expected approved"
        )

    # Packetize the diff intent through the standard pipeline so the plan
    # inherits risk classification, owner gates, and validation.
    packet = build_work_packet(
        proposal.diff_intent or proposal.rationale,
        repo_root=repo_root,
        branch_prefix=branch_prefix,
        allowed_files=[proposal.target_path],
    )

    # Use the proposal's slug for a stable branch name.
    branch = (
        f"{branch_prefix}/{_slug(proposal.target_path + ' ' + proposal.diff_intent)}"
    )
    packet = CodingWorkPacket(**{**_packet_kwargs(packet), "branch": branch})

    test_commands = _test_commands_for(proposal.target_path)
    rollback = (
        f"git checkout {branch} is isolated; drop the branch / PR to fully revert",
        "no merge/deploy/publish performed by the executor",
    )
    owner_gates = [g.value for g in packet.owner_gates]
    if proposal.risk_class in ("RC3", "RC4"):
        owner_gates = list(dict.fromkeys([*owner_gates, "owner_approval_required"]))

    return ExecutionPlan(
        proposal_kind=proposal.kind.value,
        target_path=proposal.target_path,
        branch=branch,
        packet=packet,
        test_commands=test_commands,
        rollback_plan=rollback,
        owner_gates=tuple(owner_gates),
        draft_only=draft_only,
    )


def validate_execution_plan(plan: ExecutionPlan):
    """Validate the underlying work packet. Returns a PacketValidationResult."""

    return validate_work_packet(plan.packet)


def _packet_kwargs(packet: CodingWorkPacket) -> dict:
    from dataclasses import fields

    return {f.name: getattr(packet, f.name) for f in fields(packet)}
