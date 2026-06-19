"""Build a live Gemma runner from a detected local Ollama install.

This is the missing piece that makes the Gemma memory-curator lane actually
*run*: it detects Ollama + an installed Gemma model and returns a
``(prompt) -> completion`` runner, or ``None`` when Ollama or a Gemma model is
absent (so the curator stays a no-op — byte-identical to before).

Auto-wiring is **off by default** and opt-in via
``HERMES_JARVIS_GEMMA_AUTO_RUNNER`` — spawning local model inference should be
an explicit operator choice. An explicitly-set ``JarvisConfig.gemma_runner``
always wins; an injected ``gemma_runner_factory`` is used as-is (tests/embedders).

stdlib-only. The runner reuses ``self_audit.live.command_model_invoke`` to pipe
the prompt to ``ollama run <tag>`` on stdin.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable, Optional

Runner = Callable[[str], str]
ListRunner = Callable[[], str]
InvokeFactory = Callable[[str], Runner]

ENV_AUTO_RUNNER = "HERMES_JARVIS_GEMMA_AUTO_RUNNER"

# Preference for a lightweight curator lane: small/fast variants first. Matched
# as a case-insensitive substring against the installed Ollama tag.
_PREFERENCE = ("e4b", "e2b", "4b", "2b", "12b", "26b", "31b")


def auto_runner_enabled() -> bool:
    """True if the operator opted into auto-detecting a local Gemma runner."""

    raw = os.environ.get(ENV_AUTO_RUNNER)
    return bool(raw) and raw.strip().lower() in ("1", "true", "yes", "on")


def _default_list_runner() -> str:
    proc = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return proc.stdout if proc.returncode == 0 else ""


def _installed_gemma_tags(list_output: str) -> list[str]:
    tags: list[str] = []
    for line in list_output.splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        if name.lower() == "name":  # `ollama list` header row
            continue
        if "gemma" in name.lower():
            tags.append(name)
    return tags


def _rank(tag: str) -> int:
    low = tag.lower()
    for index, token in enumerate(_PREFERENCE):
        if token in low:
            return index
    return len(_PREFERENCE)


def detect_installed_gemma_tag(list_runner: Optional[ListRunner] = None) -> Optional[str]:
    """Return the best installed Gemma Ollama tag, or ``None`` if none found."""

    runner = list_runner or _default_list_runner
    try:
        output = runner()
    except Exception:
        return None
    tags = _installed_gemma_tags(output)
    if not tags:
        return None
    return sorted(tags, key=lambda tag: (_rank(tag), tag))[0]


def _default_invoke_factory(tag: str) -> Runner:
    from hermes_cli.jarvis_prime.self_audit.live import command_model_invoke

    return command_model_invoke(f"ollama run {tag}")


def build_gemma_runner(
    *,
    which: Optional[Callable[[str], Optional[str]]] = None,
    list_runner: Optional[ListRunner] = None,
    invoke_factory: Optional[InvokeFactory] = None,
) -> Optional[Runner]:
    """Return a ``(prompt) -> completion`` runner backed by local Ollama Gemma.

    Returns ``None`` when Ollama is not on PATH or no Gemma model is installed —
    so the curator stays inert rather than erroring.
    """

    which_fn = which or shutil.which
    if which_fn("ollama") is None:
        return None
    tag = detect_installed_gemma_tag(list_runner)
    if tag is None:
        return None
    runner = (invoke_factory or _default_invoke_factory)(tag)
    # muse_TEMPLATES fast path (off by default). With the flag off this is a
    # single env read and the SAME runner object is returned — byte-identical.
    # With the flag on, maybe_wrap_runner still returns the base runner
    # unchanged unless a healthy llama-server and template artifacts exist.
    if os.environ.get("muse_TEMPLATES", "").strip().lower() in ("1", "true", "yes", "on"):
        try:
            from hermes_cli.jarvis_prime.template_fastpath import maybe_wrap_runner

            return maybe_wrap_runner(runner)
        except Exception:
            return runner
    return runner


__all__ = [
    "ENV_AUTO_RUNNER",
    "auto_runner_enabled",
    "detect_installed_gemma_tag",
    "build_gemma_runner",
]
