"""Tests for hermes_cli.jarvis_prime.memory — STM/LTM + recollection."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.memory import MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(journal_path=tmp_path / "memory.jsonl")


def test_remember_secret_is_rejected(store: MemoryStore) -> None:
    record = store.remember("api token", "AWS_KEY=sk-1234567890abcdefghij1234567890")
    assert record is None
    assert store.session == []


def test_remember_token_pattern_rejected(store: MemoryStore) -> None:
    record = store.remember("github", "ghp_abcdefghijklmnopqrstuvwxyz1234567890")
    assert record is None


@pytest.mark.parametrize(
    "secret_value",
    [
        "AKIAIOSFODNN7EXAMPLE",                                    # AWS access key
        "SSN on file: 123-45-6789",                                # US SSN
        "card 4111 1111 1111 1111 expires soon".replace(" ", ""),  # Visa
        "card 5500000000000004",                                   # Mastercard
        "card 340000000000009",                                    # AmEx
        "-----BEGIN RSA PRIVATE KEY-----\\nMIIEpAIBAAKC",          # PEM
        "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXkt",  # OpenSSH
        # JWT (header.payload.signature with realistic lengths)
        "eyJhbGciOiJIUzI1NiJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ",
    ],
)
def test_remember_extended_secret_patterns_rejected(
    store: MemoryStore, secret_value: str
) -> None:
    """Final-release review (W1): SSN, AWS, cards, PEM, JWT must be rejected."""
    record = store.remember("leak", secret_value)
    assert record is None


def test_remember_temporary_emotion_downgrades_to_session(store: MemoryStore) -> None:
    record = store.remember(
        "mood",
        "I'm tired and feeling stressed about the launch",
        durability="durable",
    )
    assert record is not None
    assert record.durability == "session"


def test_durable_low_confidence_rejected(store: MemoryStore) -> None:
    assert store.remember(
        "claim", "the moon is made of green cheese", durability="durable", confidence=0.4
    ) is None


def test_durable_high_confidence_accepted(store: MemoryStore) -> None:
    record = store.remember(
        "mission", "ship muse v1", durability="durable", confidence=0.9
    )
    assert record is not None
    assert record.durability == "durable"
    assert store.durable[-1].value == "ship muse v1"


def test_journal_persistence_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "memory.jsonl"
    s1 = MemoryStore(journal_path=path)
    s1.remember("mission", "ship v1", durability="durable", confidence=0.9)
    s1.remember("session note", "discussed pricing", durability="session")

    # Working memory does NOT persist.
    s1.remember("scratch", "temp", durability="working")

    s2 = MemoryStore(journal_path=path)
    durable_keys = {r.key for r in s2.durable}
    session_keys = {r.key for r in s2.session}
    assert "mission" in durable_keys
    assert "session note" in session_keys
    assert "scratch" not in (durable_keys | session_keys)


def test_recollect_ranks_durable_above_session(store: MemoryStore) -> None:
    store.remember("session topic", "we talked about pricing strategy", durability="session")
    store.remember("durable mission", "ship pricing model v2", durability="durable", confidence=0.9)
    hits = store.recollect("pricing")
    assert hits
    # Durable hit should outrank session hit thanks to weight 1.5 vs 1.0.
    assert hits[0].durability == "durable"


def test_recollect_returns_empty_when_no_match(store: MemoryStore) -> None:
    store.remember("foo", "bar", durability="session")
    assert store.recollect("unrelated query xyz") == []


def test_summarize_for_prompt_renders_block(store: MemoryStore) -> None:
    store.remember("mission", "ship JARVIS", durability="durable", confidence=0.9)
    block = store.summarize_for_prompt("ship", limit=3)
    assert "RECOLLECTION" in block
    assert "mission" in block
    assert "JARVIS" in block


def test_forget_removes_by_key(store: MemoryStore) -> None:
    store.remember("topic", "first", durability="session")
    store.remember("topic", "second", durability="session")
    removed = store.forget("topic")
    assert removed == 2
    assert store.session == []


def test_forget_persists_across_a_new_store(tmp_path: Path) -> None:
    """A forget must be durable — a fresh store (e.g. the per-request cockpit
    handler) must not reload the forgotten record."""
    path = tmp_path / "memory.jsonl"
    s1 = MemoryStore(journal_path=path)
    s1.remember("deploy_window", "after 6pm", durability="durable", confidence=0.9)
    s1.remember("keep", "this one stays", durability="durable", confidence=0.9)
    assert s1.forget("deploy_window") == 1

    s2 = MemoryStore(journal_path=path)
    keys = {r.key for r in s2.durable}
    assert "deploy_window" not in keys  # persisted removal
    assert "keep" in keys  # untouched record survives the rewrite


def test_journal_path_honors_hermes_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = MemoryStore()
    assert str(tmp_path) in str(store.journal_path)
    assert store.journal_path.name == "memory.jsonl"
