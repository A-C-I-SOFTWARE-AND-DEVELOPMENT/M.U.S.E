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

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence

from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_GIT_DIFF,
    ARTIFACT_OWNER_GRANT,
    ARTIFACT_REVIEW,
    ARTIFACT_ROLLBACK,
    ARTIFACT_SECRET_SCAN,
    ARTIFACT_TEST_RESULT,
    GuardrailEvidenceBundle,
)


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
    chain_finding = _axiom_chain_finding()
    if chain_finding:
        return GateResult(
            name=name,
            outcome=GateOutcome.FAIL,
            reason="axiom event chain failed verification",
            findings=(chain_finding,),
        )
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


def high_risk_owner_approval_gate(
    packet: Mapping[str, Any],
    base: Optional[Callable[[Mapping[str, Any]], GateResult]] = None,
) -> GateResult:
    """OwnerApproval when the *job itself* is the gated action.

    Used for HIGH-classified jobs (see ``axiom_bridge.classify_change``):
    regardless of declared action categories, a HIGH job waits for the
    exact authorization phrase. Once the phrase is present, the *base*
    evaluator (legacy or strict) still rules on declared actions.
    """

    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    name = "owner_approval"
    phrase = (_get(packet, "owner_authorization_phrase") or "").strip()
    if phrase != AUTHORIZATION_PHRASE:
        return GateResult(
            name=name,
            outcome=GateOutcome.NEEDS_OWNER_APPROVAL,
            reason=f"HIGH-risk job awaits exact phrase: {AUTHORIZATION_PHRASE!r}",
        )
    return (base or owner_approval_gate)(packet)


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
# Strict, evidence-bound gates
#
# These evaluators ignore self-attested packet fields entirely. They pass only
# when the matching captured artifact is present in the evidence bundle (and the
# bundle's ``packet_id`` matches the packet under evaluation, so a real bundle
# cannot be replayed against a different packet). The planning gate stays
# packet-level — planning *is* a statement of intent, not an observation.
# ---------------------------------------------------------------------------


# Risk-band ordering, mirrored from ``capability_wall._RC_ORDER``. Kept local so
# the review gate can compare bands without importing capability_wall (which
# imports this module — a lazy dependency, not a load-time cycle).
_RC_ORDER = {"RC0": 0, "RC1": 1, "RC2": 2, "RC3": 3, "RC4": 4}

# Clause C19: for RC2+ work, the agent that wrote the change may not be the one
# that approves it. The threshold band at/above which self-approval is blocked.
_C19_MIN_BAND = "RC2"


def _rc_at_or_above(risk_class: str, threshold: str) -> bool:
    """True when ``risk_class`` is at least as high a band as ``threshold``.

    Unknown bands are treated as RC1 (the packet default), matching
    ``capability_wall._packet_rc`` so a missing/garbled class is never silently
    escalated *or* silently exempted below RC2.
    """

    rc = _RC_ORDER.get(str(risk_class).upper(), _RC_ORDER["RC1"])
    return rc >= _RC_ORDER.get(threshold.upper(), _RC_ORDER["RC2"])


