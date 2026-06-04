"""Store-level tests for the optional embedding column + migration."""

from __future__ import annotations

import sqlite3

from plugins.memory.holographic.embeddings import EmbeddingBackend
from plugins.memory.holographic.store import MemoryStore


class FakeBackend(EmbeddingBackend):
    """Deterministic embedding backend — no model load, no network."""

    name = "fake"

    def __init__(self, mapping=None, dim=3):
        self._mapping = mapping or {}
        self.dim = dim

    def is_available(self) -> bool:
        return True

    def embed(self, text):
        if text in self._mapping:
            return list(self._mapping[text])
        # Default deterministic non-zero unit vector.
        return [1.0] + [0.0] * (self.dim - 1)


def _columns(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(facts)").fetchall()}
    finally:
        conn.close()


def test_migration_adds_embedding_columns_to_legacy_db(tmp_path):
    db = tmp_path / "legacy.db"
    # Simulate an old DB that only has the pre-embedding schema (+ hrr_vector).
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE facts (
            fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT 'general',
            tags TEXT DEFAULT '',
            trust_score REAL DEFAULT 0.5,
            retrieval_count INTEGER DEFAULT 0,
            helpful_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hrr_vector BLOB
        );
        """
    )
    conn.execute("INSERT INTO facts (content) VALUES ('legacy fact')")
    conn.commit()
    conn.close()

    # Opening through MemoryStore must add the new columns and keep old rows.
    store = MemoryStore(db_path=db)
    try:
        cols = _columns(db)
        assert {"embedding", "embedding_dim", "embedding_model"} <= cols
        rows = store.list_facts(min_trust=0.0)
        assert any(r["content"] == "legacy fact" for r in rows)
    finally:
        store.close()


def test_add_fact_writes_embedding_when_backend_present(tmp_path):
    db = tmp_path / "emb.db"
    store = MemoryStore(db_path=db, embedding_backend=FakeBackend())
    try:
        fid = store.add_fact("a brand new fact")
        row = store._conn.execute(
            "SELECT embedding, embedding_dim, embedding_model FROM facts WHERE fact_id = ?",
            (fid,),
        ).fetchone()
        assert row["embedding"] is not None
        assert row["embedding_dim"] == 3
        assert row["embedding_model"] == "fake"
    finally:
        store.close()


def test_add_fact_leaves_embedding_null_without_backend(tmp_path):
    db = tmp_path / "noemb.db"
    store = MemoryStore(db_path=db)  # no backend
    try:
        fid = store.add_fact("a fact with no embedding")
        row = store._conn.execute(
            "SELECT embedding FROM facts WHERE fact_id = ?", (fid,)
        ).fetchone()
        assert row["embedding"] is None
    finally:
        store.close()


def test_rebuild_all_embeddings(tmp_path):
    db = tmp_path / "rebuild.db"
    # Start with no backend so facts land without embeddings...
    store = MemoryStore(db_path=db)
    store.add_fact("fact one")
    store.add_fact("fact two")
    store.close()

    # ...then reopen with a backend and backfill.
    store2 = MemoryStore(db_path=db, embedding_backend=FakeBackend())
    try:
        n = store2.rebuild_all_embeddings()
        assert n == 2
        missing = store2._conn.execute(
            "SELECT COUNT(*) FROM facts WHERE embedding IS NULL"
        ).fetchone()[0]
        assert missing == 0
    finally:
        store2.close()
