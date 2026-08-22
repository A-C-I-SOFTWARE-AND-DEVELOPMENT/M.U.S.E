"""``graph_query`` — GraphRAG knowledge-graph retrieval for the agent.

Lets the agent consult the local knowledge graph (typed, source-backed
nodes/edges over repo code, docs, the Research Vault and the Memory Tree)
*before* writing code, so coding tasks reuse existing implementations instead
of duplicating them. It supplements — never replaces — the existing ``memory``
/ ``session_search`` retrieval tools.

The graph is an additive cache under ``$HERMES_HOME/prime/graph/``. This tool
only *reads* that cache — it never builds one, because a build parses every
python file in the tree and takes on the order of a minute on a large
checkout, which is not something an agent tool call may block on. When the
cache is missing the tool says so and names the command that creates it
(``hermes graph build``). Read-only: it never edits the repo, never calls the
network.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_graph_query_requirements() -> bool:
    """Available whenever the GraphRAG runtime imports (stdlib-only)."""
    try:
        import plugins.prime.graphrag  # noqa: F401

        return True
    except Exception:
        return False


def graph_query(question: str = "", mode: str = "coding", limit: int = 8) -> str:
    if not (question or "").strip():
        return "graph_query: provide a 'question'."
    try:
        from plugins.prime.graphrag import (
            GraphStore,
            coding_query,
            global_query,
            local_query,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return f"graph_query: GraphRAG unavailable ({exc})."

    store = GraphStore()
    try:
        graph = store.load()
    except Exception as exc:  # pragma: no cover - defensive
        return f"graph_query: could not read the knowledge graph ({exc})."
    if not graph.nodes:
        return (
            "graph_query: no knowledge graph cached at "
            f"{store.path}. Build it first with `hermes graph build` "
            "(it indexes the repo once; querying is instant afterwards)."
        )

    if mode == "global":
        answer = global_query(graph, question, max_communities=max(1, limit // 2))
    elif mode == "local":
        answer = local_query(graph, question, limit=limit)
    else:
        answer = coding_query(graph, question, limit=limit)
    return answer.render()


GRAPH_QUERY_SCHEMA = {
    "name": "graph_query",
    "description": (
        "Query the local knowledge graph (repo code, docs, stored evidence and "
        "memory) to find existing implementations, tests and notes BEFORE "
        "writing new code — so you reuse what exists instead of duplicating "
        "it. Modes: 'coding' (relevant files + tests + docs; default), "
        "'local' (nearest nodes to the question), 'global' "
        "(cluster/community summary). Results are source-backed. Reads a "
        "cache that `hermes graph build` creates; if none exists the tool "
        "says so instead of building one."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "What you want to find or understand.",
            },
            "mode": {
                "type": "string",
                "enum": ["coding", "local", "global"],
                "description": "Retrieval mode (default 'coding').",
            },
            "limit": {
                "type": "integer",
                "description": "Approximate number of seed nodes (default 8).",
            },
        },
        "required": ["question"],
    },
}


def _handler(args, **_kw) -> str:
    return graph_query(
        question=args.get("question") or "",
        mode=args.get("mode") or "coding",
        limit=int(args.get("limit", 8) or 8),
    )


TOOL_REGISTRATIONS = (
    ("graph_query", GRAPH_QUERY_SCHEMA, _handler, "🕸️", check_graph_query_requirements),
)
