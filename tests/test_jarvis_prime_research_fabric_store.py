"""Tests for the SQLite snapshot index + its internal hash chain."""

from __future__ import annotations

from muse_cli.jarvis_prime.research_fabric.store import SnapshotStore


def test_snapshot_chain_progresses_and_verifies(tmp_path) -> None:
    store = SnapshotStore(tmp_path / "rf.sqlite3")
    h1 = store.record_snapshot("a", "s1", {"x": 1})
    h2 = store.record_snapshot("b", "s2", {"y": 2})
    assert h1 != h2
    diag = store.verify_chain()
    assert diag.ok is True
    assert diag.length == 2
    store.close()


def test_tampered_row_is_detected(tmp_path) -> None:
    db = tmp_path / "rf.sqlite3"
    store = SnapshotStore(db)
    store.record_snapshot("a", "s1", {"x": 1})
    store.record_snapshot("b", "s2", {"y": 2})
    # Tamper with a payload directly in SQLite, leaving the row_hash stale.
    store.conn.execute(
        "UPDATE snapshots SET payload_json = ? WHERE kind = 'a'",
        ('{"x":999}',),
    )
    store.conn.commit()
    diag = store.verify_chain()
    assert diag.ok is False
    assert diag.broken_at == 0
    store.close()


def test_latest_and_list(tmp_path) -> None:
    store = SnapshotStore(tmp_path / "rf.sqlite3")
    store.record_snapshot("champion_freeze", "c1", {"n": 1})
    store.record_snapshot("champion_freeze", "c2", {"n": 2})
    latest = store.latest("champion_freeze")
    assert latest is not None and latest["subject"] == "c2"
    assert len(store.list_snapshots("champion_freeze")) == 2
    store.close()