def _packet_id_mismatch(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> Optional[str]:
    pid = _get(packet, "packet_id")
    if pid and bundle.packet_id and str(pid) != str(bundle.packet_id):
        return f"evidence packet_id {bundle.packet_id!r} != packet {pid!r}"
    return None


def _strict_fail(name: str, reason: str, findings: Sequence[str] = ()) -> GateResult:
    return GateResult(name=name, outcome=GateOutcome.FAIL, reason=reason, findings=tuple(findings))


def strict_build_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    name = "build"
    mismatch = _packet_id_mismatch(packet, bundle)
    if mismatch:
        return _strict_fail(name, "evidence does not match packet", (mismatch,))
    arts = bundle.by_type(ARTIFACT_GIT_DIFF)
    if not arts:
        return _strict_fail(name, "no git_diff evidence captured")
    payload = arts[-1].payload
    if not payload.get("git_available", False):
        return _strict_fail(name, "git unavailable — cannot verify build scope")
    findings: list[str] = []
    oos = list(payload.get("out_of_scope_files") or [])
    if oos:
        findings.append(f"out-of-scope edits: {oos[:5]}")
    protected = list(payload.get("protected_files_touched") or [])
    if protected:
        findings.append(f"protected files touched: {protected}")
    if payload.get("diff_check_passed") is False:
        findings.append("git diff --check failed (whitespace/conflict markers)")
    if findings:
        return _strict_fail(name, "build outside scope (observed)", findings)
    changed = list(payload.get("changed_files") or [])
    return GateResult(name=name, outcome=GateOutcome.PASS, reason=f"observed diff in scope ({len(changed)} files)")


def strict_review_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    name = "review"
    arts = bundle.by_type(ARTIFACT_REVIEW)
    if not arts:
        return _strict_fail(name, "no review evidence captured")
    review = arts[-1]

    # Clause C19 gate: for RC2+ work the reviewer must not be the builder. The
    # reviewer identity is the review artifact's ``reviewer_id`` (falling back to
    # its producer); the builder identity is the producer of the captured
    # git_diff artifact — the agent that authored the change under review. A
    # self-approving review (reviewer == builder) is a hard FAIL, not a score.
    risk_class = str(_get(packet, "risk_class", "RC1"))
    if _rc_at_or_above(risk_class, _C19_MIN_BAND):
        reviewer = str(review.payload.get("reviewer_id") or review.producer or "").strip()
        diff_arts = bundle.by_type(ARTIFACT_GIT_DIFF)
        builder = str(diff_arts[-1].producer).strip() if diff_arts else ""
        if reviewer and builder and reviewer == builder:
            return _strict_fail(
                name,
                f"C19 self-approval blocked at {risk_class.upper()}: "
                f"reviewer {reviewer!r} is the change's builder",
                (f"reviewer_id={reviewer}", f"builder={builder}"),
            )

    verdict = str(review.payload.get("verdict", ""))
    if verdict in ("blocked", "request_changes"):
        return _strict_fail(name, f"reviewer verdict: {verdict}", (verdict,))
    if verdict == "needs_owner":
        return GateResult(name=name, outcome=GateOutcome.NEEDS_OWNER_APPROVAL, reason="review defers to owner")
    return GateResult(name=name, outcome=GateOutcome.PASS, reason=f"reviewer verdict: {verdict or 'approve'}")


def strict_test_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    name = "test"
    arts = bundle.by_type(ARTIFACT_TEST_RESULT)
    executed = [a for a in arts if a.payload.get("executed")]
    failed = [a for a in executed if not a.payload.get("passed")]
    skip_reason = _get(packet, "tests_skipped_reason") or _get(packet, "accepted_test_skip")
    if not executed:
        if skip_reason:
            return GateResult(name=name, outcome=GateOutcome.SKIPPED, reason=f"tests skipped: {skip_reason}")
        return _strict_fail(name, "no executed test evidence (planned commands do not count)")
    if failed:
        cmds = [str(a.payload.get("command")) for a in failed]
        return _strict_fail(name, "test command(s) failed", cmds[:5])
    return GateResult(name=name, outcome=GateOutcome.PASS, reason=f"tests executed and passed ({len(executed)})")


def strict_security_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    name = "security"
    diff_arts = bundle.by_type(ARTIFACT_GIT_DIFF)
    files_changed = list(diff_arts[-1].payload.get("changed_files") or []) if diff_arts else []
    scans = bundle.by_type(ARTIFACT_SECRET_SCAN)
    if files_changed and not scans:
        return _strict_fail(name, "code changed but no secret_scan evidence captured")
    if scans and not scans[-1].payload.get("clean", True):
        count = scans[-1].payload.get("finding_count", 0)
        return _strict_fail(name, f"secret scan flagged {count} finding(s)")
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="secret scan clean over changed files")


