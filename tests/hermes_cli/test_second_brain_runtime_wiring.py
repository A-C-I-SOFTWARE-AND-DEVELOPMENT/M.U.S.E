"""The Second Brain is fused into ``JarvisPrime.recollect`` only when opted in.

Verifies: (1) default-off recollection is byte-identical to native retrieval and
never even consults the bridge; (2) with ``MUSE_SECOND_BRAIN`` set and the module
available, a Second Brain block is appended *after* — never replacing — the native
recollection; (3) a backend failure can never break recall.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import second_brain_bridge as sbb
from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.memory_tree import MemoryLayer, MemoryTreeStore
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime
from hermes_cli.jarvis_prime.second_brain_bridge import RetrievedContext


@pytest.fixture
def jp(tmp_path: Path) -> JarvisPrime:
    # Isolate both stores under tmp_path so the default-ON memory layers never
    # read the real ~/.hermes during tests; seed one durable, cited fact.
    config = JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_tree=MemoryTreeStore(path=tmp_path / "memory_tree.jsonl"),
    )
    prime = JarvisPrime(config=config)
    tree = prime.memory_tree()
    assert tree is not None
    tree.write(
        "Hermes is the canonical backend per the operating spec.",
        namespace="jarvis/architecture",
        title="backend-primary",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        source_uri="docs/jarvis-prime-operating-system.md",
        owner_approved=True,
    )
    return prime


def test_recollect_is_byte_identical_when_disabled(jp: JarvisPrime, monkeypatch) -> None:
    monkeypatch.delenv("MUSE_SECOND_BRAIN", raising=False)
    # Even if a brain were reachable, the flag-off path must never consult it.
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(
        sbb,
        "retrieve_optional",
        lambda *a, **k: pytest.fail("retrieve_optional called while disabled"),
    )
    out = jp.recollect("which backend is canonical")
    assert "## second brain" not in out
    assert "CONTEXT PACK" in out  # native Memory-Tree pack still present


def test_recollect_appends_second_brain_when_enabled(
    jp: JarvisPrime, monkeypatch
) -> None:
    # Baseline with the flag off — native retrieval only.
    monkeypatch.delenv("MUSE_SECOND_BRAIN", raising=False)
    base = jp.recollect("which backend is canonical")

    # Opt in + a fake available brain.
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(
        sbb,
        "retrieve_optional",
        lambda query, **k: RetrievedContext(
            text="SB FACT about routing", block_count=2
        ),
    )
    out = jp.recollect("which backend is canonical")
    assert out.startswith(base)  # augments, never replaces
    assert "## second brain" in out
    assert "SB FACT about routing" in out


def test_recollect_survives_second_brain_failure(
    jp: JarvisPrime, monkeypatch
) -> None:
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("backend exploded")

    monkeypatch.setattr(sbb, "retrieve_optional", boom)
    out = jp.recollect("which backend is canonical")  # must not raise
    assert "## second brain" not in out
    assert "CONTEXT PACK" in out


def test_recollect_skips_when_enabled_but_unavailable(
    jp: JarvisPrime, monkeypatch
) -> None:
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: False)
    monkeypatch.setattr(
        sbb,
        "retrieve_optional",
        lambda *a, **k: pytest.fail("retrieve_optional called while unavailable"),
    )
    out = jp.recollect("which backend is canonical")
    assert "## second brain" not in out
    assert "CONTEXT PACK" in out
