"""Claude Code CLI worker adapter."""

from __future__ import annotations

import re
from typing import Any

from hermes_cli.workers.base import JobContext, WorkerAdapter


class ClaudeCodeWorker(WorkerAdapter):
    name = "claude_code"
    binary = "claude"
    description = "Anthropic Claude Code CLI (requires Claude subscription)"

    def build_command(self, job: JobContext) -> list[str]:
        return [
            self.binary,
            "--print",
            "--cwd",
            str(job.repo_dir),
            "--file",
            str(job.job_dir / "prompt.md"),
        ]

    def parse_log(self, log: str) -> dict[str, Any]:
        """Claude Code emits ``Modified <N> files`` or ``No changes``."""
        m = re.search(r"Modified\s+(\d+)\s+files?", log)
        if m:
            return {"files_changed": int(m.group(1)), "message": "claude run"}
        if "No changes" in log:
            return {"files_changed": 0, "message": "no changes"}
        return {}