def strict_release_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    name = "release"
    # Packet-level *intent* fields a release narrative legitimately owns.
    missing = [
        label
        for field_name, label in (
            ("verification_summary", "verification summary"),
            ("non_goals", "non-goals"),
            ("remaining_risks", "remaining risks"),
            ("rollback_plan", "rollback plan"),
        )
        if not _has(packet, field_name)
    ]
    if missing:
        return _strict_fail(name, "release packet incomplete", missing)
    # Observed evidence: a real diff and a real rollback must back the release.
    if not bundle.has(ARTIFACT_GIT_DIFF):
        return _strict_fail(name, "release packet present but no git_diff evidence")
    if not bundle.has(ARTIFACT_ROLLBACK):
        return _strict_fail(name, "release packet present but no rollback evidence")
    chain_finding = _axiom_chain_finding()
    if chain_finding:
        return _strict_fail(name, "axiom event chain failed verification", (chain_finding,))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="release packet backed by evidence bundle")


def strict_owner_approval_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    from hermes_cli.jarvis_prime.owner_auth import OWNER_GATED_ACTIONS

    name = "owner_approval"
    pending = list(_get(packet, "owner_gated_actions") or [])
    if not pending:
        return GateResult(name=name, outcome=GateOutcome.PASS, reason="no owner-gated action pending")
    unknown = [a for a in pending if a not in OWNER_GATED_ACTIONS]
    if unknown:
        return _strict_fail(name, "unknown owner-gated action category", tuple(f"unknown: {a}" for a in unknown))
    grants = bundle.by_type(ARTIFACT_OWNER_GRANT)
    granted_actions = {str(g.payload.get("action")) for g in grants}
    missing = [a for a in pending if a not in granted_actions]
    if missing:
        return GateResult(
            name=name,
            outcome=GateOutcome.NEEDS_OWNER_APPROVAL,
            reason="challenge-bound owner authorization missing",
            findings=tuple(f"pending: {a}" for a in missing),
        )
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="challenge-bound owner authorization captured")


def strict_rollback_gate(packet: Mapping[str, Any], bundle: GuardrailEvidenceBundle) -> GateResult:
    name = "rollback"
    arts = bundle.by_type(ARTIFACT_ROLLBACK)
    if not arts:
        return _strict_fail(name, "no rollback evidence captured")
    payload = arts[-1].payload
    if not payload.get("plausible", False):
        return _strict_fail(name, "rollback plan not operationally plausible", tuple(payload.get("reasons") or ()))
    return GateResult(name=name, outcome=GateOutcome.PASS, reason="rollback plan validated")


CAPABILITY_GATE_ENV = "HERMES_CAPABILITY_GATE"


def _capability_gate_enabled() -> bool:
    return os.environ.get(CAPABILITY_GATE_ENV, "").lower() in {"1", "true", "yes", "on"}


def _axiom_chain_finding() -> Optional[str]:
    """Release objection when the axiom event chain fails verification.

    None (no objection) when the bridge is inert, no chain exists yet,
    or the bridge itself is unavailable — "ship" only means "history
    verifies" once there is a history to verify. Never raises.
    """
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        bridge = get_bridge()
        if bridge.inert or not bridge.chain_exists():
            return None
        audit = bridge.audit()
        if audit.get("chain_valid") is not True:
            return (
                f"chain invalid at {audit.get('chain_path')} "
                f"(first_bad_seq={audit.get('first_bad_seq')})"
            )
    except Exception:
        return None
    return None


def _chain_summary(packet: Mapping[str, Any], summary: "GateSummary") -> None:
    """Soft hook: append the gate run to the axiom event chain.

    Never raises into the host — a broken or absent bridge must not
    change gate behavior.
    """
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        bridge = get_bridge()
        if bridge.inert:
            return
        bridge.record_event(
            "gate.summary",
            {
                "packet_id": str(_get(packet, "packet_id") or ""),
                "overall": summary.overall.value,
                "results": [r.to_dict() for r in summary.results],
            },
        )
    except Exception:
        pass


