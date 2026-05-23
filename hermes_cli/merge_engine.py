"""Merge engine — combines selected worker proposals into one artifact.

If the arbiter returns a single winner, the merge engine forwards its
proposal verbatim. If multiple proposals are selected (draw), the merge
engine produces a deterministic union: each contributor's summary appears
under its own subsection so a human reviewer can compare them side by
side.
"""

from __future__ import annotations

import dataclasses
from typing import Sequence

from hermes_cli.arbiter import ArbiterDecision
from hermes_cli.workers.base import WorkerResult


@dataclasses.dataclass(frozen=True)
class MergeArtifact:
    title: str
    body: str
    contributors: list[str]
    is_draw: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "contributors": self.contributors,
            "is_draw": self.is_draw,
        }


def merge(decision: ArbiterDecision, *, task_title: str) -> MergeArtifact:
    if not decision.selected:
        return MergeArtifact(
            title=f"[no-merge] {task_title}",
            body=f"Arbiter abstained: {decision.rationale}\n",
            contributors=[],
            is_draw=False,
        )
    if len(decision.selected) == 1:
        winner = decision.selected[0]
        return MergeArtifact(
            title=f"[hermes] {task_title}",
            body=winner.proposal,
            contributors=[winner.worker_name],
            is_draw=False,
        )
    return _merge_draw(decision.selected, task_title=task_title, rationale=decision.rationale)


def _merge_draw(
    proposals: Sequence[WorkerResult],
    *,
    task_title: str,
    rationale: str,
) -> MergeArtifact:
    sections: list[str] = []
    for prop in sorted(proposals, key=lambda p: p.worker_name):
        header = f"### {prop.worker_name} ({prop.metadata.get('role', 'worker')})"
        sections.append("\n".join([header, "", prop.proposal.strip()]))
    body = (
        f"Arbiter flagged a draw: {rationale}.\n\n"
        "Each candidate is preserved below for human comparison.\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n"
    )
    return MergeArtifact(
        title=f"[hermes:draw] {task_title}",
        body=body,
        contributors=[p.worker_name for p in proposals],
        is_draw=True,
    )
