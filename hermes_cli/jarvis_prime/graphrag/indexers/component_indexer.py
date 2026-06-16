"""Component indexer — COMPONENT nodes from the M.U.S.E component registry.

Loads ``docs/architecture/muse-component-registry.yaml`` (via
:mod:`hermes_cli.jarvis_prime.component_registry`) and adds one ``COMPONENT``
node per registered component, then attaches:

* an ``OWNS`` edge to the ``FILE`` node of the component's ``owner_module``
  (when the code indexer created it), and
* a ``CITES`` edge to each ``DOCUMENT`` node the component lists in ``docs``
  (when the docs indexer created it).

The registry is resolved **relative to the tree being indexed** so a
``graph build --repo-root X`` over a non-MUSE workspace does not inject this
repo's components into an unrelated graph. Resolution order when no explicit
``registry_path`` is given: the registry inside ``repo_root``, then the
``MUSE_COMPONENT_REGISTRY`` env override; otherwise the indexer is a no-op for
that tree (it never falls back to the packaged copy of a *different* repo).

Like every indexer this is best-effort and source-backed: each node/edge carries
a provenance pointer to the registry file it was actually loaded from. It
*reads* the registry — it never writes back. Runs after the code + docs indexers
so the FILE/DOCUMENT endpoints already exist.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from hermes_cli.jarvis_prime.component_registry import (
    REGISTRY_PATH_ENV,
    load_registry,
)
from hermes_cli.jarvis_prime.graphrag.graph import (
    EdgeType,
    KnowledgeGraph,
    NodeType,
    node_id,
)

logger = logging.getLogger(__name__)

# Registry location relative to a repo root (mirrors component_registry's layout).
_REGISTRY_RELPATH = Path("docs") / "architecture" / "muse-component-registry.yaml"


def _registry_uri(path: Path, root: Path) -> str:
    """Provenance URI for the registry, relative to the tree being indexed so it
    matches how FILE/DOCUMENT nodes record their paths. Absolute when the
    registry lives outside that tree (an explicit path or env override)."""

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _src(registry_uri: str) -> dict:
    return {"uri": registry_uri, "kind": "registry"}


def index_components(
    graph: KnowledgeGraph,
    repo_root,
    *,
    registry_path: Optional[Path] = None,
) -> KnowledgeGraph:
    root = Path(repo_root).resolve()

    # Tie the registry to the tree being indexed (see module docstring). Only an
    # explicit ``registry_path`` or the env override may point outside it; we
    # never reach for the packaged default, which could belong to a different
    # checkout and would skew an unrelated repo's graph.
    if registry_path is None:
        in_tree = root / _REGISTRY_RELPATH
        env = os.environ.get(REGISTRY_PATH_ENV)
        if in_tree.exists():
            registry_path = in_tree
        elif env:
            registry_path = Path(env)
        else:
            return graph

    try:
        components = load_registry(registry_path)
    except Exception as exc:
        # A registry that is present but fails to validate (bad schema header,
        # duplicate ids, unknown owner-gated action) is a real problem — surface
        # it with a warning rather than silently producing zero COMPONENT nodes.
        logger.warning(
            "component registry at %s failed to load: %s", registry_path, exc
        )
        return graph

    src = _src(_registry_uri(Path(registry_path), root))
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
            sources=[src],
        )

        # OWNS edge -> the FILE node of the owner module (if the code indexer
        # created it; directory owner_modules simply have no FILE node).
        file_id = node_id(NodeType.FILE, c.owner_module)
        if file_id in graph.nodes:
            graph.add_edge(comp.id, file_id, EdgeType.OWNS, sources=[src])

        # CITES edge -> each DOCUMENT node the component points at.
        for doc in c.docs:
            doc_id = node_id(NodeType.DOCUMENT, doc)
            if doc_id in graph.nodes:
                graph.add_edge(comp.id, doc_id, EdgeType.CITES, sources=[src])

    return graph
