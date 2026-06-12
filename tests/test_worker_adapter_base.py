"""Contract tests for :mod:`muse_cli.workers`.

Exercises the dataclass records and the abstract base / registry. A
concrete ``_FakeAdapter`` stands in for the real workers (Codex, Claude
Code, Aider, Goose, Hermes Local, GitHub Publisher, ChatGPT handoff)
so we can verify the contract without depending on any of them being
installed in CI.
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
from muse_cli.workers import base as worker_base
from muse_cli.workers import registry as worker_registry


# ── Fixtures ────────────────────────────────────────────────────────────


class _FakeAdapter(WorkerAdapter):
    """Minimal concrete adapter used to verify the contract."""

    id = "fake"
    display_name = "Fake Worker"

    def __init__(self, *, available: bool = True) -> None:
        self._available = available

    def detect(self) -> WorkerDetection:
        return WorkerDetection(
            available=self._available,
            version="0.0.0",
            reason="ok" if self._available else "missing",
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(
            text=f"do: {getattr(job, 'goal', job)}",
            role="builder",
            metadata={"job_id": getattr(job, "id", None)},
        )

    def run(self, job: Any) -> WorkerRunResult:
        return WorkerRunResult(ok=True, stdout="done", duration_seconds=0.01)

    def collect(self, job: Any) -> WorkerArtifacts:
        return WorkerArtifacts(files=("README.md",), notes="touched README")

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        return WorkerScore(
            value=1.0 if artifacts.files else 0.0,
            confidence=0.8,
            rationale="files were produced",
            components={"compiles": 1.0, "tests": 0.5},
        )


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


# ── Result records ──────────────────────────────────────────────────────


def test_worker_detection_defaults():
    d = WorkerDetection(available=True)
    assert d.available is True
    assert d.version == ""
    assert d.reason == ""
    assert d.details == {}


def test_worker_detection_carries_full_payload():
    d = WorkerDetection(
        available=False,
        version="",
        reason="codex not on PATH",
        details={"checked": ["/usr/local/bin"]},
    )
    assert d.available is False
    assert d.reason == "codex not on PATH"
    assert d.details["checked"] == ["/usr/local/bin"]


def test_worker_prompt_defaults():
    p = WorkerPrompt(text="hello")
    assert p.text == "hello"
    assert p.role == ""
    assert p.metadata == {}


def test_worker_run_result_defaults_to_success_shape():
    r = WorkerRunResult(ok=True)
    assert r.ok is True
    assert r.exit_code == 0
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.duration_seconds == 0.0
    assert r.error == ""


def test_worker_artifacts_defaults_use_immutable_tuples():
    a = WorkerArtifacts()
    assert a.files == ()
    assert a.patches == ()
    assert a.logs == ()
    assert a.links == ()
    assert a.workspace_path == ""
    assert a.notes == ""


def test_dataclass_records_are_frozen():
    d = WorkerDetection(available=True)
    # Use setattr so the static type checker doesn't pre-empt the
    # FrozenInstanceError we're trying to assert on at runtime.
    with pytest.raises(Exception):
        setattr(d, "available", False)


def test_worker_score_accepts_valid_range():
    s = WorkerScore(value=0.5, confidence=0.9, rationale="ok")
    assert s.value == 0.5
    assert s.confidence == 0.9


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -5.0])
def test_worker_score_rejects_out_of_range_value(bad):
    with pytest.raises(ValueError):
        WorkerScore(value=bad)


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_worker_score_rejects_out_of_range_confidence(bad):
    with pytest.raises(ValueError):
        WorkerScore(value=0.5, confidence=bad)


def test_worker_score_rejects_out_of_range_component():
    with pytest.raises(ValueError):
        WorkerScore(value=0.5, components={"tests": 1.5})


# ── WorkerAdapter contract ──────────────────────────────────────────────


def test_worker_adapter_is_abstract():
    with pytest.raises(TypeError):
        WorkerAdapter()  # type: ignore[abstract]


def test_subclass_missing_id_fails_at_definition():
    with pytest.raises(TypeError, match="`id`"):

        class _NoId(WorkerAdapter):
            display_name = "x"

            def detect(self) -> WorkerDetection:
                return WorkerDetection(available=True)

            def prepare_prompt(self, job):
                return WorkerPrompt(text="")

            def run(self, job):
                return WorkerRunResult(ok=True)

            def collect(self, job):
                return WorkerArtifacts()

            def score(self, artifacts):
                return WorkerScore(value=0.0)


def test_subclass_missing_display_name_fails_at_definition():
    with pytest.raises(TypeError, match="`display_name`"):

        class _NoName(WorkerAdapter):
            id = "x"

            def detect(self) -> WorkerDetection:
                return WorkerDetection(available=True)

            def prepare_prompt(self, job):
                return WorkerPrompt(text="")

            def run(self, job):
                return WorkerRunResult(ok=True)

            def collect(self, job):
                return WorkerArtifacts()

            def score(self, artifacts):
                return WorkerScore(value=0.0)


def test_subclass_missing_abstract_method_cannot_instantiate():
    class _Partial(WorkerAdapter):
        id = "partial"
        display_name = "Partial"

        def detect(self) -> WorkerDetection:
            return WorkerDetection(available=True)

        # missing prepare_prompt / run / collect / score

    with pytest.raises(TypeError):
        _Partial()  # type: ignore[abstract]


def test_fake_adapter_round_trip():
    adapter = _FakeAdapter()
    detection = adapter.detect()
    assert detection.available is True

    prompt = adapter.prepare_prompt("ship it")
    assert "ship it" in prompt.text
    assert prompt.role == "builder"

    run_result = adapter.run("ship it")
    assert run_result.ok is True

    artifacts = adapter.collect("ship it")
    assert artifacts.files == ("README.md",)

    score = adapter.score(artifacts)
    assert score.value == 1.0
    assert 0.0 <= score.confidence <= 1.0


def test_fake_adapter_detection_reflects_state():
    assert _FakeAdapter(available=True).detect().available is True
    missing = _FakeAdapter(available=False).detect()
    assert missing.available is False
    assert missing.reason == "missing"


# ── Registry ────────────────────────────────────────────────────────────


def test_registry_starts_empty(fresh_registry):
    assert fresh_registry.known_workers() == []
    assert len(fresh_registry) == 0
    assert "fake" not in fresh_registry


def test_registry_register_and_get(fresh_registry):
    adapter = _FakeAdapter()
    fresh_registry.register(adapter)
    assert fresh_registry.get("fake") is adapter
    assert fresh_registry.known_workers() == ["fake"]
    assert "fake" in fresh_registry
    assert len(fresh_registry) == 1


def test_registry_get_unknown_raises(fresh_registry):
    with pytest.raises(KeyError, match="missing"):
        fresh_registry.get("missing")


def test_registry_rejects_duplicate_id(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    with pytest.raises(ValueError, match="already registered"):
        fresh_registry.register(_FakeAdapter())


def test_registry_replace_overrides_existing(fresh_registry):
    first = _FakeAdapter()
    second = _FakeAdapter()
    fresh_registry.register(first)
    fresh_registry.register(second, replace=True)
    assert fresh_registry.get("fake") is second


def test_registry_unregister_returns_adapter(fresh_registry):
    adapter = _FakeAdapter()
    fresh_registry.register(adapter)
    removed = fresh_registry.unregister("fake")
    assert removed is adapter
    assert "fake" not in fresh_registry


def test_registry_unregister_unknown_raises(fresh_registry):
    with pytest.raises(KeyError, match="missing"):
        fresh_registry.unregister("missing")


def test_registry_rejects_non_adapter(fresh_registry):
    with pytest.raises(TypeError, match="WorkerAdapter"):
        fresh_registry.register("not an adapter")  # type: ignore[arg-type]


def test_registry_iter_yields_registered_adapters(fresh_registry):
    a1 = _FakeAdapter()
    fresh_registry.register(a1)
    assert list(fresh_registry) == [a1]


def test_registry_contains_only_strings(fresh_registry):
    fresh_registry.register(_FakeAdapter())
    assert 123 not in fresh_registry  # type: ignore[operator]


def test_module_level_helpers_delegate_to_default(isolated_default_registry):
    adapter = _FakeAdapter()
    worker_registry.register(adapter)
    try:
        assert worker_registry.get("fake") is adapter
        assert "fake" in worker_registry.known_workers()
    finally:
        worker_registry.unregister("fake")
    assert worker_registry.known_workers() == []


def test_default_registry_is_a_registry_instance():
    assert isinstance(default_registry, WorkerRegistry)


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


# ── Public API surface ──────────────────────────────────────────────────


def test_public_api_exports():
    expected = {
        "WorkerAdapter",
        "WorkerArtifacts",
        "WorkerDetection",
        "WorkerPrompt",
        "WorkerRegistry",
        "WorkerRunResult",
        "WorkerScore",
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


def test_base_module_exports_only_data_and_adapter():
    # Sanity check: registry symbols don't leak into `base`.
    assert not hasattr(worker_base, "WorkerRegistry")
    assert not hasattr(worker_base, "register")
