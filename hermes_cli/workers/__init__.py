"""Worker adapters for handing Hermes tasks to local CLI agents.

A *worker* is a thin Python adapter around a third-party local agent
CLI (Aider, Goose, …). Hermes itself never replaces these tools —
each worker prepares a sandboxed workspace with:

    workspace/
        prompt.md          # worker-tuned instructions
        status.json        # machine-readable status the dashboard reads
        output.md          # captured stdout (only when executed)
        patch.diff         # ``git diff`` after the run (only when executed)
        changed-files.txt  # newline-separated paths (only when executed)

The default mode is **handoff-required**: the worker writes ``prompt.md``
and ``status.json`` and stops. The user (or another orchestrator) runs
the CLI manually with the prompt. The ``execute=True`` mode is opt-in
and only runs commands the upstream tool publishes as safe — no
destructive shortcuts (``--yes-always``, ``--auto-commit``, ``rm``,
``reset --hard``, …) are ever invoked automatically.

The adapters never automate paid subscription UIs. They only invoke the
local CLI binaries the user installed on their own machine.
"""

from hermes_cli.workers.base import (
    WorkerError,
    WorkerResult,
    WorkerStatus,
    WorkerTask,
)

__all__ = [
    "WorkerError",
    "WorkerResult",
    "WorkerStatus",
    "WorkerTask",
]
