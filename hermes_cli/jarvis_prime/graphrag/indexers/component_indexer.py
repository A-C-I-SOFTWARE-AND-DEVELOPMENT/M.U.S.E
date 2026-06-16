"""Component indexer — COMPONENT nodes from the M.U.S.E component registry.

Loads ``docs/architecture/muse-component-registry.yaml`` (via
:mod:`hermes_cli.jarvis_prime.component_registry`) and adds one ``COMPONENT``
node per registered component, then attaches:

* an ``OWNS`` edge to the ``FILE`` node of the component's ``owner_module``
  (when the code indexer created it), and
* a ``CITES`` edge to each ``DOCUMENT`` node the component lists in ``docs``
  (when the docs indexer created it).

Like every indexer this is best-effort and source-backed: each node/edge carries
a provenance pointer to the registry YAML. It *reads* the registry — it never
writes back. Runs after the code + docs indexers so the FILE/DOCUMENT endpoints
already exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from hermes_cli.jarvis_prime.component_registry import (
    DEFAULT_REGISTRY_PATH,
    load_registry,
)
from hermes_cli.jarvis_prime.graphrag.graph import (
    EdgeType,
    KnowledgeGraph,
    NodeType,
    node_id,
)


def _src() -> dict:
    # Repo-relative registry path; falls back to the resolved default.
    try:
        uri = str(DEFAULT_REGISTRY_PATH.relative_to(DEFAULT_REGISTRY_PATH.parents[2]))
    except (ValueError, IndexError):
        uri = "docs/architecture/muse-component-registry.yaml"
    return {"uri": uri, "kind": "registry"}


def index_components(
    graph: KnowledgeGraph,
    repo_root,  # noqa: ARG001 - kept for indexer-signature parity
    *,
    registry_path: Optional[Path] = None,
) -> KnowledgeGraph:
    try:
        components = load_registry(registry_path)
    except Exception:
        # Best-effort: a missing/unreadable registry never aborts a build.
        return graph

    for c in components:
        comp = graph.add_node(
            NodeType.COMPONENT,
            c.id,
            title=c.name,
            attrs={
                "kind": c.kind,
                "risk_class": c.risk_class,
                "owner_module": c.owner_module,
                "owner_gated_actions": list(c.owner_gated_actions),
                "capabilities": list(c.capabilities),
                "is_owner_gated": c.is_owner_gated,
            },
            sources=[_src()],
        )

        # OWNS edge -> the FILE node of the owner module (if the code indexer
        # created it; directory owner_modules simply have no FILE node).
        file_id = node_id(NodeType.FILE, c.owner_module)
        if file_id in graph.nodes:
            graph.add_edge(comp.id, file_id, EdgeType.OWNS, sources=[_src()])

        # CITES edge -> each DOCUMENT node the component points at.
        for doc in c.docs:
            doc_id = node_id(NodeType.DOCUMENT, doc)
            if doc_id in graph.nodes:
                graph.add_edge(comp.id, doc_id, EdgeType.CITES, sources=[_src()])

    return graph
