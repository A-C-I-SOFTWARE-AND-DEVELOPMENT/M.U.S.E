"""The bundled local Hermes worker — uses the CLI itself, no external tool."""

from __future__ import annotations

from typing import Any

from hermes_cli.workers.base import JobContext, WorkerAdapter


class HermesLocalWorker(WorkerAdapter):
    """A worker backed by the locally-installed ``hermes`` CLI.

    This worker is always considered ``detect()`` true because it is the
    bundled fallback — if no subscription-based tool is available we can
    still attempt the job locally with the user's configured Hermes setup.
    """

    name = "hermes_local"
    binary = "hermes"
    description = "Local Hermes CLI agent (bundled, no external subscription)"
    bundled = True

    def build_command(self, job: JobContext) -> list[str]:
        return [
            self.binary,
            "oneshot",
            "--prompt-file",
            str(job.job_dir / "prompt.md"),
            "--workdir",
            str(job.repo_dir),
            "--non-interactive",
        ]

    def parse_log(self, log: str) -> dict[str, Any]:
        """Look for the ``HERMES_DONE:`` sentinel line emitted by oneshot."""
        for line in log.splitlines():
            if line.startswith("HERMES_DONE:"):
                return {"message": line.split(":", 1)[1].strip()}
        return {}
