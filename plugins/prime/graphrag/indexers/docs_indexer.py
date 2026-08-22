"""Docs indexer — DOCUMENT nodes for markdown, CITES edges to the files they
reference.

Reuses :class:`RepoIndex`'s doc classification (``role == "doc"``) so the walk
and ignore-list are shared with the code indexer. A doc CITES a file when the
file's repo-relative path appears in the doc text — a deterministic, explainable
signal (no embeddings, no guessing).
"""

from __future__ import annotations

import re
from pathlib import Path

from plugins.prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id
from plugins.prime.navigation.repo_index import RepoIndex

# Only treat reasonably specific paths as citations to avoid noise.
_MIN_PATH_LEN = 6
_MAX_CITES_PER_DOC = 40

# A path-like token: at least one ``/`` and a file extension. Matching tokens
# from the doc text (once) and intersecting with the known-paths set is O(text)
# instead of O(text x files).
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]*[A-Za-z0-9_\-]+/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+")


def _src(path: str) -> dict:
    return {"uri": path, "kind": "doc"}


def index_docs(
    graph: KnowledgeGraph, repo_root, *, index: RepoIndex | None = None
) -> KnowledgeGraph:
    root = Path(repo_root).resolve()
    index = index or RepoIndex.build(root)

    known_paths = {
        f.path for f in index.files if len(f.path) >= _MIN_PATH_LEN
    }

    for doc in index.doc_files:
        try:
            text = (root / doc.path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        doc_node = graph.add_node(
            NodeType.DOCUMENT,
            doc.path,
            title=doc.name,
            attrs={"path": doc.path, "lines": doc.lines},
            sources=[_src(doc.path)],
        )
        cited = 0
        seen: set[str] = set()
        for token in _PATH_TOKEN_RE.findall(text):
            fp = token.lstrip("./")
            if fp == doc.path or fp in seen or fp not in known_paths:
                continue
            seen.add(fp)
            file_id = node_id(NodeType.FILE, fp)
            if file_id in graph.nodes:
                if graph.add_edge(
                    doc_node.id, file_id, EdgeType.CITES, sources=[_src(doc.path)]
                ):
                    cited += 1
                    if cited >= _MAX_CITES_PER_DOC:
                        break
    return graph
