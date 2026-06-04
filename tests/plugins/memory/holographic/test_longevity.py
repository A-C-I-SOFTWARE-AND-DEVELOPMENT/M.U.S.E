"""Tests for the longevity layer: importance, tiering, access, consolidation."""

from __future__ import annotations

import sqlite3
import time

from plugins.memory.holographic.consolidation import consolidate
from plugins.memory.holographic.retrieval import FactRetriever
from plugins.memory.holographic.store import MemoryStore


def test_migration_adds_longevity_columns(tmp_path):
    db = tmp_path / "legacy.db"
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute("INSERT INTO facts (content) VALUES ('old fact')")
    conn.commit()
    conn.close()

    store = MemoryStore(db_path=db)
    try:
        cols = {
            r[1] for r in store._conn.execute("PRAGMA table_info(facts)").fetchall()
        }
        assert {"importance", "last_accessed", "memory_tier"} <= cols
        # Old row readable; default tier applied to new rows.
        store.add_fact("new fact", importance=0.9)
        row = store._conn.execute(
            "SELECT importance, memory_tier FROM facts WHERE content = 'new fact'"
        ).fetchone()
        assert abs(row["importance"] - 0.9) < 1e-6
        assert row["memory_tier"] == "short"
    finally:
        store.close()


def test_record_access_bumps_count_and_timestamp(tmp_path):
    store = MemoryStore(db_path=tmp_path / "a.db")
    fid = store.add_fact("recall me")
    try:
        store.record_access([fid])
        row = store._conn.execute(
            "SELECT retrieval_count, last_accessed FROM facts WHERE fact_id = ?", (fid,)
        ).fetchone()
        assert row["retrieval_count"] == 1
        assert row["last_accessed"] is not None
    finally:
        store.close()


def test_search_tracks_access_when_enabled(tmp_path):
    store = MemoryStore(db_path=tmp_path / "t.db")
    fid = store.add_fact("trackable alpha")
    try:
        ret = FactRetriever(store, track_access=True)
        ret.search("trackable", min_trust=0.0, limit=5)
        row = store._conn.execute(
            "SELECT retrieval_count FROM facts WHERE fact_id = ?", (fid,)
        ).fetchone()
        assert row["retrieval_count"] >= 1
    finally:
        store.close()


def test_tiered_decay_long_outlasts_short(tmp_path):
    store = MemoryStore(db_path=tmp_path / "decay.db")
    try:
        ret = FactRetriever(store, short_half_life_days=1, long_half_life_days=365)
        # Same age, different tiers -> long decays far less.
        old_ts = "2000-01-01T00:00:00+00:00"
        short_fact = {"memory_tier": "short", "updated_at": old_ts, "created_at": old_ts}
        long_fact = {"memory_tier": "long", "updated_at": old_ts, "created_at": old_ts}
        d_short = ret._decay_for(short_fact)
        d_long = ret._decay_for(long_fact)
        assert d_long > d_short
    finally:
        store.close()


def test_consolidate_dry_run_does_not_mutate(tmp_path):
    store = MemoryStore(db_path=tmp_path / "c.db")
    try:
        # Two near-identical facts (token-Jaccard duplicate).
        store.add_fact("the deploy command is make deploy")
        store.add_fact("the deploy command is make deploy please")
        before = len(store.all_facts_for_consolidation())
        report = consolidate(store, dry_run=True, config={"dedup_threshold": 0.5})
        after = len(store.all_facts_for_consolidation())
        assert report.dry_run is True
        assert after == before  # nothing changed on a dry run
        assert len(report.merged) >= 1
    finally:
        store.close()


def test_consolidate_apply_merges_promotes_and_protects(tmp_path):
    store = MemoryStore(db_path=tmp_path / "c2.db")
    try:
        keep = store.add_fact("alpha beta gamma duplicate line", importance=0.1)
        dup = store.add_fact("alpha beta gamma duplicate line extra", importance=0.1)
        # A high-importance fact that must be promoted, never forgotten.
        important = store.add_fact("critical owner directive", importance=0.95)

        report = consolidate(
            store,
            dry_run=False,
            config={"dedup_threshold": 0.5, "promote_importance_threshold": 0.75},
        )

        ids = {f["fact_id"] for f in store.all_facts_for_consolidation()}
        # The duplicate was merged away (one of the pair removed).
        assert (keep in ids) != (dup in ids) or len(report.merged) >= 1
        # The important fact was promoted to long and still present.
        assert important in ids
        tier = store._conn.execute(
            "SELECT memory_tier FROM facts WHERE fact_id = ?", (important,)
        ).fetchone()["memory_tier"]
        assert tier == "long"
        assert any(p["fact_id"] == important for p in report.promoted)
    finally:
        store.close()


def test_consolidate_forgets_only_stale_low_value(tmp_path):
    store = MemoryStore(db_path=tmp_path / "c3.db")
    try:
        stale = store.add_fact("ephemeral low value note", importance=0.1)
        # Make it stale, low trust, short tier.
        store._conn.execute(
            "UPDATE facts SET trust_score = 0.1, created_at = '2000-01-01T00:00:00+00:00', "
            "updated_at = '2000-01-01T00:00:00+00:00', last_accessed = NULL "
            "WHERE fact_id = ?",
            (stale,),
        )
        # A protected high-trust fact, also old, must survive.
        protected = store.add_fact("durable trusted fact", importance=0.1)
        store._conn.execute(
            "UPDATE facts SET trust_score = 0.9, created_at = '2000-01-01T00:00:00+00:00', "
            "updated_at = '2000-01-01T00:00:00+00:00' WHERE fact_id = ?",
            (protected,),
        )
        store._conn.commit()

        report = consolidate(
            store,
            dry_run=False,
            config={"forget_after_days": 30, "forget_trust_floor": 0.3, "dedup_threshold": 0.99},
        )
        ids = {f["fact_id"] for f in store.all_facts_for_consolidation()}
        assert stale not in ids  # forgotten
        assert protected in ids  # high trust -> never forgotten
        assert any(fgt["fact_id"] == stale for fgt in report.forgotten)
    finally:
        store.close()
