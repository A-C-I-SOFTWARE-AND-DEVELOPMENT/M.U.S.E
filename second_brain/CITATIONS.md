# Citations

The Second Brain's design is grounded in published research on
retrieval-augmented generation, hybrid/graph retrieval, knowledge-graph
reasoning, personal knowledge bases, and knowledge-lifecycle governance. The
references below map to the design decisions they inform.

## Retrieval-Augmented Generation

- Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N.,
  Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D.
  (2020). **Retrieval-Augmented Generation for Knowledge-Intensive NLP
  Tasks.** *Advances in Neural Information Processing Systems (NeurIPS) 33.*
  arXiv:2005.11401. — *Foundational RAG pattern: retrieve source passages,
  then condition generation on them. Motivates Layers 1–3 and source-backed
  injection payloads.*
- Karpukhin, V., Oğuz, B., Min, S., Lewis, P., Wu, L., Edunov, S., Chen, D.,
  & Yih, W. (2020). **Dense Passage Retrieval for Open-Domain Question
  Answering.** *EMNLP 2020.* arXiv:2004.04906. — *Dense bi-encoder retrieval;
  basis for the vector-search path and the embedding abstraction.*

## Hybrid RAG (vector + graph / sparse)

- Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A., Truitt, S.,
  & Larson, J. (2024). **From Local to Global: A Graph RAG Approach to
  Query-Focused Summarization.** Microsoft Research. arXiv:2404.16130. —
  *Combines knowledge-graph structure with retrieval; motivates the graph
  expansion stage in Layer 3 and multi-hop reasoning in Layer 4.*
- Robertson, S., & Zaragoza, H. (2009). **The Probabilistic Relevance
  Framework: BM25 and Beyond.** *Foundations and Trends in Information
  Retrieval, 3(4), 333–389.* — *BM25 weighting; basis for `BM25Ranker` and the
  keyword fallback.*
- Cormack, G. V., Clarke, C. L. A., & Büttcher, S. (2009). **Reciprocal Rank
  Fusion Outperforms Condorcet and Individual Rank Learning Methods.**
  *SIGIR 2009.* — *Rank fusion of heterogeneous retrievers; informs the
  candidate-merge strategy (and the Phase-1 RRF roadmap item).*

## Knowledge graph reasoning

- Hogan, A., Blomqvist, E., Cochez, M., et al. (2021). **Knowledge Graphs.**
  *ACM Computing Surveys, 54(4), 1–37.* arXiv:2003.02320. — *Property-graph
  modelling of entities and typed relationships; informs the Neo4j schema.*
- Pearl, J. (1988). **Probabilistic Reasoning in Intelligent Systems:
  Networks of Plausible Inference.** Morgan Kaufmann. — *Noisy-OR
  combination of independent evidence; basis for confidence-weighted
  inference and corroboration aggregation.*
- Ji, S., Pan, S., Cambria, E., Marttinen, P., & Yu, P. S. (2022). **A Survey
  on Knowledge Graphs: Representation, Acquisition, and Applications.** *IEEE
  TNNLS, 33(2), 494–514.* — *Multi-hop reasoning and relation extraction
  framing for Layers 1 and 4.*

## Personal knowledge bases

- Davies, S., Velez-Morales, J., & King, R. (2005). **Building the Memex
  Sixty Years Later: Trends and Directions in Personal Information
  Management.** University of British Columbia, Technical Report. — *PKB /
  personal information management design considerations.*
- Bush, V. (1945). **As We May Think.** *The Atlantic Monthly.* — *The Memex:
  associative, traversable personal memory; conceptual ancestor of a graph
  "second brain".*

## Vector indexing

- Malkov, Y. A., & Yashunin, D. A. (2018). **Efficient and Robust Approximate
  Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs
  (HNSW).** *IEEE TPAMI, 42(4), 824–836.* arXiv:1603.09320. — *ANN index used
  by the pgvector HNSW index in the migration.*
- Johnson, J., Douze, M., & Jégou, H. (2019). **Billion-Scale Similarity
  Search with GPUs.** *IEEE Transactions on Big Data.* arXiv:1702.08734. —
  *Scalable similarity search; informs the IVFFlat scaling guidance.*

## Knowledge lifecycle & evaluation

- Manning, C. D., Raghavan, P., & Schütze, H. (2008). **Introduction to
  Information Retrieval.** Cambridge University Press. — *Precision@k,
  Recall@k, F1, and Average Precision / MAP definitions used by the
  evaluation suite.*
- Es, S., James, J., Espinosa-Anke, L., & Schockaert, S. (2024). **RAGAS:
  Automated Evaluation of Retrieval Augmented Generation.** *EACL 2024
  (Demonstrations).* arXiv:2309.15217. — *Faithfulness / context-grounding
  metrics; motivates the grounding-coverage and hallucination-proxy metrics.*
- Carbonell, J., & Goldstein, J. (1998). **The Use of MMR, Diversity-Based
  Reranking for Reordering Documents and Producing Summaries.** *SIGIR 1998.*
  — *Diversity-aware reranking; Phase-1 roadmap item.*
- Khattab, O., & Zaharia, M. (2020). **ColBERT: Efficient and Effective
  Passage Search via Contextualized Late Interaction over BERT.** *SIGIR
  2020.* arXiv:2004.12832. — *Late-interaction retrieval; Phase-2 roadmap
  item.*

## Implementation references

- **pgvector** — open-source vector similarity search for PostgreSQL.
  <https://github.com/pgvector/pgvector>
- **Neo4j** — graph database and the Cypher query language.
  <https://neo4j.com/docs/>
- **PostgreSQL Full Text Search** — `tsvector` / `ts_rank`.
  <https://www.postgresql.org/docs/current/textsearch.html>
