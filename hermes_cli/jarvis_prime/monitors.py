"""Continuous monitors for muse — fail-visible, read-only.

Monitors observe a source, classify severity, and — crucially — track
per-source last-success timestamps and failure counts so a *silent*
monitor (a blind spot) is itself visible. Nothing here mutates state or
performs owner-gated actions; monitors are pure observation.

Each monitor implements ``check(context) -> MonitorResult``. The context
is a plain mapping the caller assembles (repo state, open PRs, test
results, etc.) so monitors stay testable and free of I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Severity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLIND = "blind"  # the monitor could not observe its source at all


@dataclass(frozen=True)
class MonitorResult:
    source: str
    severity: Severity
    summary: str
    findings: tuple[str, ...] = ()
    observed_at: str = field(default_factory=_now_iso)
    needs_approval: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "severity": self.severity.value,
            "summary": self.summary,
            "findings": list(self.findings),
            "observed_at": self.observed_at,
            "needs_approval": self.needs_approval,
        }


@dataclass
class Monitor:
    name: str
    checker: Callable[[Mapping[str, Any]], MonitorResult]
    last_success_at: Optional[str] = None
    failure_count: int = 0

    def check(self, context: Mapping[str, Any]) -> MonitorResult:
        try:
            result = self.checker(context)
        except Exception as exc:  # a throwing monitor is a blind spot, not a crash
            self.failure_count += 1
            return MonitorResult(
                source=self.name,
                severity=Severity.BLIND,
                summary=f"monitor raised: {exc}",
                findings=(str(exc),),
            )
        if result.severity == Severity.BLIND:
            self.failure_count += 1
        else:
            self.last_success_at = result.observed_at
        return result


# ---------------------------------------------------------------------------
# Individual checkers (read-only; operate on a supplied context mapping)
# ---------------------------------------------------------------------------


def _missing(context: Mapping[str, Any], key: str) -> bool:
    return key not in context or context.get(key) is None


def repo_state_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "repo_state"
    if _missing(context, "repo"):
        return MonitorResult(name, Severity.BLIND, "no repo snapshot supplied")
    repo = context["repo"]
    dirty = bool(repo.get("dirty"))
    branch = repo.get("branch", "?")
    if dirty:
        return MonitorResult(
            name,
            Severity.WARNING,
            f"working tree dirty on {branch}",
            findings=tuple(repo.get("changed_files", []))[:10],
        )
    return MonitorResult(name, Severity.OK, f"clean working tree on {branch}")


def open_pr_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "open_prs"
    if _missing(context, "open_prs"):
        return MonitorResult(name, Severity.BLIND, "no PR data supplied")
    prs = context["open_prs"]
    stale = [p for p in prs if p.get("stale")]
    if stale:
        return MonitorResult(
            name,
            Severity.WARNING,
            f"{len(stale)} stale PR(s)",
            findings=tuple(f"#{p.get('number')}" for p in stale),
        )
    return MonitorResult(name, Severity.OK, f"{len(prs)} open PR(s), none stale")


def failing_tests_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "failing_tests"
    if _missing(context, "tests"):
        return MonitorResult(name, Severity.BLIND, "no test results supplied")
    tests = context["tests"]
    failed = list(tests.get("failed", []))
    if failed:
        return MonitorResult(
            name,
            Severity.CRITICAL,
            f"{len(failed)} failing test(s)",
            findings=tuple(failed)[:10],
        )
    return MonitorResult(name, Severity.OK, f"{tests.get('passed', 0)} passing")


def stale_docs_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "stale_docs"
    if _missing(context, "docs"):
        return MonitorResult(name, Severity.BLIND, "no docs freshness data supplied")
    stale = [d for d in context["docs"] if d.get("stale")]
    if stale:
        return MonitorResult(
            name,
            Severity.INFO,
            f"{len(stale)} doc(s) past freshness",
            findings=tuple(d.get("path", "?") for d in stale)[:10],
        )
    return MonitorResult(name, Severity.OK, "docs within freshness window")


def memory_contradiction_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "memory_contradictions"
    if _missing(context, "open_contradictions"):
        return MonitorResult(
            name, Severity.BLIND, "no memory contradiction data supplied"
        )
    open_c = context["open_contradictions"]
    if open_c:
        return MonitorResult(
            name,
            Severity.WARNING,
            f"{len(open_c)} unresolved contradiction(s)",
            findings=tuple(str(c) for c in open_c)[:10],
            needs_approval=True,
        )
    return MonitorResult(name, Severity.OK, "no open memory contradictions")


def skill_proposal_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "skill_proposals"
    if _missing(context, "pending_proposals"):
        return MonitorResult(name, Severity.BLIND, "no proposal data supplied")
    pending = context["pending_proposals"]
    if pending:
        return MonitorResult(
            name,
            Severity.INFO,
            f"{len(pending)} proposal(s) awaiting owner",
            needs_approval=True,
        )
    return MonitorResult(name, Severity.OK, "no pending proposals")


def model_failure_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "model_failures"
    if _missing(context, "model_failures"):
        return MonitorResult(name, Severity.BLIND, "no model telemetry supplied")
    fails = context["model_failures"]
    if fails:
        return MonitorResult(
            name,
            Severity.WARNING,
            f"{len(fails)} model failure(s) recorded",
            findings=tuple(str(f) for f in fails)[:10],
        )
    return MonitorResult(name, Severity.OK, "no recent model failures")


def android_capability_checker(context: Mapping[str, Any]) -> MonitorResult:
    name = "android_capability"
    if _missing(context, "android"):
        return MonitorResult(
            name, Severity.BLIND, "no Android capability snapshot supplied"
        )
    android = context["android"]
    missing = [k for k, v in android.items() if not v]
    if missing:
        return MonitorResult(
            name,
            Severity.INFO,
            "some Android capabilities unavailable",
            findings=tuple(missing),
        )
    return MonitorResult(name, Severity.OK, "Android capabilities present")


def behavioral_drift_checker(context: Mapping[str, Any]) -> MonitorResult:
    """Detect Article VI risk dynamics from recent worker actions.

    Read-only: classifies ``context['worker_actions']`` via ``behavioral_risk``
    (privilege escalation, destructive cleanup/workaround, scope creep, reward
    hacking). Blind — a visible gap — when no action history is supplied.
    """

    name = "behavioral_drift"
    if _missing(context, "worker_actions"):
        return MonitorResult(name, Severity.BLIND, "no worker action history supplied")
    from hermes_cli.jarvis_prime.behavioral_risk import classify

    findings = classify(context["worker_actions"])
    if not findings:
        return MonitorResult(name, Severity.OK, "no behavioral-risk findings")
    fatal = [f for f in findings if f.severity == "fatal"]
    severity = Severity.CRITICAL if fatal else Severity.WARNING
    return MonitorResult(
        name,
        severity,
        f"{len(findings)} behavioral-risk finding(s), {len(fatal)} fatal",
        findings=tuple(
            f"{f.category.value}[{f.worker_id}]: {', '.join(f.evidence)}"
            for f in findings
        )[:10],
        needs_approval=bool(fatal),
    )


DEFAULT_MONITORS: tuple[tuple[str, Callable], ...] = (
    ("repo_state", repo_state_checker),
    ("open_prs", open_pr_checker),
    ("failing_tests", failing_tests_checker),
    ("stale_docs", stale_docs_checker),
    ("memory_contradictions", memory_contradiction_checker),
    ("skill_proposals", skill_proposal_checker),
    ("model_failures", model_failure_checker),
    ("android_capability", android_capability_checker),
    ("behavioral_drift", behavioral_drift_checker),
)


@dataclass
class MonitorBoard:
    monitors: list[Monitor] = field(default_factory=list)

    @classmethod
    def default(cls) -> "MonitorBoard":
        return cls(monitors=[Monitor(name=n, checker=c) for n, c in DEFAULT_MONITORS])

    def run(self, context: Mapping[str, Any]) -> list[MonitorResult]:
        return [m.check(context) for m in self.monitors]

    def coverage(self, results: list[MonitorResult]) -> dict[str, object]:
        blind = [r.source for r in results if r.severity == Severity.BLIND]
        return {
            "total": len(results),
            "observed": len(results) - len(blind),
            "blind_spots": blind,
            "coverage_ratio": round((len(results) - len(blind)) / len(results), 3)
            if results
            else 0.0,
        }
