-- ===========================================================================
-- Second Brain — initial schema (Layer 2: Persistent Storage)
--
-- Target: PostgreSQL 14+ with the pgvector extension.
--
-- IMPORTANT: the vector dimension below (1536) MUST match
-- SECOND_BRAIN_EMBEDDING_DIM / EmbeddingConfig.dimension. If you change the
-- embedding model's dimension, change it here too and re-create the table.
--
-- This script is idempotent and is also mounted into the Postgres container's
-- docker-entrypoint-initdb.d by docker-compose.yml.
-- ===========================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- --------------------------------------------------------------------------
-- Raw source documents (immutable origin for every derived node).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL,
    title        TEXT,
    raw_content  TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT documents_content_hash_key UNIQUE (content_hash)
);

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents (source_id);

-- --------------------------------------------------------------------------
-- Memory nodes (the canonical unit of governed knowledge).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memory_nodes (
    id                  TEXT PRIMARY KEY,
    content             TEXT NOT NULL,
    embedding           vector(1536),
    entities            TEXT[] NOT NULL DEFAULT '{}',
    relationships       TEXT[] NOT NULL DEFAULT '{}',
    source_id           TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence_score    DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    version             INTEGER NOT NULL DEFAULT 1,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at    TIMESTAMPTZ,
    reinforcement_count INTEGER NOT NULL DEFAULT 0,
    ttl_expires_at      TIMESTAMPTZ,
    document_id         TEXT REFERENCES documents (id) ON DELETE CASCADE,
    content_hash        TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT memory_nodes_confidence_range
        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
);

-- Approximate-nearest-neighbour index for cosine similarity. HNSW (pgvector
-- >= 0.5) gives strong recall/latency. For very large corpora consider
-- IVFFlat instead:
--   CREATE INDEX ON memory_nodes USING ivfflat (embedding vector_cosine_ops)
--       WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_embedding_hnsw
    ON memory_nodes USING hnsw (embedding vector_cosine_ops);

-- Graph/membership and governance access paths.
CREATE INDEX IF NOT EXISTS idx_memory_nodes_entities
    ON memory_nodes USING gin (entities);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_source_id
    ON memory_nodes (source_id);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_document_id
    ON memory_nodes (document_id);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_ttl
    ON memory_nodes (ttl_expires_at);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_content_hash
    ON memory_nodes (content_hash);

-- Full-text index backing the keyword (BM25-like) fallback path.
CREATE INDEX IF NOT EXISTS idx_memory_nodes_fts
    ON memory_nodes USING gin (to_tsvector('english', content));

-- --------------------------------------------------------------------------
-- Provenance (append-only origin/transformation chain per node).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provenance (
    id             TEXT PRIMARY KEY,
    node_id        TEXT NOT NULL REFERENCES memory_nodes (id) ON DELETE CASCADE,
    source_id      TEXT NOT NULL,
    source_type    TEXT,
    source_uri     TEXT,
    transformation TEXT,
    content_hash   TEXT,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_provenance_node_id ON provenance (node_id);
CREATE INDEX IF NOT EXISTS idx_provenance_source_id ON provenance (source_id);

-- --------------------------------------------------------------------------
-- Version history (immutable snapshots for audit / rollback).
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS node_versions (
    id               BIGSERIAL PRIMARY KEY,
    node_id          TEXT NOT NULL REFERENCES memory_nodes (id) ON DELETE CASCADE,
    version          INTEGER NOT NULL,
    content          TEXT,
    confidence_score DOUBLE PRECISION,
    reason           TEXT,
    changed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_node_versions_node_id ON node_versions (node_id);

-- --------------------------------------------------------------------------
-- Keep updated_at fresh on every row mutation.
-- --------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_memory_nodes_updated_at ON memory_nodes;
CREATE TRIGGER trg_memory_nodes_updated_at
    BEFORE UPDATE ON memory_nodes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
