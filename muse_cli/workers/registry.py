"""In-process registry of worker adapters.

The orchestrator looks up workers by id (``"codex"``, ``"claude-code"``,
``"aider"``, ``"hermes-local"``, ...). Adapters register themselves at
import time — usually via ``register(MyAdapter())`` at the bottom of
their module — so the orchestrator never has to import each adapter
directly.

We use a module-level ``default_registry`` for the common case and
expose the underlying :class:`WorkerRegistry` class so tests and
embedders can build isolated registries when they want to avoid the
global one. ``register`` / ``get`` / ``known_workers`` are thin module
wrappers around the default registry.
"""

from __future__ import annotations

from threading import Lock
from typing import Iterator

from muse_cli.workers.base import WorkerAdapter


class WorkerRegistry:
    """Maps worker ids to adapter instances.

    The registry is intentionally simple: a dict behind a lock. Adapters
    are stored as already-constructed instances so consumers don't have
    to know whether the adapter takes constructor arguments — that's
    the registering module's problem.

    Re-registering an existing id raises ``ValueError`` by default to
    catch accidental clobbering during plugin loading. Pass
    ``replace=True`` to register over the top — useful in tests and
    when a plugin intentionally overrides a built-in worker.
    """

    def __init__(self) -> None:
        self._workers: dict[str, WorkerAdapter] = {}
        self._lock = Lock()

    def register(self, adapter: WorkerAdapter, *, replace: bool = False) -> None:
        """Add ``adapter`` to the registry under ``adapter.id``."""
        if not isinstance(adapter, WorkerAdapter):
            raise TypeError(
                f"register() expected a WorkerAdapter, got {type(adapter).__name__}"
            )
        worker_id = adapter.id
        if not worker_id:
            raise ValueError(f"{type(adapter).__name__} has no `id` — cannot register")
        with self._lock:
            if not replace and worker_id in self._workers:
                existing = type(self._workers[worker_id]).__name__
                incoming = type(adapter).__name__
                raise ValueError(
                    f"Worker id {worker_id!r} already registered by "
                    f"{existing}; pass replace=True to override with "
                    f"{incoming}."
                )
            self._workers[worker_id] = adapter

    def unregister(self, worker_id: str) -> WorkerAdapter:
        """Remove and return the adapter registered under ``worker_id``."""
        with self._lock:
            try:
                return self._workers.pop(worker_id)
            except KeyError as exc:
                raise KeyError(
                    f"No worker registered for id {worker_id!r}. "
                    f"Known: {sorted(self._workers)}"
                ) from exc

    def get(self, worker_id: str) -> WorkerAdapter:
        """Return the adapter registered under ``worker_id``."""
        with self._lock:
            try:
                return self._workers[worker_id]
            except KeyError as exc:
                raise KeyError(
                    f"No worker registered for id {worker_id!r}. "
                    f"Known: {sorted(self._workers)}"
                ) from exc

    def known_workers(self) -> list[str]:
        """Return the ids of all registered workers, sorted."""
        with self._lock:
            return sorted(self._workers)

    def __contains__(self, worker_id: object) -> bool:
        if not isinstance(worker_id, str):
            return False
        with self._lock:
            return worker_id in self._workers

    def __iter__(self) -> Iterator[WorkerAdapter]:
        with self._lock:
            snapshot = list(self._workers.values())
        return iter(snapshot)

    def __len__(self) -> int:
        with self._lock:
            return len(self._workers)

    def clear(self) -> None:
        """Drop every registered worker. Test helper — avoid in prod."""
        with self._lock:
            self._workers.clear()


# ── Module-level convenience wrappers ───────────────────────────────────

default_registry = WorkerRegistry()


def register(adapter: WorkerAdapter, *, replace: bool = False) -> None:
    """Register ``adapter`` on the default registry."""
    default_registry.register(adapter, replace=replace)


def unregister(worker_id: str) -> WorkerAdapter:
    """Remove ``worker_id`` from the default registry."""
    return default_registry.unregister(worker_id)


def get(worker_id: str) -> WorkerAdapter:
    """Return the adapter registered under ``worker_id`` on the default registry."""
    return default_registry.get(worker_id)


def known_workers() -> list[str]:
    """Return ids registered on the default registry, sorted."""
    return default_registry.known_workers()


__all__ = [
    "WorkerRegistry",
    "default_registry",
    "get",
    "known_workers",
    "register",
    "unregister",
]
