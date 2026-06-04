# Roadmap

A phased plan from the shipped baseline to a fully autonomous, self-improving
knowledge substrate. Each phase is independently shippable.

## Phase 0 — Baseline (shipped)

- Five-layer architecture: ingestion, storage, hybrid retrieval, reasoning,
  governance.
- Postgres + pgvector and Neo4j backends; deterministic offline embedding
  provider.
- Priority ranking, token budgeting, multi-hop reasoning, conflict detection.
- Lifecycle: TTL decay, reinforcement, consolidation, scheduled refresh,
  versioning.
- Evaluation suite (precision/recall/grounding/latency/hallucination) and CI.

## Phase 1 — Retrieval quality

- Cross-encoder / LLM re-ranking stage after the priority ranker.
- Maximal-marginal-relevance (MMR) diversification to cut redundancy.
- Learned, query-adaptive fusion weights (replace static 0.5/0.3/0.2).
- Hybrid dense+sparse scoring (reciprocal rank fusion) as a first-class path.

## Phase 2 — Representation depth

- Pluggable ML NER + relation extraction (spaCy / transformer) behind the
  existing `EntityExtractor` / `RelationshipExtractor` interfaces.
- Entity resolution / canonicalisation (alias clustering, coreference).
- Proposition-level chunking and claim extraction for finer grounding.
- Multi-vector / late-interaction (ColBERT-style) embeddings option.

## Phase 3 — Reasoning

- Temporal reasoning (validity intervals, supersession) using existing
  versioning.
- Path-ranked multi-hop explanation with natural-language justifications.
- Abstention / "insufficient evidence" signalling tied to confidence floors.
- Contradiction surfacing into the governance queue for owner review.

## Phase 4 — Governance & autonomy

- Owner-gated write/promotion flow (aligns with JARVIS verification gates):
  propose-then-approve for contested or high-impact updates.
- Active forgetting policies (privacy/sensitivity-aware TTLs).
- Drift detection on embedding-model upgrades with staged re-embedding.
- Provenance-driven trust propagation across the graph.

## Phase 5 — Scale & operations

- Sharding / partitioning strategy for `memory_nodes`; IVFFlat tuning guidance.
- Incremental, online consolidation (replace the batch O(n²) window with
  ANN-bucketed candidate generation).
- Streaming ingestion connectors (repo code, docs, Research Vault, Memory
  Tree, ledgers).
- Observability: per-stage latency/recall dashboards and golden-set
  regression gates wired into CI.

## Phase 6 — Evaluation & research

- Held-out benchmark wall with labelled relevance judgements.
- Faithfulness evaluation with a stronger verifier model (beyond the
  reference-free proxy).
- Continuous A/B of retrieval configurations against the benchmark wall.
