"""Aider worker adapter."""

from __future__ import annotations

import re
from typing import Any

from hermes_cli.workers.base import JobContext, WorkerAdapter


class AiderWorker(WorkerAdapter):
    name = "aider"
    binary = "aider"
    description = "Aider AI coding assistant (uses configured provider key)"

    def build_command(self, job: JobContext) -> list[str]:
        return [
            self.binary,
            "--yes",
            "--no-stream",
            "--message-file",
            str(job.job_dir / "prompt.md"),
        ]

    def parse_log(self, log: str) -> dict[str, Any]:
        """Aider prints ``Applied edit to <file>`` per file touched."""
        files = re.findall(r"Applied edit to (\S+)", log)
        if files:
            return {"files_changed": len(set(files)), "message": "aider run"}
        return {}
