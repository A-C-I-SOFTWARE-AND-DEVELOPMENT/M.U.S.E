"""``graph_query`` tool — GraphRAG knowledge-graph retrieval for the agent.

Lets the agent consult the muse knowledge graph (typed, source-backed
nodes/edges over repo code, docs, Research Vault, Memory Tree, and ledgers)
*before* writing code, so coding tasks reuse existing implementations instead
of duplicating them. It supplements — never replaces — the existing
``memory`` / ``session_search`` retrieval tools.

The graph is an additive cache under ``~/.hermes/jarvis_prime/graph/``; it is
built from the current working directory on first use and reused thereafter.
This tool is read-only: it never edits the repo and never calls the network.
"""

from __future__ import annotations

import logging

from tools.registry import registry

logger = logging.getLogger(__name__)


def check_graph_query_requirements() -> bool:
    """Available whenever the GraphRAG runtime imports (stdlib-only)."""
    try:
        import hermes_cli.jarvis_prime.graphrag  # noqa: F401

        return True
    except Exception:
        return False


def graph_query(question: str = "", mode: str = "coding", limit: int = 8) -> str:
    if not (question or "").strip():
        return "graph_query: provide a 'question'."
    try:
        from hermes_cli.jarvis_prime.graphrag import (
            GraphStore,
            coding_query,
            global_query,
            load_or_build,
            local_query,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return f"graph_query: GraphRAG unavailable ({exc})."

    try:
        graph = load_or_build(".", store=GraphStore())
    except Exception as exc:  # pragma: no cover - defensive
        return f"graph_query: could not build the knowledge graph ({exc})."

    if mode == "global":
        answer = global_query(graph, question)
    elif mode == "local":
        answer = local_query(graph, question)
    else:
        answer = coding_query(graph, question)
    return answer.render()


GRAPH_QUERY_SCHEMA = {
    "name": "graph_query",
    "description": (
        "Query the muse knowledge graph (code, docs, evidence, memory, "
        "decisions) to find existing implementations, tests, and prior "
        "decisions BEFORE writing new code — so you reuse what exists instead "
        "of duplicating it. Modes: 'coding' (relevant files + tests + docs + "
        "prior decisions; default), 'local' (nearest nodes to the question), "
        "'global' (cluster/community summary). Results are source-backed."
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


registry.register(
    name="graph_query",
    toolset="graph_query",
    schema=GRAPH_QUERY_SCHEMA,
    handler=lambda args, **kw: graph_query(
        question=args.get("question") or "",
        mode=args.get("mode") or "coding",
        limit=int(args.get("limit", 8) or 8),
    ),
    check_fn=check_graph_query_requirements,
    emoji="🕸️",
)
