"""GitHub PR-body builder for Hermes jobs (Sprint 5 core).

The publisher's PR body carries the job id but not the **validation summary**
or the **decision-verdict id** the plan's "PR body contract" requires. This
kernel renders the complete, redaction-safe body from a structured result so
the publisher can drop in a single call.

Pure string assembly: every free-text field is passed through
:func:`hermes_cli.secrets_policy.redact` so a worker log line or rollback note
can't leak a credential into a public PR. Wiring this into
``github_publisher.prepare_pr_body`` is a deliberate follow-up.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["PrBodyInputs", "render_pr_body"]

_NA = "n/a"


@dataclass(frozen=True)
class PrBodyInputs:
    """Everything the PR-body contract needs. Ids are required; rest optional."""

    job_id: str
    session_id: Optional[str] = None
    verdict_id: Optional[str] = None
    validation_summary: Optional[str] = None
    worker_selected: Optional[str] = None
    diffstat: Optional[str] = None
    acceptance_criteria: Sequence[str] = field(default_factory=tuple)
    tests_run: Sequence[str] = field(default_factory=tuple)
    rollback: Optional[str] = None


def render_pr_body(inputs: PrBodyInputs) -> str:
    """Render the PR body markdown from ``inputs`` (free text redacted)."""

    from hermes_cli.secrets_policy import redact

    if not inputs.job_id:
        raise ValueError("job_id is required")

    def r(value: Optional[str]) -> str:
        return redact(value) if value else _NA

    lines: list[str] = []
    lines.append("## muse Job")
    lines.append("")
    lines.append(f"- Job: `{inputs.job_id}`")
    lines.append(f"- Source session: `{inputs.session_id or _NA}`")
    lines.append(f"- Decision verdict: `{inputs.verdict_id or _NA}`")
    lines.append(f"- Validation: {r(inputs.validation_summary)}")
    lines.append(f"- Worker selected: `{inputs.worker_selected or _NA}`")
    lines.append(f"- Diffstat: {r(inputs.diffstat)}")
    lines.append("")

    lines.append("## Acceptance criteria")
    lines.append("")
    if inputs.acceptance_criteria:
        for item in inputs.acceptance_criteria:
            lines.append(f"- [ ] {redact(item)}")
    else:
        lines.append("- [ ] (none specified)")
    lines.append("")

    lines.append("## Tests run")
    lines.append("")
    lines.append("```text")
    if inputs.tests_run:
        for line in inputs.tests_run:
            lines.append(redact(line))
    else:
        lines.append("(none recorded)")
    lines.append("```")
    lines.append("")

    lines.append("## Rollback")
    lines.append("")
    lines.append(r(inputs.rollback))
    lines.append("")

    return "\n".join(lines)
