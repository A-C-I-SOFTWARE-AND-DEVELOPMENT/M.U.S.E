"""Eight JARVIS verification gates.

Implements the gates from ``docs/jarvis-verification-gates.md``:

1. Planning gate — mission clear before execution.
2. Build gate — implementation stays inside scope.
3. Review gate — weak logic / regression / scope-creep.
4. Test gate — local verification when tools available.
5. Security gate — credential / privacy / supply-chain / unsafe.
6. Release gate — PR / release ready.
7. Owner Approval gate — preserve owner control on high-impact.
8. Rollback gate — make changes reversible.

Each ``Gate.evaluate(packet)`` returns a ``GateResult`` with outcome
PASS / FAIL / NEEDS_OWNER_APPROVAL plus a reason. ``run_gate_summary``
runs all eight and renders the gate-summary template from the doc.

The gate signatures are intentionally permissive — they read fields
out of a duck-typed mapping. Callers can pass a dataclass with
``__dict__`` or a plain dict; missing fields default to "not provided"
and surface as gate failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence


class GateOutcome(Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_OWNER_APPROVAL = "needs_owner_approval"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class GateResult:
    name: str
    outcome: GateOutcome
    reason: str
    findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "findings": list(self.findings),
        }


@dataclass
class Gate:
    name: str
    evaluator: Callable[[Mapping[str, Any]], GateResult]

    def evaluate(self, packet: Mapping[str, Any]) -> GateResult:
        return self.evaluator(packet)


def _get(packet: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if hasattr(packet, "__dict__") and not isinstance(packet, Mapping):
        return getattr(packet, key, default)
    return packet.get(key, default) if isinstance(packet, Mapping) else default


def _has(packet: Mapping[str, Any], key: str) -> bool:
    value = _get(packet, key)
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, set, dict)) and len(value) == 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Individual gate evaluators
# ---------------------------------------------------------------------------


def planning_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "planning"
    missing = []
    for field_name, label in (
        ("repo_root", "repo root"),
        ("branch", "branch"),
        ("mission", "goal/mission"),
        ("allowed_files", "allowed files list"),
        ("non_goals", "non-goals"),
        ("acceptance_criteria", "acceptance criteria"),
    ):
        if not _has(packet, field_name):
            missing.append(label)

    if missing:
        return GateResult(
            name=name,
            outcome=GateOutcome.FAIL,
            reason="missing required planning fields",
            findings=tuple(missing),
        )
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="planning fields present")


def build_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "build"
    findings: list[str] = []

    allowed = set(_get(packet, "allowed_files", []) or [])
    files_changed = list(_get(packet, "files_changed", []) or [])
    protected = set(_get(packet, "protected_files", []) or [])

    if allowed:
        out_of_scope = [f for f in files_changed if f not in allowed]
        if out_of_scope:
            findings.append(f"out-of-scope edits: {out_of_scope[:5]}")

    protected_touched = [f for f in files_changed if f in protected]
    if protected_touched:
        findings.append(f"protected files touched without approval: {protected_touched}")

    concurrent = _get(packet, "concurrent_editors") or []
    if isinstance(concurrent, (list, tuple, set)) and len(set(concurrent)) > 1:
        findings.append(f"concurrent editors on the same branch: {sorted(set(concurrent))}")

    secrets = _get(packet, "secrets_added") or []
    if secrets:
        findings.append(f"secrets added: {len(secrets)}")

    if findings:
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="build outside scope", findings=tuple(findings))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="build stayed in scope")


def review_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "review"
    findings: list[str] = []
    if not _has(packet, "diff_reviewed"):
        findings.append("diff not reviewed")
    blocking = _get(packet, "blocking_findings") or []
    if blocking:
        findings.extend(f"blocking: {b}" for b in blocking[:5])
    if not _has(packet, "contrarian_objection"):
        findings.append("contrarian objection not stated")

    if any(f.startswith("blocking:") for f in findings):
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="blocking review findings", findings=tuple(findings))
    if findings:
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="review incomplete", findings=tuple(findings))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="review complete with citations")


def test_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "test"
    findings: list[str] = []
    tests_run = _get(packet, "tests_run") or []
    tests_failed = _get(packet, "tests_failed") or []
    tests_skipped_reason = _get(packet, "tests_skipped_reason")
    diff_check = _get(packet, "git_diff_check_passed")

    if not tests_run:
        if not tests_skipped_reason:
            findings.append("no tests run and no skip reason")
        else:
            return GateResult(
                name=name,
                outcome=GateOutcome.SKIPPED,
                reason=f"tests skipped: {tests_skipped_reason}",
            )
    if tests_failed:
        findings.append(f"failed tests: {list(tests_failed)[:5]}")
    if diff_check is False:
        findings.append("git diff --check failed")

    if findings:
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="test gate failure", findings=tuple(findings))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason=f"tests ran ({len(tests_run)})")


def security_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "security"
    findings: list[str] = []
    files_changed = list(_get(packet, "files_changed", []) or [])
    if _get(packet, "secrets_added"):
        findings.append("secret content added")
    sensitive = [f for f in files_changed if f.endswith(".env") or "credentials" in f.lower()]
    if sensitive and not _get(packet, "env_edit_approved"):
        findings.append(f"sensitive file edits without approval: {sensitive}")
    if _get(packet, "dependency_changed") and not _get(packet, "dependency_review_separate"):
        findings.append("dependency change not isolated to its own review")
    network_calls = _get(packet, "network_calls_added") or []
    if network_calls and _get(packet, "scope") == "local-only":
        findings.append("network calls added to local-only scope")

    risky_actions = _get(packet, "risky_actions") or []
    if risky_actions:
        approved = _get(packet, "owner_approved") is True
        if not approved:
            return GateResult(
                name=name,
                outcome=GateOutcome.NEEDS_OWNER_APPROVAL,
                reason="risky action awaits owner authorization",
                findings=tuple(f"risky: {a}" for a in risky_actions),
            )

    if findings:
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="security findings", findings=tuple(findings))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="security gate clean")


def release_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "release"
    missing: list[str] = []
    for field_name, label in (
        ("files_changed", "changed files list"),
        ("commits_scoped", "scoped commits"),
        ("verification_summary", "verification summary"),
        ("non_goals", "non-goals"),
        ("remaining_risks", "remaining risks"),
        ("rollback_plan", "rollback plan"),
    ):
        if not _has(packet, field_name):
            missing.append(label)
    if missing:
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="release packet incomplete", findings=tuple(missing))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="release packet ready")


def owner_approval_gate(packet: Mapping[str, Any]) -> GateResult:
    """Gate any owner-gated action on the exact authorization phrase."""

    from hermes_cli.jarvis_prime.owner_auth import (
        AUTHORIZATION_PHRASE,
        OWNER_GATED_ACTIONS,
    )

    name = "owner_approval"
    pending = _get(packet, "owner_gated_actions") or []
    if not pending:
        return GateResult(name=name, outcome=GateOutcome.PASS, reason="no owner-gated action pending")

    unknown = [a for a in pending if a not in OWNER_GATED_ACTIONS]
    if unknown:
        return GateResult(
            name=name,
            outcome=GateOutcome.FAIL,
            reason="unknown owner-gated action category",
            findings=tuple(f"unknown: {a}" for a in unknown),
        )

    phrase = (_get(packet, "owner_authorization_phrase") or "").strip()
    if phrase != AUTHORIZATION_PHRASE:
        return GateResult(
            name=name,
            outcome=GateOutcome.NEEDS_OWNER_APPROVAL,
            reason=f"awaiting exact phrase: {AUTHORIZATION_PHRASE!r}",
            findings=tuple(f"pending: {a}" for a in pending),
        )

    return GateResult(name=name, outcome=GateOutcome.PASS, reason="owner authorization captured")


def rollback_gate(packet: Mapping[str, Any]) -> GateResult:
    name = "rollback"
    missing: list[str] = []
    if not _has(packet, "rollback_plan"):
        missing.append("rollback plan")
    if not _has(packet, "commit_hash") and not _has(packet, "files_changed"):
        missing.append("commit hash or file list for revert")
    if missing:
        return GateResult(name=name, outcome=GateOutcome.FAIL, reason="rollback unrecoverable", findings=tuple(missing))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="rollback path documented")


GATES: tuple[Gate, ...] = (
    Gate("planning", planning_gate),
    Gate("build", build_gate),
    Gate("review", review_gate),
    Gate("test", test_gate),
    Gate("security", security_gate),
    Gate("release", release_gate),
    Gate("owner_approval", owner_approval_gate),
    Gate("rollback", rollback_gate),
)


# ---------------------------------------------------------------------------
# Gate summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateSummary:
    results: tuple[GateResult, ...]

    @property
    def overall(self) -> GateOutcome:
        outcomes = [r.outcome for r in self.results]
        if any(o == GateOutcome.FAIL for o in outcomes):
            return GateOutcome.FAIL
        if any(o == GateOutcome.NEEDS_OWNER_APPROVAL for o in outcomes):
            return GateOutcome.NEEDS_OWNER_APPROVAL
        if all(o in (GateOutcome.PASS, GateOutcome.SKIPPED) for o in outcomes):
            return GateOutcome.PASS
        return GateOutcome.FAIL

    @property
    def remaining_risk(self) -> str:
        bits: list[str] = []
        for r in self.results:
            if r.outcome in (GateOutcome.FAIL, GateOutcome.NEEDS_OWNER_APPROVAL):
                bits.append(f"[{r.name}:{r.outcome.value}] {r.reason}")
        return "; ".join(bits) or "none"

    def render(self) -> str:
        """Render the GATE SUMMARY template from the doc."""

        by_name = {r.name: r for r in self.results}

        def line(label: str, key: str) -> str:
            r = by_name.get(key)
            if r is None:
                return f"{label} gate:"
            return f"{label} gate: {r.outcome.value} — {r.reason}"

        return (
            "GATE SUMMARY\n"
            f"{line('Planning', 'planning')}\n"
            f"{line('Build', 'build')}\n"
            f"{line('Review', 'review')}\n"
            f"{line('Test', 'test')}\n"
            f"{line('Security', 'security')}\n"
            f"{line('Release', 'release')}\n"
            f"{line('Owner approval', 'owner_approval')}\n"
            f"{line('Rollback', 'rollback')}\n"
            f"Result: {self.overall.value}\n"
            f"Remaining risk: {self.remaining_risk}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "results": [r.to_dict() for r in self.results],
            "overall": self.overall.value,
            "remaining_risk": self.remaining_risk,
        }


def run_gate_summary(
    packet: Mapping[str, Any],
    gates: Optional[Sequence[Gate]] = None,
) -> GateSummary:
    """Run every gate against the work packet and return a GateSummary."""

    gates = gates or GATES
    return GateSummary(results=tuple(g.evaluate(packet) for g in gates))
