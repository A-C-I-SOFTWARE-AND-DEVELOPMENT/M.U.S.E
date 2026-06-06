"""Sandboxed code execution — the executable reward channel.

Runs a candidate's code in an isolated subprocess with a wall-clock timeout, a
scrubbed environment (no secrets), and an unroutable proxy (best-effort network
deny), then returns a structured result. This is the ground-truth signal the
research fabric trusts — compilers/tests/latency, not a model's self-estimate.

It is intentionally minimal and stdlib-only. It does NOT claim to be a hardened
security sandbox; for untrusted third-party code, run it inside a container with
real isolation. Within the fabric, candidate code is the agent's own output run
under ``WORKER_POLICY`` (network off, no secrets) — this enforces that policy at
the process boundary as far as a pure-Python launcher can.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Env var name fragments we never propagate into a candidate subprocess.
_SECRET_FRAGMENTS = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH",
    "API", "PRIVATE", "SESSION", "COOKIE", "OPENAI", "ANTHROPIC", "AWS",
    "GITHUB_TOKEN", "HF_", "HUGGINGFACE",
)


def _scrubbed_env() -> dict[str, str]:
    """A minimal env with secrets removed and network proxied to a dead address."""

    safe: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(frag in upper for frag in _SECRET_FRAGMENTS):
            continue
        safe[key] = value
    # Keep PATH so the interpreter resolves, but deny network via dead proxies.
    safe.setdefault("PATH", os.environ.get("PATH", ""))
    safe["http_proxy"] = "http://127.0.0.1:9"
    safe["https_proxy"] = "http://127.0.0.1:9"
    safe["HTTP_PROXY"] = "http://127.0.0.1:9"
    safe["HTTPS_PROXY"] = "http://127.0.0.1:9"
    safe["no_proxy"] = ""
    safe["PYTHONDONTWRITEBYTECODE"] = "1"
    return safe


@dataclass(frozen=True)
class ExecResult:
    ok: bool
    exit_code: Optional[int]
    timed_out: bool
    latency_s: float
    stdout: str
    stderr: str
    parsed: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "latency_s": round(self.latency_s, 6),
            "stdout_tail": self.stdout[-2000:],
            "stderr_tail": self.stderr[-2000:],
            "parsed": self.parsed,
        }


def run_python_script(
    script: str,
    *,
    args: Optional[list[str]] = None,
    timeout_s: float = 30.0,
    cwd: Optional[Path] = None,
) -> ExecResult:
    """Run ``script`` as an isolated ``python -I -S`` subprocess.

    ``-I`` isolates from the user's site/env (ignores PYTHON* and the cwd on
    sys.path beyond the script dir); ``-S`` skips site customization. The last
    line of stdout, if it is a JSON object, is surfaced as ``parsed``.
    """

    with tempfile.TemporaryDirectory(prefix="rf_sandbox_") as td:
        tdp = Path(td)
        script_path = tdp / "candidate_main.py"
        script_path.write_text(script, encoding="utf-8")
        cmd = [sys.executable, "-I", "-S", str(script_path), *(args or [])]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd or tdp),
                env=_scrubbed_env(),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(
                ok=False,
                exit_code=None,
                timed_out=True,
                latency_s=time.monotonic() - start,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            )
        latency = time.monotonic() - start

    parsed: Optional[dict[str, Any]] = None
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    parsed = obj
                    break
            except json.JSONDecodeError:
                continue
    return ExecResult(
        ok=proc.returncode == 0,
        exit_code=proc.returncode,
        timed_out=False,
        latency_s=latency,
        stdout=proc.stdout,
        stderr=proc.stderr,
        parsed=parsed,
    )


def run_command(
    argv: list[str],
    *,
    cwd: Optional[Path] = None,
    timeout_s: float = 60.0,
) -> ExecResult:
    """Run an arbitrary command with a scrubbed env + timeout (no shell).

    Used by the SWE-style verifier to run a repo's real test command. The last
    JSON object on stdout, if any, is surfaced as ``parsed`` (usually unused
    here — the exit code is the signal).
    """

    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=_scrubbed_env(),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecResult(
            ok=False,
            exit_code=None,
            timed_out=True,
            latency_s=time.monotonic() - start,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
        )
    return ExecResult(
        ok=proc.returncode == 0,
        exit_code=proc.returncode,
        timed_out=False,
        latency_s=time.monotonic() - start,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


__all__ = ["ExecResult", "run_python_script", "run_command"]
