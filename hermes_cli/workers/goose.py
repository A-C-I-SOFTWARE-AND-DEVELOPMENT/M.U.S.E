"""Block Goose worker adapter."""

from __future__ import annotations

import re
from typing import Any

from hermes_cli.workers.base import JobContext, WorkerAdapter


class GooseWorker(WorkerAdapter):
    name = "goose"
    binary = "goose"
    description = "Block Goose CLI (requires configured Goose provider)"

    def build_command(self, job: JobContext) -> list[str]:
        return [
            self.binary,
            "run",
            "--instructions",
            str(job.job_dir / "prompt.md"),
            "--quiet",
        ]

    def parse_log(self, log: str) -> dict[str, Any]:
        """Goose prints ``files modified: <N>`` at the end of a run."""
        m = re.search(r"files modified:\s*(\d+)", log)
        if m:
            return {"files_changed": int(m.group(1)), "message": "goose run"}
        return {}
