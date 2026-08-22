"""GraphRAG indexers — populate the knowledge graph from existing subsystems.

Each indexer is a pure ``index_*(graph, ...)`` function that *reads* an
authoritative substrate (repo, docs, Research Vault, Memory Tree) and
adds typed, source-backed nodes/edges. None of them write back to their source.
"""

from plugins.prime.graphrag.indexers.code_indexer import index_code
from plugins.prime.graphrag.indexers.docs_indexer import index_docs
from plugins.prime.graphrag.indexers.evidence_indexer import index_evidence
from plugins.prime.graphrag.indexers.memory_indexer import index_memory

__all__ = [
    "index_code",
    "index_docs",
    "index_evidence",
    "index_memory",
]
