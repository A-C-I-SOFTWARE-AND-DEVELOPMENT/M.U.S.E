"""Resolve a *live* ``model_invoke`` for the optional self-audit LLM lanes.

JARVIS is local-first and model-agnostic, so the live lane is wired through a
generic, opt-in escape hatch rather than one hard-coded provider:

1. an in-process override registered via :func:`set_model_invoke` (e.g. the
   runtime hands in its already-configured model), or
2. the ``HERMES_SELF_AUDIT_MODEL_CMD`` environment variable — any local model
   CLI (e.g. ``ollama run llama3``) that reads a prompt on **stdin** and writes
   the completion to **stdout**.

:func:`resolve_model_invoke` returns ``None`` when neither is configured, so
callers degrade gracefully instead of pretending a model exists. The prompt is
passed on stdin (never interpolated into the command), so prompt content cannot
inject shell arguments.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import Callable, Optional

ModelInvoke = Callable[[str], str]

ENV_MODEL_CMD = "HERMES_SELF_AUDIT_MODEL_CMD"

_OVERRIDE: Optional[ModelInvoke] = None


def set_model_invoke(fn: Optional[ModelInvoke]) -> None:
    """Register (``fn``) or clear (``None``) an in-process model_invoke override."""

    global _OVERRIDE
    _OVERRIDE = fn


def command_model_invoke(command: str, *, timeout: int = 120) -> ModelInvoke:
    """Build a model_invoke that pipes the prompt through a local model CLI."""

    argv = shlex.split(command)

    def invoke(prompt: str) -> str:
        proc = subprocess.run(
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                proc.stderr.strip() or f"model command exited {proc.returncode}"
            )
        return proc.stdout

    return invoke


def resolve_model_invoke() -> Optional[ModelInvoke]:
    """Return a live model_invoke, or ``None`` if none is configured."""

    if _OVERRIDE is not None:
        return _OVERRIDE
    command = os.environ.get(ENV_MODEL_CMD, "").strip()
    if command:
        return command_model_invoke(command)
    return None


__all__ = [
    "ModelInvoke",
    "ENV_MODEL_CMD",
    "set_model_invoke",
    "command_model_invoke",
    "resolve_model_invoke",
]
