# Technical Specification

## 1. Core schema — `MemoryNode`

The canonical unit of knowledge. The first nine fields are the mandated
schema; the remainder carry lifecycle/governance state with safe defaults.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | UUID4 (text). |
| `content` | `str` | The chunk text. |
| `embedding` | `List[float]` | Length must equal `EmbeddingConfig.dimension`. |
| `entities` | `List[str]` | Extracted entity surface forms. |
| `relationships` | `List[str]` | `subject\|predicate\|object` triples. |
| `source_id` | `str` | Logical source key. |
| `created_at` | `datetime` | Timezone-aware UTC. |
| `confidence_score` | `float` | In `[0, 1]`. |
| `version` | `int` | Monotonic; bumped on mutation. |
| `updated_at` | `datetime` | DB-maintained via trigger. |
| `last_accessed_at` | `datetime?` | Set on reinforcement/access. |
| `reinforcement_count` | `int` | Number of reinforcements. |
| `ttl_expires_at` | `datetime?` | TTL horizon. |
| `document_id` | `str?` | FK to `documents`. |
| `content_hash` | `str?` | SHA-256 of content. |
| `metadata` | `Dict[str, Any]` | JSONB. |

## 2. SQL schema & indexing strategy

Defined in `migrations/001_init.sql`. Tables: `documents`, `memory_nodes`,
`provenance`, `node_versions`.

Indexes on `memory_nodes`:

- **HNSW** on `embedding` with `vector_cosine_ops` — approximate nearest
  neighbour for vector search. (IVFFlat alternative documented inline for very
  large corpora.)
- **GIN** on `entities` — entity membership lookups.
- **GIN** on `to_tsvector('english', content)` — keyword/full-text fallback.
- **btree** on `source_id`, `document_id`, `ttl_expires_at`, `content_hash`.

A `BEFORE UPDATE` trigger keeps `updated_at` authoritative.

### Vector similarity query

```sql
SELECT id, content, 1 - (embedding <=> %s) AS similarity
FROM memory_nodes
WHERE confidence_score >= %s
  AND (ttl_expires_at IS NULL OR ttl_expires_at > now())
ORDER BY embedding <=> %s
LIMIT %s;
```

### Graph expansion query (Cypher)

```cypher
MATCH (seed:MemoryNode) WHERE seed.id IN $ids
MATCH path = (seed)-[:MENTIONS|REL*1..$depth]-(m:MemoryNode)
WHERE NOT m.id IN $ids
WITH m, min(length(path)) AS dist
RETURN m.id AS id, dist ORDER BY dist ASC LIMIT $limit;
```

Each logical hop is `node → entity → node` (two relationships), so `depth =
hops × 2`. The hop count is validated and clamped (`1..6`) before being
interpolated into the query.

## 3. Configuration

All settings come from environment variables (see `.env.example`) via
`load_settings()`, which returns an immutable `Settings` snapshot composed of
`PostgresConfig`, `Neo4jConfig`, `EmbeddingConfig`, `ChunkingConfig`,
`RetrievalConfig`, and `LifecycleConfig`. No credentials are hardcoded; no
global mutable state is used.

## 4. Layer 1 — ingestion API

```python
IngestionPipeline(
    vector_store, document_store, provenance, embedding_provider, settings,
    graph_store=None, entity_extractor=None, relationship_extractor=None,
    metadata_extractor=None, chunker=None, confidence_engine=None,
)
.ingest(document: Document, *, skip_duplicates=True) -> IngestionResult
.ingest_text(content, source_id, *, title=None, metadata=None) -> IngestionResult
```

Embedding providers implement `EmbeddingProvider` (`dimension`, `embed`,
`embed_one`). The factory `build_embedding_provider(EmbeddingConfig)` selects
`hashing` (default), `sentence-transformers`, or `openai`.

## 5. Layer 3 — retrieval API & ranking

```python
RetrievalOrchestrator(vector_store, *, embedding_provider, settings,
                      graph_store=None, keyword_ranker=None)
.retrieve(query, *, top_k=None, token_budget=None, hops=None,
          use_keyword_fallback=None, min_confidence=0.0) -> InjectionPayload
```

**Ranking formula** (weights configurable, defaults shown):

```
priority_score = (similarity * 0.5) + (confidence * 0.3) + (recency * 0.2)
```

- `similarity` — cosine similarity, mapped to `[0, 1]`.
- `confidence` — the node's `confidence_score`.
- `recency` — `0.5 ** (age_days / recency_half_life_days)`.

Candidates from vector, graph, and keyword sources are merged (deduped by id,
best similarity kept, sources unioned, multi-source tagged `hybrid`), ranked,
then **token-budget trimmed** to produce an `InjectionPayload` whose
`to_prompt()` renders a citation-tagged context string.

`BM25Ranker` provides an in-memory BM25 keyword fallback (k1=1.5, b=0.75) for
offline/no-DB use; with a database, Postgres `ts_rank` full-text search is
preferred.

## 6. Layer 4 — reasoning API

```python
ReasoningEngine(*, settings, graph_store=None)
.reason(nodes, *, seeds=None, max_hops=None) -> ReasoningResult
.multi_hop(edges, seeds, max_hops) -> ReasoningTrace
.detect_conflicts(edges) -> List[Conflict]
.weighted_inference(edges) -> List[Inference]
```

- **Conflict**: a `(subject, predicate)` with ≥2 distinct objects;
  `resolution` is the highest-confidence object.
- **Inference** confidence via noisy-OR: `1 − Π(1 − cᵢ)` over corroborating
  triples.

## 7. Layer 5 — governance API

```python
MemoryLifecycleManager(vector_store, *, settings, confidence_engine=None,
                       graph_store=None, embedding_provider=None, provenance=None)
.decay_confidence() / .expire_stale() / .reinforce(node_id, times=1)
.consolidate(similarity_threshold=None)
.refresh_embeddings(scheduler) / .run_maintenance(refresh=False)
```

Confidence dynamics (`ConfidenceEngine`):

- **initial**: weighted blend of source trust, extraction quality, length
  prior, clamped to `[floor, ceiling]`.
- **decay**: `floor + (c − floor) · 0.5^(age/half_life)`.
- **reinforcement**: `c += (ceiling − c) · boost` (diminishing returns).
- **corroboration**: noisy-OR; **conflict**: multiplicative penalty.

Consolidation merges nodes with cosine similarity ≥ threshold, snapshotting
the canonical node to `node_versions` before the merge.

## 8. Evaluation framework

| Metric | Function | Definition |
|--------|----------|------------|
| Precision@k | `precision_at_k` | relevant ∩ top-k ÷ k |
| Recall@k | `recall_at_k` | relevant ∩ top-k ÷ relevant |
| F1@k | `f1_at_k` | harmonic mean of the above |
| MAP | `average_precision` | area under precision-recall curve |
| Grounding coverage | `grounding_coverage` | fraction of answer claims supported by context |
| Hallucination proxy | `hallucination_score` | `1 − grounding_coverage` + flagging |
| Latency | `LatencyBenchmark.run` | mean/p50/p95/p99 + throughput |

All evaluation functions are pure and infrastructure-free.

## 9. Error handling & logging

- Every module uses `logging.getLogger(__name__)`; the library never
  configures logging on import (`configure_logging()` is opt-in).
- Missing optional dependencies raise actionable `RuntimeError`s naming the
  package to install.
- Best-effort side-channels (graph, provenance) are wrapped so they never
  abort the authoritative vector write.
- Dimension mismatches raise `ValueError` rather than silently mis-ranking.
