# Architecture

The Second Brain is a five-layer hybrid knowledge system. Each layer has a
single responsibility and a narrow, dependency-injected interface, so layers
can be tested in isolation and backends swapped without touching callers.

## Design principles

1. **Hybrid by default.** Dense vector recall captures semantic similarity;
   the graph captures explicit structure and enables multi-hop reasoning.
   Neither alone is sufficient — the orchestrator fuses both and adds a
   keyword fallback for lexical/rare-term queries.
2. **Everything is governed.** Every node carries confidence, provenance, a
   version, and a TTL. Knowledge is not write-once; it decays, is reinforced,
   consolidated, and refreshed (a knowledge lifecycle, not a dump).
3. **Source-backed answers.** Retrieval returns citation-tagged blocks with
   provenance so downstream prompts stay grounded and auditable.
4. **Runnable without infrastructure.** Core logic is standard-library only;
   drivers (psycopg2, neo4j) and models (sentence-transformers, OpenAI) are
   lazy. This keeps unit tests, CI, and demos fast and hermetic.
5. **No global state.** Configuration is an immutable `Settings` snapshot
   passed explicitly; stores and engines receive their collaborators by
   constructor injection.

## Data flow

```
                        ┌──────────────────────────────────────────────┐
   raw source           │ LAYER 1  Ingestion & Representation           │
   (text + metadata) ──▶│  semantic chunking → metadata/entity/         │
                        │  relationship extraction → embedding →        │
                        │  provenance tagging → MemoryNode              │
                        └───────────────┬──────────────────────────────┘
                                        │ upsert
                        ┌───────────────▼──────────────────────────────┐
                        │ LAYER 2  Persistent Storage                   │
                        │  Postgres+pgvector (vectors, nodes, FTS)      │
                        │  Neo4j (entities, typed relationships)        │
                        │  documents (raw)   provenance   node_versions │
                        └───────────────┬──────────────────────────────┘
                                        │ read
   query ──────────────▶┌──────────────▼──────────────────────────────┐
                        │ LAYER 3  Hybrid Retrieval Orchestrator        │
                        │  vector search → graph expansion →            │
                        │  keyword fallback → merge → rank → budget     │
                        │  priority = 0.5·sim + 0.3·conf + 0.2·recency  │
                        └───────────────┬──────────────────────────────┘
                                        │ InjectionPayload / nodes
                        ┌───────────────▼──────────────────────────────┐
                        │ LAYER 4  Reasoning Engine                     │
                        │  multi-hop traversal → conflict detection →   │
                        │  confidence-weighted inference                │
                        └───────────────────────────────────────────────┘

         ┌──────────────────────────────────────────────────────────────┐
         │ LAYER 5  Governance & Lifecycle (runs continuously/scheduled) │
         │  TTL decay · reinforcement · consolidation · embedding        │
         │  refresh · version tracking · confidence adjustment           │
         └──────────────────────────────────────────────────────────────┘
```

## Layer 1 — Ingestion & Representation

- **Semantic chunking** (`SemanticChunker`): paragraph- and sentence-aware,
  greedy packing to a token target with a sliding overlap window to preserve
  cross-boundary context.
- **Metadata extraction** (`MetadataExtractor`): length, top terms, numeric
  presence, content hash.
- **Entity extraction** (`EntityExtractor` → `RegexEntityExtractor`): heuristic
  proper-noun and acronym detection by default; pluggable for spaCy/LLM NER.
- **Relationship mapping** (`RelationshipExtractor`): intra-sentence
  co-occurrence plus a lightweight subject-verb-object heuristic, emitted as
  typed triples.
- **Embedding abstraction** (`EmbeddingProvider`): `HashingEmbeddingProvider`
  (deterministic, offline) by default; `SentenceTransformerEmbeddingProvider`
  and `OpenAIEmbeddingProvider` behind lazy imports.
- **Provenance tagging**: every node gets a `ProvenanceRecord` linking it to
  its source and transformation chain.

The canonical output is a `MemoryNode` (see `TECHNICAL_SPEC.md`).

## Layer 2 — Persistent Storage

- **`PostgresClient`**: one pooled, pgvector-registered connection manager
  shared by all Postgres-backed stores.
- **`VectorStore`**: node persistence and cosine similarity search via the
  pgvector `<=>` operator, plus full-text (`tsvector`/`ts_rank`) keyword
  search and lifecycle mutators.
- **`GraphStore`**: Neo4j property graph — `MemoryNode`, `Entity`, `MENTIONS`,
  and typed `REL` edges; node→entity→node expansion and entity-path queries.
- **`DocumentStore`**: content-addressable raw document persistence (dedupe by
  hash).
- **`ProvenanceTracker`**: append-only provenance chain.

Indexing strategy and the SQL schema live in `migrations/001_init.sql`.

## Layer 3 — Hybrid Retrieval Orchestrator

The `RetrievalOrchestrator`:

1. embeds the query,
2. runs dense vector similarity search,
3. expands the strongest seeds through the graph (node→entity→node),
4. optionally falls back to keyword search when dense recall is thin,
5. merges candidates (deduping by id, keeping best similarity, tagging
   sources as hybrid),
6. ranks by `priority = 0.5·similarity + 0.3·confidence + 0.2·recency`,
7. trims to a token budget,
8. returns a structured, citation-tagged `InjectionPayload`.

## Layer 4 — Reasoning Engine

Operates on the retrieved working set (and optionally the graph store):

- **Multi-hop traversal**: BFS over the relationship graph from seed entities.
- **Conflict detection**: a `(subject, predicate)` mapping to multiple objects
  is a contradiction, resolved in favour of the highest-confidence object.
- **Confidence-weighted inference**: corroborating triples are combined with
  noisy-OR (`1 − Π(1 − cᵢ)`).

## Layer 5 — Governance & Lifecycle

`MemoryLifecycleManager` provides:

- **TTL decay**: exponential, half-life-based confidence decay toward a floor.
- **Expiry**: prune nodes past TTL whose confidence has fallen below a floor.
- **Reinforcement**: boost confidence (diminishing returns) and extend TTL on
  re-access/corroboration.
- **Consolidation**: merge near-duplicate embeddings into a canonical node,
  unioning entities/relationships, bumping the version, and snapshotting the
  prior state to `node_versions`.
- **Scheduled embedding refresh**: an `EmbeddingRefreshScheduler` abstraction
  selects due nodes (interval- or flag-driven) for re-embedding.
- **Version tracking**: immutable snapshots support audit and rollback.

## Failure & degradation

- Missing graph store → retrieval still works (vector + keyword); graph writes
  are best-effort and logged.
- Missing driver → a clear `RuntimeError` names the package to install; the
  rest of the package keeps importing.
- Graph/provenance write failures during ingestion are logged and never abort
  the vector write (the system of record).
