"""Worker adapters for the Hermes Job Controller (Phase 7 skeleton).

This package is the registry of every worker adapter Hermes can hand a
job off to. The package init is intentionally tiny: it does **not**
import the individual adapter modules at load time, so that adding a
new adapter that depends on an optional CLI never breaks ``import
hermes_cli``.

See:
    - ``docs/orchestration/job-controller-roadmap.md``
    - ``docs/orchestration/worker-adapter-interface.md``
    - ``docs/orchestration/orchestrator-command-roadmap.md``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_cli.workers.base import WorkerAdapter

# Adapter names known to Phase 7. The mapping is name -> dotted module
# path; the controller imports the module lazily via ``importlib`` only
# when the adapter is actually selected by the model router. Listing a
# name here is **not** the same as wiring it into the CLI — the slash
# commands described in ``orchestrator-command-roadmap.md`` are not
# registered yet.
BUILTIN_ADAPTERS: dict[str, str] = {
    "hermes_local": "hermes_cli.workers.hermes_local",
    "codex": "hermes_cli.workers.codex",
    "claude_code": "hermes_cli.workers.claude_code",
    "aider": "hermes_cli.workers.aider",
    "goose": "hermes_cli.workers.goose",
    "chatgpt_handoff": "hermes_cli.workers.chatgpt_handoff",
}


def load_adapter(name: str) -> "WorkerAdapter":
    """Lazily import and instantiate the adapter registered under ``name``.

    Raises :class:`KeyError` if the name is not in ``BUILTIN_ADAPTERS``.
    Raises :class:`ImportError` if the optional dependency required by
    the adapter is not installed — callers should catch that and treat
    the adapter as unavailable.

    TODO(phase-7): wire this into ``hermes_cli/orchestrator.py`` once
    the controller lands. For now it is reachable only from tests.
    """
    import importlib

    module_path = BUILTIN_ADAPTERS[name]
    module = importlib.import_module(module_path)
    factory = getattr(module, "adapter", None)
    if factory is None:
        raise ImportError(
            f"worker module {module_path!r} does not expose an `adapter` factory",
        )
    return factory()


__all__ = ["BUILTIN_ADAPTERS", "load_adapter"]
