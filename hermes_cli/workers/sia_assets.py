"""Vendored, attributed assets for the SIA self-improvement worker.

The **task-directory format** and the three-role (meta / target /
feedback) generation design are adapted from Hexo Labs' open-source
SIA project (https://github.com/hexo-ai/sia), which is MIT-licensed.
See ``THIRD_PARTY_NOTICES.md`` at the repo root for the full
attribution. The prompt/template *text* below is Hermes-original,
written to match SIA's documented task layout so the upstream ``sia``
CLI can consume a directory Hermes generates.

SIA expects a task directory shaped like::

    <task>/
    ├── data/
    │   └── public/
    │       └── task.md          # the task description the agent reads
    └── reference/
        ├── reference_target_agent.py
        └── SAMPLE_TASK_DESCRIPTIONS.md

``materialize_task_dir`` writes exactly that shape from a Hermes
objective + the current (baseline) contents of the target we want SIA
to improve.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

# ── Templates (Hermes-original; layout adapted from hexo-ai/sia, MIT) ──

TASK_MD_TEMPLATE = """\
# Self-improvement task: {{TARGET_NAME}}

You are an autonomous agent whose job is to produce the best possible
version of the artifact named **{{TARGET_NAME}}** for the objective
below. Each generation you will be rewritten by a feedback agent that
reads your execution log; aim to make the next generation strictly
better than the last on the acceptance criteria.

## Objective

{{OBJECTIVE}}

## Acceptance criteria

{{ACCEPTANCE}}

## Baseline

A baseline version of the target is provided under
``data/public/baseline/`` (when available). Treat it as the current
best. Your improved scaffold must not regress any criterion above.

## Output contract

- Produce your improved target as ``target_agent.py`` in the generation
  output directory (the SIA harness handles this).
- Record what you changed and why so the feedback agent can build on it.
- Do not attempt to access the network or write outside the run
  directory.
"""

REFERENCE_AGENT_TEMPLATE = '''\
"""Reference target-agent interface for a Hermes/SIA self-improvement run.

This is the shape the SIA feedback agent rewrites each generation. It is
intentionally minimal: a single ``solve`` entry point that takes the task
description and returns the agent's answer/artifact. Hermes scores the
result; the feedback agent edits this file for the next generation.

(Hermes-original template; interface adapted from hexo-ai/sia, MIT.)
"""

from __future__ import annotations


def solve(task_description: str) -> str:
    """Attempt the task and return the result.

    The feedback agent will rewrite the body (and may add helpers) to
    improve the score on the acceptance criteria across generations.
    """
    raise NotImplementedError("the meta-agent generates the first version")
'''

SAMPLE_TASK_DESCRIPTIONS = """\
# Sample task descriptions

These illustrate the kind of objective Hermes hands to SIA. They are
examples only — the live task is in ``data/public/task.md``.

- "Improve the code-navigation skill so it localizes the correct edit
  site on a held-out set of repository bug reports."
- "Rewrite the planner prompt so plans pass the local validation gate
  on first try more often."
- "Make the summarizer produce answers that match the reference rubric
  more closely."
"""


def _fill(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def render_task_md(
    objective: str,
    *,
    target_name: str = "target",
    acceptance: Sequence[str] = (),
) -> str:
    """Render ``task.md`` from a Hermes objective."""
    acc = "\n".join(f"- {item}" for item in acceptance) or "- (none specified)"
    return _fill(
        TASK_MD_TEMPLATE,
        {
            "TARGET_NAME": target_name or "target",
            "OBJECTIVE": (objective or "(no objective provided)").strip(),
            "ACCEPTANCE": acc,
        },
    )


def materialize_task_dir(
    dest: Path,
    *,
    objective: str,
    target_name: str = "target",
    baseline_code: str = "",
    acceptance: Sequence[str] = (),
) -> Path:
    """Write a SIA-compatible task directory under ``dest``.

    Creates ``data/public/task.md``, an optional
    ``data/public/baseline/<target_name>`` snapshot, and the
    ``reference/`` files. Returns ``dest``.
    """
    dest = Path(dest)
    public = dest / "data" / "public"
    reference = dest / "reference"
    public.mkdir(parents=True, exist_ok=True)
    reference.mkdir(parents=True, exist_ok=True)

    (public / "task.md").write_text(
        render_task_md(objective, target_name=target_name, acceptance=acceptance),
        encoding="utf-8",
    )
    if baseline_code:
        baseline_dir = public / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(target_name or "target").name or "target"
        (baseline_dir / safe_name).write_text(baseline_code, encoding="utf-8")

    (reference / "reference_target_agent.py").write_text(
        REFERENCE_AGENT_TEMPLATE, encoding="utf-8"
    )
    (reference / "SAMPLE_TASK_DESCRIPTIONS.md").write_text(
        SAMPLE_TASK_DESCRIPTIONS, encoding="utf-8"
    )
    return dest


__all__ = [
    "TASK_MD_TEMPLATE",
    "REFERENCE_AGENT_TEMPLATE",
    "SAMPLE_TASK_DESCRIPTIONS",
    "render_task_md",
    "materialize_task_dir",
]
