# Second Brain

A hybrid (vector + graph), governed, research-grounded **AI Second Brain**
module for the Hermes-Agent / JARVIS architecture. It gives an agent a
persistent, inspectable, source-backed long-term memory built on a
five-layer architecture grounded in published retrieval-augmented generation
and knowledge-graph research (see [`CITATIONS.md`](CITATIONS.md)).

> The core (data models, ingestion logic, ranking, reasoning, evaluation) runs
> on the **Python standard library alone** — no database or model download is
> required to import and exercise it. Persistent backends (Postgres + pgvector,
> Neo4j) and richer embedding providers are imported lazily and only needed
> when you turn them on.

---

## The five layers

| Layer | Responsibility | Modules |
|------:|----------------|---------|
| **1. Ingestion & Representation** | Semantic chunking, metadata/entity/relationship extraction, embedding abstraction, provenance tagging | [`knowledge/ingestion.py`](knowledge/ingestion.py), [`knowledge/models.py`](knowledge/models.py) |
| **2. Persistent Storage** | Postgres + pgvector, Neo4j graph, raw documents, provenance | [`knowledge/vector_store.py`](knowledge/vector_store.py), [`knowledge/graph_store.py`](knowledge/graph_store.py), [`knowledge/document_store.py`](knowledge/document_store.py), [`knowledge/provenance.py`](knowledge/provenance.py) |
| **3. Hybrid Retrieval** | Vector search + graph expansion + keyword fallback, ranking, token budgeting | [`knowledge/retrieval_orchestrator.py`](knowledge/retrieval_orchestrator.py) |
| **4. Reasoning** | Multi-hop traversal, conflict detection, confidence-weighted inference | [`knowledge/reasoning_engine.py`](knowledge/reasoning_engine.py) |
| **5. Governance & Lifecycle** | TTL decay, reinforcement, consolidation, scheduled refresh, versioning | [`knowledge/memory_lifecycle.py`](knowledge/memory_lifecycle.py), [`knowledge/confidence.py`](knowledge/confidence.py) |

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the data-flow diagram and
[`TECHNICAL_SPEC.md`](TECHNICAL_SPEC.md) for schemas, formulas, and APIs.

---

## Install

```bash
cd second_brain
python -m pip install -r requirements.txt   # only needed for the DB backends
cp .env.example .env                          # then edit credentials
docker compose up -d                          # Postgres+pgvector and Neo4j
```

The Postgres container applies [`migrations/001_init.sql`](migrations/001_init.sql)
automatically on first start. For an existing database, apply it manually:

```bash
psql "$DATABASE_URL" -f migrations/001_init.sql
```

---

## Quickstart (offline, no infrastructure)

Everything below runs with the deterministic hashing embedding provider and
in-process logic — no Postgres, Neo4j, or network needed.

```python
from knowledge.ingestion import (
    HashingEmbeddingProvider, SemanticChunker,
    RegexEntityExtractor, RelationshipExtractor,
)
from knowledge.models import MemoryNode
from knowledge.reasoning_engine import ReasoningEngine
from knowledge.config import load_settings
from evaluation import grounding_coverage, precision_at_k

emb = HashingEmbeddingProvider(dimension=256)
text = "Ada Lovelace collaborated with Charles Babbage on the Analytical Engine."
entities = RegexEntityExtractor().extract(text)
rels = RelationshipExtractor().extract(text, entities)

node = MemoryNode(
    content=text, embedding=emb.embed_one(text),
    entities=entities, relationships=[r.encode() for r in rels], source_id="bio",
)

result = ReasoningEngine(settings=load_settings()).reason([node])
for inf in result.inferences:
    print(f"{inf.as_text()}  (confidence={inf.confidence})")

print("grounded:", grounding_coverage("Ada worked with Babbage.", [text]).coverage)
```

---

## Quickstart (full stack)

```python
from knowledge import SecondBrain, load_settings

brain = SecondBrain(load_settings(), enable_graph=True)
brain.ensure_graph_schema()

brain.ingest_text(
    "Ada Lovelace collaborated with Charles Babbage on the Analytical Engine. "
    "She is regarded as the first computer programmer.",
    source_id="history/ada",
    metadata={"trust": 0.9, "source_type": "encyclopedia"},
)

payload = brain.retrieve("Who worked with Charles Babbage?")
print(payload.to_prompt())          # ready to inject into a model prompt

reasoning = brain.retrieve_and_reason("Charles Babbage")
report = brain.maintain()           # decay + expire + consolidate
brain.close()
```

---

## Integration with Hermes / JARVIS

The module is intentionally framework-agnostic and dependency-injected, so it
drops into the Hermes plugin/tool layer without pulling the agent's runtime
into the database:

- Wire `SecondBrain.retrieve(...)` behind a `graph_query`-style tool to return
  a citation-tagged `InjectionPayload` for prompt construction.
- Call `SecondBrain.ingest(...)` from the ingestion side of the cognition
  plane (repo code, docs, Research Vault, Memory Tree, ledgers).
- Schedule `SecondBrain.maintain(refresh=...)` from a cron/worker for Layer-5
  governance.

Because retrieval returns provenance-tagged, scored blocks, it *supplements*
(never silently replaces) existing RAG/memory and keeps every answer
source-backed.

---

## Layout

```
second_brain/
├── README.md ARCHITECTURE.md TECHNICAL_SPEC.md ROADMAP.md CITATIONS.md
├── requirements.txt docker-compose.yml .env.example
├── migrations/001_init.sql
├── knowledge/        # the five layers
└── evaluation/       # precision/recall/grounding/latency/hallucination
```

## Evaluation

```python
from evaluation import (
    precision_at_k, recall_at_k, f1_at_k, average_precision,
    grounding_coverage, hallucination_score, LatencyBenchmark,
)
```

See [`evaluation/`](evaluation/) and the metric definitions in
[`TECHNICAL_SPEC.md`](TECHNICAL_SPEC.md#evaluation-framework).

## License

Inherits the repository license (see the repo root `LICENSE`).
