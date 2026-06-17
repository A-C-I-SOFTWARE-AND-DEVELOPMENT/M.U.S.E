"""Tests for the MUSE <-> Second Brain bridge.

Exercises the bridge with a fake brain (no database required) and verifies that
the real backend path degrades gracefully — raising the catchable
SecondBrainUnavailable rather than crashing — when the DB drivers aren't present.
"""

from __future__ import annotations

import pytest

from hermes_cli.jarvis_prime.second_brain_bridge import (
    RetrievedContext,
    SecondBrainUnavailable,
    is_available,
    retrieve,
)


class _FakePayload:
    def __init__(self, prompt: str, n_blocks: int) -> None:
        self._prompt = prompt
        self.blocks = list(range(n_blocks))

    def to_prompt(self) -> str:
        return self._prompt


class _FakeBrain:
    def __init__(self, payload, *, fail: bool = False) -> None:
        self._payload = payload
        self._fail = fail
        self.closed = False

    def retrieve(self, query, *, top_k=None):
        if self._fail:
            raise RuntimeError("boom")
        return self._payload

    def close(self) -> None:
        self.closed = True


def test_retrieve_with_fake_brain_returns_context():
    brain = _FakeBrain(_FakePayload("CONTEXT", 3))
    out = retrieve("q", factory=lambda *, enable_graph=False: brain)
    assert isinstance(out, RetrievedContext)
    assert out.text == "CONTEXT"
    assert out.block_count == 3
    assert out.source == "second_brain"
    assert brain.closed  # connections released even on the happy path


def test_factory_failure_is_wrapped_as_unavailable():
    def boom(*, enable_graph=False):
        raise ImportError("no psycopg")

    with pytest.raises(SecondBrainUnavailable, match="not available"):
        retrieve("q", factory=boom)


def test_retrieval_failure_is_wrapped_and_brain_closed():
    brain = _FakeBrain(_FakePayload("x", 1), fail=True)
    with pytest.raises(SecondBrainUnavailable, match="retrieval failed"):
        retrieve("q", factory=lambda *, enable_graph=False: brain)
    assert brain.closed  # closed even when retrieval raises


def test_is_available_imports_without_drivers():
    # second_brain.knowledge must be importable (driver-free) for capability checks.
    assert is_available() is True


def test_is_available_returns_false_when_parent_package_missing(monkeypatch):
    # find_spec imports the parent package; if second_brain isn't installed it
    # raises ModuleNotFoundError. The probe must swallow that and return False,
    # not crash.
    import importlib.util as iu

    def boom(name):
        raise ModuleNotFoundError("No module named 'second_brain'")

    monkeypatch.setattr(iu, "find_spec", boom)
    assert is_available() is False


def test_real_backend_degrades_gracefully_without_drivers():
    # In an environment without the DB drivers/backend, the real factory must
    # surface SecondBrainUnavailable (catchable) — never a bare ImportError.
    with pytest.raises(SecondBrainUnavailable):
        retrieve("q")
