"""HTN-lite task trees with mandatory verifier nodes (Phase 5.1).

A goal decomposes into a tree: composite tasks decompose, leaf tasks
do work. Every decomposition node MUST carry a verifier task — a
decomposition that cannot say how it will be checked is rejected at
construction (no spec, no parse, applied to plans). Leaves execute
through the JobStore, so re-running a plan never re-runs committed
work (exactly-once).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .jobs import JobStore


@dataclass
class Task:
    name: str
    kind: str  # "composite" | "leaf"
    inputs: dict = field(default_factory=dict)
    job: Callable[[dict], Any] | None = None
    children: list["Task"] = field(default_factory=list)
    verifier: Callable[[list], bool] | None = None

    @staticmethod
    def leaf(name: str, inputs: dict, job: Callable[[dict], Any]) -> "Task":
        return Task(name=name, kind="leaf", inputs=inputs, job=job)

    @staticmethod
    def composite(
        name: str,
        children: list["Task"],
        verifier: Callable[[list], bool] | None,
    ) -> "Task":
        if verifier is None:
            raise ValueError(
                f"decomposition {name!r} has no verifier task — "
                "a plan that cannot be checked is not a plan"
            )
        if not children:
            raise ValueError(f"decomposition {name!r} has no children")
        return Task(name=name, kind="composite", children=children,
                    verifier=verifier)


class Plan:
    """Executes a task tree depth-first with exactly-once leaves."""

    def __init__(self, store: JobStore):
        self.store = store

    def execute(self, task: Task) -> Any:
        if task.kind == "leaf":
            _key, result, _ran = self.store.run(task.name, task.inputs, task.job)
            return result
        results = [self.execute(child) for child in task.children]
        if not task.verifier(results):
            raise RuntimeError(
                f"decomposition {task.name!r}: verifier rejected results"
            )
        return results
