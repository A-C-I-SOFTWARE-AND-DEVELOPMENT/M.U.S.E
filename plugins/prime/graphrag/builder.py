"""Graph builder — assemble the knowledge graph from the selected indexers.

The builder is the one place that knows the *order* indexers should run in
(code first, so docs/evidence/memory can attach CITES/DEPENDS_ON edges onto
existing FILE nodes). Every indexer is best-effort: one failing source never
aborts the build. The result is an additive cache, safe to delete and rebuild.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from plugins.prime.graphrag.graph import KnowledgeGraph
from plugins.prime.graphrag.indexers import (
    index_code,
    index_docs,
    index_evidence,
    index_memory,
)
from plugins.prime.graphrag.store import GraphStore
from plugins.prime.navigation.repo_index import RepoIndex

logger = logging.getLogger(__name__)

# Run order matters: code/docs create the FILE/DOCUMENT nodes that the later
# indexers attach their CITES/SUPERSEDES/CONTRADICTS edges onto.
ALL_INDEXERS: tuple[str, ...] = (
    "code",
    "docs",
    "evidence",
    "memory",
)


def build_graph(
    repo_root,
    *,
    indexers: Optional[Iterable[str]] = None,
    graph: Optional[KnowledgeGraph] = None,
) -> KnowledgeGraph:
    """Build (or extend) a :class:`KnowledgeGraph` for ``repo_root``.

    ``indexers`` selects which sources to include (default: all). Unknown
    names are ignored. Returns the populated graph (not persisted — call
    :func:`build_and_save` or use :class:`GraphStore` to persist).
    """

    root = Path(repo_root).resolve()
    graph = graph or KnowledgeGraph()
    selected = list(indexers) if indexers is not None else list(ALL_INDEXERS)

    # Share one RepoIndex across the code + docs indexers (one walk, not two).
    shared_index: Optional[RepoIndex] = None
    if "code" in selected or "docs" in selected:
        try:
            shared_index = RepoIndex.build(root)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("repo index failed: %s", exc)

    steps = {
        "code": lambda: index_code(graph, root, index=shared_index),
        "docs": lambda: index_docs(graph, root, index=shared_index),
        "evidence": lambda: index_evidence(graph),
        "memory": lambda: index_memory(graph),
    }
    for name in ALL_INDEXERS:  # deterministic order regardless of input order
        if name in selected and name in steps:
            try:
                steps[name]()
            except Exception as exc:  # best-effort: one source never aborts build
                logger.warning("graphrag indexer %s failed: %s", name, exc)
    return graph


def build_and_save(
    repo_root,
    *,
    indexers: Optional[Iterable[str]] = None,
    store: Optional[GraphStore] = None,
) -> tuple[KnowledgeGraph, Path]:
    """Build the graph and persist it via :class:`GraphStore`. Returns
    ``(graph, path)``.
    """

    graph = build_graph(repo_root, indexers=indexers)
    store = store or GraphStore()
    path = store.save(graph)
    return graph, path


def load_or_build(
    repo_root, *, store: Optional[GraphStore] = None
) -> KnowledgeGraph:
    """Load the cached graph, building + saving it on first use."""

    store = store or GraphStore()
    if store.exists():
        graph = store.load()
        if graph.nodes:
            return graph
    graph, _ = build_and_save(repo_root, store=store)
    return graph
