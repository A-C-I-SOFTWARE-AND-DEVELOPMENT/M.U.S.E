"""Goose handoff worker — turn a job into a ready-to-run Goose invocation.

Non-executing (``goose.run(..., execute=False)``): writes a worker-tuned
``prompt.md`` scoped to the navigator's candidate files and returns a
copy-pasteable ``goose`` command. Never spawns Goose or edits the repo, runs
ungated, and is verifiable without the ``goose`` binary present.
"""

from __future__ import annotations

from hermes_cli.workers import goose
from hermes_cli.workers.handoff_base import ProceduralHandoffWorker
from hermes_cli.workers.registry import register


class GooseHandoffWorker(ProceduralHandoffWorker):
    id = "goose-handoff"
    display_name = "Goose (handoff)"
    tool_label = "Goose"
    worker_module = goose
    config_cls = goose.GooseConfig


register(GooseHandoffWorker(), replace=True)