def _strict_gates(bundle: GuardrailEvidenceBundle) -> tuple[Gate, ...]:
    """Build a gate list whose evidence-bound members close over ``bundle``.

    When ``HERMES_CAPABILITY_GATE`` is enabled, the opt-in capability gate is
    appended — RC2+ work then requires a passing ``capability_attestation`` in
    the bundle (see ``capability_wall.py``). It is absent by default, so the
    default strict suite and every existing strict-gate test are unchanged.
    """

    def bind(fn):
        return lambda packet: fn(packet, bundle)

    gates = [
        Gate("planning", planning_gate),
        Gate("build", bind(strict_build_gate)),
        Gate("review", bind(strict_review_gate)),
        Gate("test", bind(strict_test_gate)),
        Gate("security", bind(strict_security_gate)),
        Gate("release", bind(strict_release_gate)),
        Gate("owner_approval", bind(strict_owner_approval_gate)),
        Gate("rollback", bind(strict_rollback_gate)),
    ]
    if _capability_gate_enabled():
        # Lazy import avoids a module-load cycle (capability_wall imports gates).
        from hermes_cli.jarvis_prime.capability_wall import capability_gate

        gates.append(
            Gate("capability", lambda packet: capability_gate(packet, bundle, enabled=True))
        )
    return tuple(gates)


def gates_for_profile(
    names: Sequence[str],
    *,
    evidence_bundle: Optional[GuardrailEvidenceBundle] = None,
    strict_evidence: bool = False,
    high_risk: bool = False,
) -> tuple[Gate, ...]:
    """Resolve a risk-profile gate-name list to runnable gates.

    Names come from ``axiom_bridge.classify_change()["gates"]``. With
    ``strict_evidence`` the evidence-bound evaluators are used (a missing
    bundle is treated as empty, so self-attestation fails by design).
    With ``high_risk`` the owner_approval member treats the job itself
    as the gated action. Unknown names are ignored rather than invented.
    """
    if strict_evidence:
        bundle = evidence_bundle or GuardrailEvidenceBundle(packet_id="")
        pool = {g.name: g for g in _strict_gates(bundle)}
    else:
        pool = {g.name: g for g in GATES}
    if high_risk and "owner_approval" in pool:
        base = pool["owner_approval"].evaluator
        pool["owner_approval"] = Gate(
            "owner_approval",
            lambda packet, _base=base: high_risk_owner_approval_gate(packet, _base),
        )
    wanted = [str(n).strip().lower() for n in names]
    return tuple(pool[n] for n in wanted if n in pool)


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
    *,
    evidence_bundle: Optional[GuardrailEvidenceBundle] = None,
    strict_evidence: bool = False,
) -> GateSummary:
    """Run every gate against the work packet and return a GateSummary.

    By default (``strict_evidence=False``) the legacy packet-level gates run —
    this preserves all existing behavior and tests. In **strict evidence mode**
    the six evidence-bound gates (build, review, test, security, release,
    rollback, owner_approval) ignore self-attested packet fields and pass only on
    captured artifacts in ``evidence_bundle``. A missing bundle is treated as an
    *empty* bundle, so a self-attested packet fails strict mode by construction.

    An explicit ``gates`` sequence always wins (used by focused gate tests).
    """

    if gates is None:
        if strict_evidence:
            bundle = evidence_bundle or GuardrailEvidenceBundle(
                packet_id=str(_get(packet, "packet_id") or "")
            )
            gates = _strict_gates(bundle)
        else:
            gates = GATES
    summary = GateSummary(results=tuple(g.evaluate(packet) for g in gates))
    _chain_summary(packet, summary)
    return summary


def run_strict_gate_summary(
    packet: Mapping[str, Any],
    evidence_bundle: Optional[GuardrailEvidenceBundle] = None,
    gates: Optional[Sequence[Gate]] = None,
) -> GateSummary:
    """Convenience wrapper that forces strict, evidence-bound evaluation."""

    return run_gate_summary(
        packet,
        gates=gates,
        evidence_bundle=evidence_bundle,
        strict_evidence=True,
    )
