"""Job replay — reconstruct what an orchestrated job did, from its ledger.

``hermes orchestrate replay <job-id>`` reads the canonical per-job ledger
(``~/.hermes/jobs/<job-id>/ledger.jsonl``) and reconstructs the decision
sequence: navigation choices, worker dispatches, validation gates, repair-loop
steps, and owner-gate events. It is **read-only** — replay never re-executes
side effects, never merges, never publishes. It exists so an owner (or a test)
can audit *why* a job did what it did, deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from muse_cli import orchestrator_ledger as _ledger


@dataclass(frozen=True)
class ReplayStep:
    index: int
    kind: str
    summary: str
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "kind": self.kind, "summary": self.summary}


@dataclass
class JobReplay:
    job_id: str
    steps: list[ReplayStep] = field(default_factory=list)

    @classmethod
    def load(
        cls, job_id: str, *, entries: Optional[list[dict[str, Any]]] = None
    ) -> "JobReplay":
        raw_entries = entries if entries is not None else _ledger.read(job_id)
        steps: list[ReplayStep] = []
        for idx, entry in enumerate(raw_entries):
            kind = str(entry.get("kind") or entry.get("type") or "entry")
            steps.append(
                ReplayStep(
                    index=idx, kind=kind, summary=_summarize(kind, entry), raw=entry
                )
            )
        return cls(job_id=job_id, steps=steps)

    @property
    def is_empty(self) -> bool:
        return not self.steps

    def by_kind(self, kind: str) -> list[ReplayStep]:
        return [s for s in self.steps if s.kind == kind]

    def render(self) -> str:
        if self.is_empty:
            return f"Job {self.job_id}: no ledger entries found (nothing to replay)."
        lines = [f"Replay of job {self.job_id} — {len(self.steps)} step(s):"]
        for s in self.steps:
            lines.append(f"  [{s.index:>3}] {s.kind}: {s.summary}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
        }


def _summarize(kind: str, entry: dict[str, Any]) -> str:
    if kind == "navigation_decision":
        files = entry.get("ranked_files") or []
        top = files[0]["path"] if files and isinstance(files[0], dict) else "?"
        return f"localized → {top} (+{max(0, len(files) - 1)} more)"
    if kind in {"goal_boundary_verdict"}:
        return f"{entry.get('decision', '?')}: {entry.get('reason', '')}"
    if kind == "goal_boundary_declared":
        b = entry.get("boundary", {})
        return (
            f"objective={b.get('objective', '?')!r} max_iter={b.get('max_iterations')}"
        )
    if kind in {"repair_loop_step"}:
        phase = entry.get("phase", "?")
        if phase == "test":
            return f"test passed={entry.get('passed')} failing={entry.get('failing_tests')}"
        return f"{phase}: {entry.get('summary') or entry.get('candidate_files') or ''}"
    if kind == "repair_loop_result":
        return f"succeeded={entry.get('succeeded')} ({entry.get('stop_reason')})"
    # Generic fallback: surface a few useful fields.
    for key in ("decision", "summary", "message", "action", "status", "reason"):
        if key in entry:
            return f"{key}={entry[key]}"
    return ", ".join(f"{k}={v}" for k, v in list(entry.items())[:3] if k != "kind")


def replay_job(job_id: str) -> JobReplay:
    return JobReplay.load(job_id)
