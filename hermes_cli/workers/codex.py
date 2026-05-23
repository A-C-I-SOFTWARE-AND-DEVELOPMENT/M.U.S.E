"""OpenAI Codex CLI worker adapter."""

from __future__ import annotations

import re
from typing import Any

from hermes_cli.workers.base import JobContext, WorkerAdapter


class CodexWorker(WorkerAdapter):
    name = "codex"
    binary = "codex"
    description = "OpenAI Codex CLI (requires Codex subscription / login)"

    def build_command(self, job: JobContext) -> list[str]:
        return [
            self.binary,
            "exec",
            "--cd",
            str(job.repo_dir),
            "--file",
            str(job.job_dir / "prompt.md"),
        ]

    def parse_log(self, log: str) -> dict[str, Any]:
        """Codex prints a final ``codex: applied <N> patches`` line."""
        m = re.search(r"codex:\s+applied\s+(\d+)\s+patch(?:es)?", log)
        if m:
            return {"files_changed": int(m.group(1)), "message": "codex run"}
        return {}
