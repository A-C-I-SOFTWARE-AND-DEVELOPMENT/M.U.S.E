"""Aider handoff worker — turn a job into a ready-to-run Aider invocation.

Non-executing (``aider.run(..., execute=False)``): writes a worker-tuned
``prompt.md`` scoped to the navigator's candidate files and returns a
copy-pasteable ``aider`` command. It never spawns Aider or edits the repo, so
it runs ungated and is verifiable without the ``aider`` binary present.
Executing Aider (``execute=True``) is a separate, owner-gated capability.
"""

from __future__ import annotations

from hermes_cli.workers import aider
from hermes_cli.workers.handoff_base import ProceduralExecuteWorker, ProceduralHandoffWorker
from hermes_cli.workers.registry import register


class AiderHandoffWorker(ProceduralHandoffWorker):
    id = "aider-handoff"
    display_name = "Aider (handoff)"
    tool_label = "Aider"
    worker_module = aider
    config_cls = aider.AiderConfig


class AiderExecuteWorker(ProceduralExecuteWorker):
    """Live: actually runs Aider (owner-gated; requires the `aider` binary)."""

    id = "aider-execute"
    display_name = "Aider (execute)"
    tool_label = "Aider"
    worker_module = aider
    config_cls = aider.AiderConfig


register(AiderHandoffWorker(), replace=True)
register(AiderExecuteWorker(), replace=True)
