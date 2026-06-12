"""
SQLite-backed fact store with entity resolution and trust scoring.
Single-user Hermes memory store plugin.
"""

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

try:
    from . import holographic as hrr
except ImportError:
    import holographic as hrr  # type: ignore[no-redef]  # ty: ignore[unresolved-import]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content         TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'general',
    tags            TEXT DEFAULT '',
    trust_score     REAL DEFAULT 0.5,
    retrieval_count INTEGER DEFAULT 0,
    helpful_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hrr_vector      BLOB,
    embedding       BLOB,
    embedding_dim   INTEGER,
    embedding_model TEXT,
    importance      REAL DEFAULT 0.5,
    last_accessed   TIMESTAMP,
    memory_tier     TEXT DEFAULT 'short'
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    entity_type TEXT DEFAULT 'unknown',
    aliases     TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_entities (
    fact_id   INTEGER REFERENCES facts(fact_id),
    entity_id INTEGER REFERENCES entities(entity_id),
    PRIMARY KEY (fact_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_facts_trust    ON facts(trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_entities_name  ON entities(name);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
    USING fts5(content, tags, content=facts, content_rowid=fact_id);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content, tags)
        VALUES (new.fact_id, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, tags)
        VALUES ('delete', old.fact_id, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, tags)
        VALUES ('delete', old.fact_id, old.content, old.tags);
    INSERT INTO facts_fts(rowid, content, tags)
        VALUES (new.fact_id, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS memory_banks (
    bank_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name  TEXT NOT NULL UNIQUE,
    vector     BLOB NOT NULL,
    dim        INTEGER NOT NULL,
    fact_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Trust adjustment constants
_HELPFUL_DELTA   =  0.05
_UNHELPFUL_DELTA = -0.10
_TRUST_MIN       =  0.0
_TRUST_MAX       =  1.0

# Entity extraction patterns
_RE_CAPITALIZED  = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
_RE_DOUBLE_QUOTE = re.compile(r'"([^"]+)"')
_RE_SINGLE_QUOTE = re.compile(r"'([^']+)'")
_RE_AKA          = re.compile(
    r'(\w+(?:\s+\w+)*)\s+(?:aka|also known as)\s+(\w+(?:\s+\w+)*)',
    re.IGNORECASE,
)


def _clamp_trust(value: float) -> float:
    return max(_TRUST_MIN, min(_TRUST_MAX, value))


class MemoryStore:
    """SQLite-backed fact store with entity resolution and trust scoring."""

    def __init__(
        self,
        db_path: "str | Path | None" = None,
        default_trust: float = 0.5,
        hrr_dim: int = 1024,
        embedding_backend=None,
    ) -> None:
        if db_path is None:
            from hermes_constants import get_hermes_home
            db_path = str(get_hermes_home() / "memory_store.db")
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_trust = _clamp_trust(default_trust)
        self.hrr_dim = hrr_dim
        self._hrr_available = hrr._HAS_NUMPY
        # Optional dense-embedding backend. When None (default) or unavailable,
        # no embeddings are computed and recall is unchanged from before.
        self._embedding_backend: Any = embedding_backend
        self._embeddings_enabled = bool(
            embedding_backend is not None and embedding_backend.is_available()
        )
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        self._lock = threading.RLock()
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables, indexes, and triggers if they do not exist. Enable WAL mode."""
        # Use the shared WAL-fallback helper so memory_store.db degrades
        # gracefully on NFS/SMB/FUSE-mounted HERMES_HOME (same issue as
        # state.db / kanban.db — see hermes_state._WAL_INCOMPAT_MARKERS).
        from hermes_state import apply_wal_with_fallback
        apply_wal_with_fallback(self._conn, db_label="memory_store.db (holographic)")
        self._conn.executescript(_SCHEMA)
        # Migrate: add columns if missing (safe + idempotent for existing DBs).
        # Every added column is nullable, so old rows and old code keep working.
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(facts)").fetchall()}
        if "hrr_vector" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN hrr_vector BLOB")
        # Dense-embedding columns (optional semantic recall). embedding_dim /
        # embedding_model make the blob self-describing so a model change never
        # silently mixes incompatible vector spaces at query time.
        if "embedding" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN embedding BLOB")
        if "embedding_dim" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN embedding_dim INTEGER")
        if "embedding_model" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN embedding_model TEXT")
        # Longevity columns (importance / recency / tier). All nullable or
        # defaulted, so existing rows and old code keep working unchanged.
        if "importance" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN importance REAL DEFAULT 0.5")
        if "last_accessed" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN last_accessed TIMESTAMP")
        if "memory_tier" not in columns:
            self._conn.execute("ALTER TABLE facts ADD COLUMN memory_tier TEXT DEFAULT 'short'")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_tier ON facts(memory_tier)"
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_fact(
        self,
        content: str,
        category: str = "general",
        tags: str = "",
        importance: float | None = None,
    ) -> int:
        """Insert a fact and return its fact_id.

        Deduplicates by content (UNIQUE constraint). On duplicate, returns
        the existing fact_id without modifying the row. Extracts entities from
        the content and links them to the fact.

        ``importance`` (0..1) is an optional longevity prior used by the
        consolidation pass and, when enabled, by recall ranking. Defaults to
        0.5 when not supplied.
        """
        with self._lock:
            content = content.strip()
            if not content:
                raise ValueError("content must not be empty")
            imp = 0.5 if importance is None else max(0.0, min(1.0, float(importance)))

            try:
                cur = self._conn.execute(
                    """
                    INSERT INTO facts (content, category, tags, trust_score, importance)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (content, category, tags, self.default_trust, imp),
                )
                self._conn.commit()
                fact_id: int = cur.lastrowid  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
            except sqlite3.IntegrityError:
                # Duplicate content — return existing id
                row = self._conn.execute(
                    "SELECT fact_id FROM facts WHERE content = ?", (content,)
                ).fetchone()
                return int(row["fact_id"])

            # Entity extraction and linking
            for name in self._extract_entities(content):
                entity_id = self._resolve_entity(name)
                self._link_fact_entity(fact_id, entity_id)

            # Compute HRR vector after entity linking
            self._compute_hrr_vector(fact_id, content)
            self._compute_embedding(fact_id, content)
            self._rebuild_bank(category)

            return fact_id

    def search_facts(
        self,
        query: str,
        category: str | None = None,
        min_trust: float = 0.3,
        limit: int = 10,
    ) -> list[dict]:
        """Full-text search over facts using FTS5.

        Returns a list of fact dicts ordered by FTS5 rank, then trust_score
        descending. Also increments retrieval_count for matched facts.
        """
        with self._lock:
            query = query.strip()
            if not query:
                return []

            params: list = [query, min_trust]
            category_clause = ""
            if category is not None:
                category_clause = "AND f.category = ?"
                params.append(category)
            params.append(limit)

            sql = f"""
                SELECT f.fact_id, f.content, f.category, f.tags,
                       f.trust_score, f.retrieval_count, f.helpful_count,
                       f.created_at, f.updated_at
                FROM facts f
                JOIN facts_fts fts ON fts.rowid = f.fact_id
                WHERE facts_fts MATCH ?
                  AND f.trust_score >= ?
                  {category_clause}
                ORDER BY fts.rank, f.trust_score DESC
                LIMIT ?
            """

            rows = self._conn.execute(sql, params).fetchall()
            results = [self._row_to_dict(r) for r in rows]

            if results:
                ids = [r["fact_id"] for r in results]
                placeholders = ",".join("?" * len(ids))
                self._conn.execute(
                    f"UPDATE facts SET retrieval_count = retrieval_count + 1 WHERE fact_id IN ({placeholders})",
                    ids,
                )
                self._conn.commit()

            return results

    def update_fact(
        self,
        fact_id: int,
        content: str | None = None,
        trust_delta: float | None = None,
        tags: str | None = None,
        category: str | None = None,
    ) -> bool:
        """Partially update a fact. Trust is clamped to [0, 1].

        Returns True if the row existed, False otherwise.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT fact_id, trust_score FROM facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()
            if row is None:
                return False

            assignments: list[str] = ["updated_at = CURRENT_TIMESTAMP"]
            params: list = []

            if content is not None:
                assignments.append("content = ?")
                params.append(content.strip())
            if tags is not None:
                assignments.append("tags = ?")
                params.append(tags)
            if category is not None:
                assignments.append("category = ?")
                params.append(category)
            if trust_delta is not None:
                new_trust = _clamp_trust(row["trust_score"] + trust_delta)
                assignments.append("trust_score = ?")
                params.append(new_trust)

            params.append(fact_id)
            self._conn.execute(
                f"UPDATE facts SET {', '.join(assignments)} WHERE fact_id = ?",
                params,
            )
            self._conn.commit()

            # If content changed, re-extract entities
            if content is not None:
                self._conn.execute(
                    "DELETE FROM fact_entities WHERE fact_id = ?", (fact_id,)
                )
                for name in self._extract_entities(content):
                    entity_id = self._resolve_entity(name)
                    self._link_fact_entity(fact_id, entity_id)
                self._conn.commit()

            # Recompute HRR vector + embedding if content changed
            if content is not None:
                self._compute_hrr_vector(fact_id, content)
                self._compute_embedding(fact_id, content)
            # Rebuild bank for relevant category
            cat = category or self._conn.execute(
                "SELECT category FROM facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()["category"]
            self._rebuild_bank(cat)

            return True

    def remove_fact(self, fact_id: int) -> bool:
        """Delete a fact and its entity links. Returns True if the row existed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT fact_id, category FROM facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()
            if row is None:
                return False

            self._conn.execute(
                "DELETE FROM fact_entities WHERE fact_id = ?", (fact_id,)
            )
            self._conn.execute("DELETE FROM facts WHERE fact_id = ?", (fact_id,))
            self._conn.commit()
            self._rebuild_bank(row["category"])
            return True

    def list_facts(
        self,
        category: str | None = None,
        min_trust: float = 0.0,
        limit: int = 50,
    ) -> list[dict]:
        """Browse facts ordered by trust_score descending.

        Optionally filter by category and minimum trust score.
        """
        with self._lock:
            params: list = [min_trust]
            category_clause = ""
            if category is not None:
                category_clause = "AND category = ?"
                params.append(category)
            params.append(limit)

            sql = f"""
                SELECT fact_id, content, category, tags, trust_score,
                       retrieval_count, helpful_count, created_at, updated_at
                FROM facts
                WHERE trust_score >= ?
                  {category_clause}
                ORDER BY trust_score DESC
                LIMIT ?
            """
            rows = self._conn.execute(sql, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def record_feedback(self, fact_id: int, helpful: bool) -> dict:
        """Record user feedback and adjust trust asymmetrically.

        helpful=True  -> trust += 0.05, helpful_count += 1
        helpful=False -> trust -= 0.10

        Returns a dict with fact_id, old_trust, new_trust, helpful_count.
        Raises KeyError if fact_id does not exist.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT fact_id, trust_score, helpful_count FROM facts WHERE fact_id = ?",
                (fact_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"fact_id {fact_id} not found")

            old_trust: float = row["trust_score"]
            delta = _HELPFUL_DELTA if helpful else _UNHELPFUL_DELTA
            new_trust = _clamp_trust(old_trust + delta)

            helpful_increment = 1 if helpful else 0
            self._conn.execute(
                """
                UPDATE facts
                SET trust_score    = ?,
                    helpful_count  = helpful_count + ?,
                    updated_at     = CURRENT_TIMESTAMP
                WHERE fact_id = ?
                """,
                (new_trust, helpful_increment, fact_id),
            )
            self._conn.commit()

            return {
                "fact_id":      fact_id,
                "old_trust":    old_trust,
                "new_trust":    new_trust,
                "helpful_count": row["helpful_count"] + helpful_increment,
            }

    # ------------------------------------------------------------------
    # Entity helpers
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str) -> list[str]:
        """Extract entity candidates from text using simple regex rules.

        Rules applied (in order):
        1. Capitalized multi-word phrases  e.g. "John Doe"
        2. Double-quoted terms             e.g. "Python"
        3. Single-quoted terms             e.g. 'pytest'
        4. AKA patterns                    e.g. "Guido aka BDFL" -> two entities

        Returns a deduplicated list preserving first-seen order.
        """
        seen: set[str] = set()
        candidates: list[str] = []

        def _add(name: str) -> None:
            stripped = name.strip()
            if stripped and stripped.lower() not in seen:
                seen.add(stripped.lower())
                candidates.append(stripped)

        for m in _RE_CAPITALIZED.finditer(text):
            _add(m.group(1))

        for m in _RE_DOUBLE_QUOTE.finditer(text):
            _add(m.group(1))

        for m in _RE_SINGLE_QUOTE.finditer(text):
            _add(m.group(1))

        for m in _RE_AKA.finditer(text):
            _add(m.group(1))
            _add(m.group(2))

        return candidates

    def _resolve_entity(self, name: str) -> int:
        """Find an existing entity by name or alias (case-insensitive) or create one.

        Returns the entity_id.
        """
        # Exact name match
        row = self._conn.execute(
            "SELECT entity_id FROM entities WHERE name LIKE ?", (name,)
        ).fetchone()
        if row is not None:
            return int(row["entity_id"])

        # Search aliases — aliases stored as comma-separated; use LIKE with % boundaries
        alias_row = self._conn.execute(
            """
            SELECT entity_id FROM entities
            WHERE ',' || aliases || ',' LIKE '%,' || ? || ',%'
            """,
            (name,),
        ).fetchone()
        if alias_row is not None:
            return int(alias_row["entity_id"])

        # Create new entity
        cur = self._conn.execute(
            "INSERT INTO entities (name) VALUES (?)", (name,)
        )
        self._conn.commit()
        return int(cur.lastrowid)  # type: ignore[return-value]  # ty: ignore[invalid-argument-type]

    def _link_fact_entity(self, fact_id: int, entity_id: int) -> None:
        """Insert into fact_entities, silently ignore if the link already exists."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO fact_entities (fact_id, entity_id)
            VALUES (?, ?)
            """,
            (fact_id, entity_id),
        )
        self._conn.commit()

    def _compute_hrr_vector(self, fact_id: int, content: str) -> None:
        """Compute and store HRR vector for a fact. No-op if numpy unavailable."""
        with self._lock:
            if not self._hrr_available:
                return

            # Get entities linked to this fact
            rows = self._conn.execute(
                """
                SELECT e.name FROM entities e
                JOIN fact_entities fe ON fe.entity_id = e.entity_id
                WHERE fe.fact_id = ?
                """,
                (fact_id,),
            ).fetchall()
            entities = [row["name"] for row in rows]

            vector = hrr.encode_fact(content, entities, self.hrr_dim)
            self._conn.execute(
                "UPDATE facts SET hrr_vector = ? WHERE fact_id = ?",
                (hrr.phases_to_bytes(vector), fact_id),
            )
            self._conn.commit()

    def _compute_embedding(self, fact_id: int, content: str) -> None:
        """Compute and store a dense embedding for a fact.

        No-op when no embedding backend is configured/available. A failure to
        embed (offline API, missing model) is swallowed so it can never break
        a fact write — the fact simply has no embedding and recall falls back
        to the keyword/HRR path for that row.
        """
        with self._lock:
            if not self._embeddings_enabled:
                return
            try:
                vec = self._embedding_backend.embed(content)
            except Exception:
                vec = None
            if not vec:
                return
            from .embeddings import vector_to_bytes

            self._conn.execute(
                "UPDATE facts SET embedding = ?, embedding_dim = ?, "
                "embedding_model = ? WHERE fact_id = ?",
                (
                    vector_to_bytes(vec),
                    len(vec),
                    getattr(self._embedding_backend, "name", "unknown"),
                    fact_id,
                ),
            )
            self._conn.commit()

    def rebuild_all_embeddings(self) -> int:
        """Recompute embeddings for every fact. For migration / model changes.

        Returns the number of facts processed (0 when embeddings are disabled).
        """
        with self._lock:
            if not self._embeddings_enabled:
                return 0
            rows = self._conn.execute(
                "SELECT fact_id, content FROM facts"
            ).fetchall()
            for row in rows:
                self._compute_embedding(row["fact_id"], row["content"])
            return len(rows)

    # ------------------------------------------------------------------
    # Longevity helpers (importance, recency, tiering, consolidation)
    # ------------------------------------------------------------------

    def record_access(self, fact_ids: "list[int]") -> None:
        """Bump retrieval_count and stamp last_accessed for recalled facts.

        This is the recency/frequency signal the consolidation pass uses to
        decide what to promote and what is safe to forget. Cheap, best-effort.
        """
        ids = [int(i) for i in fact_ids if i is not None]
        if not ids:
            return
        with self._lock:
            placeholders = ",".join("?" * len(ids))
            self._conn.execute(
                f"UPDATE facts SET retrieval_count = retrieval_count + 1, "
                f"last_accessed = CURRENT_TIMESTAMP WHERE fact_id IN ({placeholders})",
                ids,
            )
            self._conn.commit()

    def set_memory_tier(self, fact_id: int, tier: str) -> bool:
        """Set a fact's memory tier ('short' | 'long'). Returns True if it existed."""
        if tier not in ("short", "long"):
            raise ValueError("tier must be 'short' or 'long'")
        with self._lock:
            cur = self._conn.execute(
                "UPDATE facts SET memory_tier = ? WHERE fact_id = ?", (tier, fact_id)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def set_importance(self, fact_id: int, importance: float) -> bool:
        """Set a fact's importance prior in [0, 1]. Returns True if it existed."""
        imp = max(0.0, min(1.0, float(importance)))
        with self._lock:
            cur = self._conn.execute(
                "UPDATE facts SET importance = ? WHERE fact_id = ?", (imp, fact_id)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def merge_facts(self, keep_id: int, drop_id: int) -> bool:
        """Merge ``drop_id`` into ``keep_id`` and delete the duplicate.

        The kept fact inherits the higher trust/importance, the summed access
        counts, and the union of tags. Non-destructive to the kept signal.
        Returns True when the merge happened.
        """
        if keep_id == drop_id:
            return False
        with self._lock:
            keep = self._conn.execute(
                "SELECT fact_id, tags, trust_score, importance, retrieval_count, "
                "helpful_count, memory_tier, category FROM facts WHERE fact_id = ?",
                (keep_id,),
            ).fetchone()
            drop = self._conn.execute(
                "SELECT fact_id, tags, trust_score, importance, retrieval_count, "
                "helpful_count FROM facts WHERE fact_id = ?",
                (drop_id,),
            ).fetchone()
            if keep is None or drop is None:
                return False

            keep_tags = {t.strip() for t in (keep["tags"] or "").split(",") if t.strip()}
            drop_tags = {t.strip() for t in (drop["tags"] or "").split(",") if t.strip()}
            merged_tags = ",".join(sorted(keep_tags | drop_tags))
            self._conn.execute(
                """
                UPDATE facts SET
                    tags = ?,
                    trust_score = MAX(trust_score, ?),
                    importance = MAX(importance, ?),
                    retrieval_count = retrieval_count + ?,
                    helpful_count = helpful_count + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE fact_id = ?
                """,
                (
                    merged_tags,
                    drop["trust_score"],
                    drop["importance"] if drop["importance"] is not None else 0.0,
                    drop["retrieval_count"] or 0,
                    drop["helpful_count"] or 0,
                    keep_id,
                ),
            )
            self._conn.execute("DELETE FROM fact_entities WHERE fact_id = ?", (drop_id,))
            self._conn.execute("DELETE FROM facts WHERE fact_id = ?", (drop_id,))
            self._conn.commit()
            self._rebuild_bank(keep["category"])
            return True

    def all_facts_for_consolidation(self) -> "list[dict]":
        """Return every fact with the columns the consolidation pass needs."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT fact_id, content, category, tags, trust_score, importance, "
                "retrieval_count, helpful_count, memory_tier, created_at, "
                "last_accessed, updated_at, embedding, embedding_dim "
                "FROM facts"
            ).fetchall()
            return [dict(r) for r in rows]

    def _rebuild_bank(self, category: str) -> None:
        """Full rebuild of a category's memory bank from all its fact vectors."""
        with self._lock:
            if not self._hrr_available:
                return

            bank_name = f"cat:{category}"
            rows = self._conn.execute(
                "SELECT hrr_vector FROM facts WHERE category = ? AND hrr_vector IS NOT NULL",
                (category,),
            ).fetchall()

            if not rows:
                self._conn.execute("DELETE FROM memory_banks WHERE bank_name = ?", (bank_name,))
                self._conn.commit()
                return

            vectors = [hrr.bytes_to_phases(row["hrr_vector"]) for row in rows]
            bank_vector = hrr.bundle(*vectors)
            fact_count = len(vectors)

            # Check SNR
            hrr.snr_estimate(self.hrr_dim, fact_count)

            self._conn.execute(
                """
                INSERT INTO memory_banks (bank_name, vector, dim, fact_count, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bank_name) DO UPDATE SET
                    vector = excluded.vector,
                    dim = excluded.dim,
                    fact_count = excluded.fact_count,
                    updated_at = excluded.updated_at
                """,
                (bank_name, hrr.phases_to_bytes(bank_vector), self.hrr_dim, fact_count),
            )
            self._conn.commit()

    def rebuild_all_vectors(self, dim: int | None = None) -> int:
        """Recompute all HRR vectors + banks from text. For recovery/migration.

        Returns the number of facts processed.
        """
        with self._lock:
            if not self._hrr_available:
                return 0

            if dim is not None:
                self.hrr_dim = dim

            rows = self._conn.execute(
                "SELECT fact_id, content, category FROM facts"
            ).fetchall()

            categories: set[str] = set()
            for row in rows:
                self._compute_hrr_vector(row["fact_id"], row["content"])
                categories.add(row["category"])

            for category in categories:
                self._rebuild_bank(category)

            return len(rows)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict."""
        return dict(row)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
