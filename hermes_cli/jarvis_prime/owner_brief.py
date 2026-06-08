"""Daily owner brief for MUSE.

Aggregates monitor results into a structured brief the owner can read in
under a minute:

* what changed
* what matters
* what needs approval
* what is blocked
* what JARVIS learned
* monitor coverage attestation (including blind spots)

Read-only: the brief is derived entirely from supplied monitor results and
optional learning/blocked notes. It performs no I/O and no owner-gated
actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Sequence

from hermes_cli.jarvis_prime.monitors import MonitorBoard, MonitorResult, Severity


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OwnerBrief:
    generated_at: str
    what_changed: list[str] = field(default_factory=list)
    what_matters: list[str] = field(default_factory=list)
    needs_approval: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    learned: list[str] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "what_changed": self.what_changed,
            "what_matters": self.what_matters,
            "needs_approval": self.needs_approval,
            "blocked": self.blocked,
            "learned": self.learned,
            "coverage": self.coverage,
        }

    def render(self) -> str:
        def section(title: str, items: Sequence[str]) -> list[str]:
            out = [f"## {title}"]
            out += [f"- {i}" for i in items] if items else ["- (nothing)"]
            return out

        cov = self.coverage
        cov_line = (
            f"- observed {cov.get('observed', 0)}/{cov.get('total', 0)} sources "
            f"(coverage {cov.get('coverage_ratio', 0):.0%})"
        )
        blind = cov.get("blind_spots", [])
        cov_items = [cov_line]
        if blind:
            cov_items.append("- BLIND SPOTS: " + ", ".join(blind))

        lines = [f"# JARVIS Owner Brief — {self.generated_at}", ""]
        lines += section("What changed", self.what_changed) + [""]
        lines += section("What matters", self.what_matters) + [""]
        lines += section("Needs approval", self.needs_approval) + [""]
        lines += section("Blocked", self.blocked) + [""]
        lines += section("What JARVIS learned", self.learned) + [""]
        lines += ["## Monitor coverage attestation"] + cov_items
        return "\n".join(lines)


def build_owner_brief(
    monitor_results: Sequence[MonitorResult],
    *,
    board: Optional[MonitorBoard] = None,
    learned: Sequence[str] = (),
    changed: Sequence[str] = (),
    blocked: Sequence[str] = (),
) -> OwnerBrief:
    board = board or MonitorBoard.default()
    coverage = board.coverage(list(monitor_results))

    what_matters: list[str] = []
    needs_approval: list[str] = []
    blocked_list = list(blocked)

    for r in monitor_results:
        if r.severity in (Severity.CRITICAL, Severity.WARNING):
            what_matters.append(f"[{r.severity.value}] {r.source}: {r.summary}")
        if r.needs_approval:
            needs_approval.append(f"{r.source}: {r.summary}")
        if r.severity == Severity.BLIND:
            # A blind monitor is surfaced as a coverage gap, not silently dropped.
            what_matters.append(f"[blind] {r.source}: {r.summary}")

    return OwnerBrief(
        generated_at=_now_iso(),
        what_changed=list(changed),
        what_matters=what_matters,
        needs_approval=needs_approval,
        blocked=blocked_list,
        learned=list(learned),
        coverage=coverage,
    )
