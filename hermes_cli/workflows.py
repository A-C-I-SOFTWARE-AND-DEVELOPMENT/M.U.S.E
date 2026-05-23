"""Phase workflow definitions for the orchestration job controller.

This module is a thin, stable surface that the orchestrator job
controller (``hermes_cli.orchestrator``) imports to discover which
phases exist, what order they run in, and which transitions are legal.

Workflows are deliberately data-only.  All side effects (subprocess
spawning, model calls, network I/O) live in the controller — this
module is safe to import from anywhere, including offline tests.

TODO:
    * Allow users to define custom workflows in ``~/.hermes/config.yaml``
      under ``orchestration.workflows``.
    * Surface workflow choice in the ``/orchestrate`` slash command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


# ---------------------------------------------------------------------------
# Canonical phase names — the controller's public phase vocabulary.
# ---------------------------------------------------------------------------

PHASE_INTAKE = "intake"
PHASE_RESEARCH = "research"
PHASE_PLANNING = "planning"
PHASE_IMPLEMENTATION = "implementation"
PHASE_VALIDATION = "validation"
PHASE_PUBLISH = "publish"
PHASE_RETROSPECTIVE = "retrospective"


PHASES_ORDERED: tuple[str, ...] = (
    PHASE_INTAKE,
    PHASE_RESEARCH,
    PHASE_PLANNING,
    PHASE_IMPLEMENTATION,
    PHASE_VALIDATION,
    PHASE_PUBLISH,
    PHASE_RETROSPECTIVE,
)


# Phases that require user approval before the controller may proceed.
# These are conservative defaults — implementation mutates the working
# tree, publish mutates remote state.  See the controller's
# ``request_approval`` / ``run_<phase>_phase`` functions.
APPROVAL_GATED_PHASES: frozenset[str] = frozenset({
    PHASE_IMPLEMENTATION,
    PHASE_PUBLISH,
})


# Phases that the controller will refuse to auto-run when the job is
# operating in continuous-listening mode.  Continuous listening means
# the user is not at the keyboard ready to approve; auto-implementing
# would violate the safe-by-default rule.
NEVER_AUTO_IN_LISTENING_MODE: frozenset[str] = frozenset({
    PHASE_IMPLEMENTATION,
    PHASE_PUBLISH,
})


@dataclass(frozen=True)
class PhaseSpec:
    """Static metadata about one phase."""

    name: str
    description: str
    requires_approval: bool = False
    mutates_local: bool = False
    mutates_remote: bool = False


PHASE_SPECS: dict[str, PhaseSpec] = {
    PHASE_INTAKE: PhaseSpec(
        name=PHASE_INTAKE,
        description="Capture the prompt, repo context, mode, and trust level.",
    ),
    PHASE_RESEARCH: PhaseSpec(
        name=PHASE_RESEARCH,
        description="Gather background — read-only repo scans, doc lookups.",
    ),
    PHASE_PLANNING: PhaseSpec(
        name=PHASE_PLANNING,
        description="Decompose the task into a worker plan; no mutations yet.",
    ),
    PHASE_IMPLEMENTATION: PhaseSpec(
        name=PHASE_IMPLEMENTATION,
        description="Run workers; produce patches and artifacts.",
        requires_approval=True,
        mutates_local=True,
    ),
    PHASE_VALIDATION: PhaseSpec(
        name=PHASE_VALIDATION,
        description="Score outputs and run validation gates.",
    ),
    PHASE_PUBLISH: PhaseSpec(
        name=PHASE_PUBLISH,
        description="Prepare GitHub-ready artifacts (PR body, manifest, etc.).",
        requires_approval=True,
        mutates_remote=True,
    ),
    PHASE_RETROSPECTIVE: PhaseSpec(
        name=PHASE_RETROSPECTIVE,
        description="Record lessons learned to the decision ledger.",
    ),
}


@dataclass
class WorkflowDef:
    """A named sequence of phases.  Only the default is shipped today."""

    name: str
    phases: tuple[str, ...]
    description: str = ""


DEFAULT_WORKFLOW = WorkflowDef(
    name="default",
    phases=PHASES_ORDERED,
    description="Linear intake→retrospective workflow used by the controller.",
)


def get_workflow(name: str | None = None) -> WorkflowDef:
    """Return the workflow named *name*.  Falls back to the default.

    TODO: read user-defined workflows from config.yaml.
    """
    if name and name != DEFAULT_WORKFLOW.name:
        # No registry yet; refuse to silently fall back so callers notice.
        raise KeyError(f"Unknown workflow: {name!r}")
    return DEFAULT_WORKFLOW


def next_phase(current: str, workflow: WorkflowDef | None = None) -> str | None:
    """Return the phase that follows *current*, or ``None`` if last."""
    wf = workflow or DEFAULT_WORKFLOW
    try:
        idx = wf.phases.index(current)
    except ValueError:
        return wf.phases[0] if wf.phases else None
    if idx + 1 >= len(wf.phases):
        return None
    return wf.phases[idx + 1]


def is_known_phase(name: str) -> bool:
    return name in PHASE_SPECS


def phases_in_order(workflow: WorkflowDef | None = None) -> Iterable[PhaseSpec]:
    wf = workflow or DEFAULT_WORKFLOW
    for ph in wf.phases:
        yield PHASE_SPECS[ph]


__all__ = [
    "PHASE_INTAKE",
    "PHASE_RESEARCH",
    "PHASE_PLANNING",
    "PHASE_IMPLEMENTATION",
    "PHASE_VALIDATION",
    "PHASE_PUBLISH",
    "PHASE_RETROSPECTIVE",
    "PHASES_ORDERED",
    "APPROVAL_GATED_PHASES",
    "NEVER_AUTO_IN_LISTENING_MODE",
    "PhaseSpec",
    "PHASE_SPECS",
    "WorkflowDef",
    "DEFAULT_WORKFLOW",
    "get_workflow",
    "next_phase",
    "is_known_phase",
    "phases_in_order",
]
