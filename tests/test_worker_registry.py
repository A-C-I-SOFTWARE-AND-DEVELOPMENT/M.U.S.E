"""Tests for :mod:`muse_cli.workers.registry`.

Exercises both the :class:`WorkerRegistry` class (used directly in
tests and embedders) and the module-level convenience wrappers that
delegate to ``default_registry``.
"""

from __future__ import annotations

from typing import Any

import pytest

from muse_cli.workers import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRegistry,
    WorkerRunResult,
    WorkerScore,
    default_registry,
)
from muse_cli.workers import registry as worker_registry


# ── Fixtures ────────────────────────────────────────────────────────────


class _FakeAdapter(WorkerAdapter):
    id = "fake"
    display_name = "Fake Worker"

    def detect(self) -> WorkerDetection:
        return WorkerDetection(available=True)

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text="")

    def run(self, job: Any) -> WorkerRunResult:
        return WorkerRunResult(ok=True)

    def collect(self, job: Any) -> WorkerArtifacts:
        return WorkerArtifacts()

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        return WorkerScore(value=1.0)


@pytest.fixture
def fresh_registry() -> WorkerRegistry:
    return WorkerRegistry()


@pytest.fixture
def isolated_default_registry():
    """Snapshot + restore the module-level registry so tests can't leak."""
    snapshot = {
        wid: default_registry.get(wid) for wid in default_registry.known_workers()
    }
    default_registry.clear()
    yield default_registry
    default_registry.clear()
    for adapter in snapshot.values():
        default_registry.register(adapter)


# ── Construction ────────────────────────────────────────────────────────


def test_registry_starts_empty(fresh_registry):
    assert fresh_registry.known_workers() == []
    assert len(fresh_registry) == 0
    assert "fake" not in fresh_registry


def test_default_registry_is_a_registry_instance():
    assert isinstance(default_registry, WorkerRegistry)


# ── register / get / unregister ─────────────────────────────────────────


def test_register_then_get(fresh_registry):
    adapter = _FakeAdapter()
    fresh_registry.register(adapter)
    assert fresh_registry.get("fake") is adapter
    assert fresh_registry.known_workers() == ["fake"]
    assert "fake" in fresh_registry
    assert len(fresh_registry) == 1


def test_get_unknown_raises(fresh_registry):
    with pytest.raises(KeyError, match="missing"):
        fresh_registry.get("missing")


def test_unknown_get_error_mentions_known_workers(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    with pytest.raises(KeyError, match="Known: \\['fake'\\]"):
        fresh_registry.get("missing")


def test_rejects_duplicate_id(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    with pytest.raises(ValueError, match="already registered"):
        fresh_registry.register(_FakeAdapter())


def test_replace_overrides_existing(fresh_registry):
    first = _FakeAdapter()
    second = _FakeAdapter()
    fresh_registry.register(first)
    fresh_registry.register(second, replace=True)
    assert fresh_registry.get("fake") is second


def test_unregister_returns_adapter(fresh_registry):
    adapter = _FakeAdapter()
    fresh_registry.register(adapter)
    removed = fresh_registry.unregister("fake")
    assert removed is adapter
    assert "fake" not in fresh_registry


def test_unregister_unknown_raises(fresh_registry):
    with pytest.raises(KeyError, match="missing"):
        fresh_registry.unregister("missing")


def test_rejects_non_adapter(fresh_registry):
    with pytest.raises(TypeError, match="WorkerAdapter"):
        fresh_registry.register("not an adapter")  # type: ignore[arg-type]


# ── Dunder behaviour ────────────────────────────────────────────────────


def test_iter_yields_registered_adapters(fresh_registry):
    a1 = _FakeAdapter()
    fresh_registry.register(a1)
    assert list(fresh_registry) == [a1]


def test_contains_only_strings(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    assert 123 not in fresh_registry  # type: ignore[operator]


def test_len_tracks_register_unregister(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    assert len(fresh_registry) == 1
    fresh_registry.unregister("fake")
    assert len(fresh_registry) == 0


def test_iter_snapshot_is_safe_against_mutation(fresh_registry):
    fresh_registry.register(_FakeAdapter())

    class _Other(_FakeAdapter):
        id = "other"
        display_name = "Other"

    it = iter(fresh_registry)
    # Mutating the registry mid-iteration must not corrupt the iterator
    # (we snapshot at __iter__ time precisely to avoid this).
    fresh_registry.register(_Other())
    collected = list(it)
    assert len(collected) == 1


# ── Ordering ────────────────────────────────────────────────────────────


def test_known_workers_returns_sorted_ids(fresh_registry):
    class _Z(_FakeAdapter):
        id = "z-worker"
        display_name = "Z"

    class _A(_FakeAdapter):
        id = "a-worker"
        display_name = "A"

    fresh_registry.register(_Z())
    fresh_registry.register(_A())
    assert fresh_registry.known_workers() == ["a-worker", "z-worker"]


# ── clear ───────────────────────────────────────────────────────────────


def test_clear_drops_everything(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    fresh_registry.clear()
    assert fresh_registry.known_workers() == []
    assert len(fresh_registry) == 0


# ── Module-level wrappers ──────────────────────────────────────────────


def test_module_level_helpers_delegate_to_default(isolated_default_registry):
    adapter = _FakeAdapter()
    worker_registry.register(adapter)
    try:
        assert worker_registry.get("fake") is adapter
        assert "fake" in worker_registry.known_workers()
    finally:
        worker_registry.unregister("fake")
    assert worker_registry.known_workers() == []


def test_module_level_register_rejects_duplicates(isolated_default_registry):
    worker_registry.register(_FakeAdapter())
    with pytest.raises(ValueError, match="already registered"):
        worker_registry.register(_FakeAdapter())


# ── Public API surface ──────────────────────────────────────────────────


def test_public_api_exports():
    expected = {
        "WorkerRegistry",
        "default_registry",
        "get",
        "known_workers",
        "register",
        "unregister",
    }
    import muse_cli.workers as workers_pkg

    assert expected.issubset(set(workers_pkg.__all__))
    for name in expected:
        assert hasattr(workers_pkg, name), name
