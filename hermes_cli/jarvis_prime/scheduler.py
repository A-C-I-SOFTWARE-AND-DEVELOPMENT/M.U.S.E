"""Recurring-task scheduler for the autonomy lanes (forge / autoresearch / SIA).

Lets the owner register recurring tasks and computes which are **due** — the
deterministic, testable core. Running a due task delegates to an injected runner;
the default runner executes the offline forge tournament directly but **refuses**
the heavy, owner-gated lanes (autoresearch / SIA) unless explicitly authorized,
so the scheduler never silently launches an owner-gated job.

State persists at ``${HERMES_HOME:-~/.hermes}/scheduler.json``.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

__all__ = ["ScheduledTask", "Scheduler", "default_runner", "OWNER_GATED_KINDS"]

OWNER_GATED_KINDS = frozenset({"autoresearch", "sia"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _state_path() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "scheduler.json"


@dataclass
class ScheduledTask:
    kind: str
    interval_seconds: int
    id: str = field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:12]}")
    enabled: bool = True
    last_run: Optional[str] = None
    created_at: str = field(default_factory=lambda: _now().isoformat())
    args: dict = field(default_factory=dict)

    @property
    def owner_gated(self) -> bool:
        return self.kind in OWNER_GATED_KINDS

    def due(self, now: Optional[datetime] = None) -> bool:
        if not self.enabled:
            return False
        now = now or _now()
        if self.last_run is None:
            return True
        try:
            last = datetime.fromisoformat(self.last_run)
        except ValueError:
            return True
        return (now - last).total_seconds() >= self.interval_seconds

    def to_dict(self) -> dict:
        d = asdict(self)
        d["owner_gated"] = self.owner_gated
        return d


class Scheduler:
    """A small JSON-backed store of recurring tasks + due computation."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _state_path()

    def _read(self) -> list[ScheduledTask]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        out: list[ScheduledTask] = []
        for entry in raw.get("tasks", []):
            d = dict(entry)
            d.pop("owner_gated", None)  # derived, not stored
            try:
                out.append(ScheduledTask(**d))
            except TypeError:
                continue
        return out

    def _write(self, tasks: list[ScheduledTask]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tasks": [asdict(t) for t in tasks]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def tasks(self) -> list[ScheduledTask]:
        return self._read()

    def add(self, kind: str, interval_seconds: int, **args) -> ScheduledTask:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        tasks = self._read()
        task = ScheduledTask(kind=kind, interval_seconds=interval_seconds, args=dict(args))
        tasks.append(task)
        self._write(tasks)
        return task

    def remove(self, task_id: str) -> bool:
        tasks = self._read()
        kept = [t for t in tasks if t.id != task_id]
        if len(kept) == len(tasks):
            return False
        self._write(kept)
        return True

    def due(self, now: Optional[datetime] = None) -> list[ScheduledTask]:
        now = now or _now()
        return [t for t in self._read() if t.due(now)]

    def mark_run(self, task_id: str, now: Optional[datetime] = None) -> None:
        now = now or _now()
        tasks = self._read()
        for t in tasks:
            if t.id == task_id:
                t.last_run = now.isoformat()
        self._write(tasks)

    def run_due(
        self, *, runner: Callable[[ScheduledTask], str], now: Optional[datetime] = None
    ) -> list[dict]:
        now = now or _now()
        results: list[dict] = []
        for t in self.due(now):
            try:
                output = runner(t)
            except Exception as exc:  # pragma: no cover - defensive
                output = f"error: {exc}"
            self.mark_run(t.id, now)
            results.append({"id": t.id, "kind": t.kind, "output": output})
        return results


def _run_forge_tournament(task: ScheduledTask) -> str:
    import random

    from hermes_cli.jarvis_prime.forge.main import DEMO_TASK
    from hermes_cli.jarvis_prime.forge.map_elites import ElitesGrid
    from hermes_cli.jarvis_prime.forge.registry import CandidateRegistry
    from hermes_cli.jarvis_prime.forge.tournament import RatingBook, run_tournament
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

    report = run_tournament(
        DEMO_TASK,
        CandidateRegistry(),
        rounds=int(task.args.get("rounds", 1)),
        rating_book=RatingBook(),
        elites=ElitesGrid(ledger=GuardrailLedger()),
        ledger=GuardrailLedger(),
        rng=random.Random(int(task.args.get("seed", 0))),
    )
    return f"ran forge tournament: {len(report.duels)} duel(s)"


def default_runner(*, allow_owner_gated: bool = False) -> Callable[[ScheduledTask], str]:
    """Map a task to an action. Owner-gated lanes refuse unless authorized."""

    def run(task: ScheduledTask) -> str:
        if task.kind == "forge-tournament":
            return _run_forge_tournament(task)
        if task.owner_gated and not allow_owner_gated:
            return f"skipped (owner-gated {task.kind} — authorize to run)"
        return f"no runner for kind {task.kind!r}"

    return run
