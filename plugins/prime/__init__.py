"""prime plugin — deterministic repo navigation and a local knowledge graph.

Two independent-but-composable substrates, plus the stores they read:

``navigation``
    A repo navigator with no LLM anywhere in the loop: a walk-based
    :class:`~plugins.prime.navigation.repo_index.RepoIndex`, an AST symbol
    graph, a five-signal issue localizer (lexical, path, symbol, test, git
    recency), a dependency/blast-radius tracer, and an edit-site ranker that
    emits a worker packet with the tests to verify against. Pure stdlib.

``graphrag``
    A typed, source-backed knowledge graph over that repo index plus the
    Memory Tree and Research Vault, with three retrieval modes (local, global,
    coding). Backed by a JSON cache that is safe to delete and rebuild.

``memory_tree`` / ``research_vault`` / ``tokenjuice``
    A provenance-carrying, contradiction-aware memory store; an evidence vault
    that summarizes only from stored excerpts; and a deterministic context
    compiler that packs both into a token-bounded prompt packet.

Registers four operator CLI commands and one agent tool::

    hermes navigate {localize,sites,packet,tests,deps,map}
    hermes graph    {build,query,related,stats}
    hermes memory-tree {write,search,outline,context,contradictions,resolve,export}
    hermes research {add,search,list,export}
    graph_query(question, mode, limit)   # agent-facing

Everything is local: no network calls, no model calls, no telemetry.
"""

from __future__ import annotations

import logging

from plugins.prime.cli import (
    graph_command,
    memory_tree_command,
    navigate_command,
    register_graph_cli,
    register_memory_tree_cli,
    register_navigate_cli,
    register_research_cli,
    research_command,
)
from plugins.prime.tools import TOOL_REGISTRATIONS

logger = logging.getLogger(__name__)

_CLI_COMMANDS = (
    (
        "navigate",
        "Deterministic repo navigation — localize an issue, rank edit sites",
        register_navigate_cli,
        navigate_command,
        "Find where an issue lives and where the edit goes, using lexical, "
        "path, symbol, test and git-recency signals over a plain repo walk. "
        "No LLM is used for localization, so results are reproducible.",
    ),
    (
        "graph",
        "Local knowledge graph over code, docs, memory and evidence",
        register_graph_cli,
        graph_command,
        "Build and query a typed, source-backed knowledge graph so coding "
        "work reuses existing implementations. The graph is a cache under "
        "$HERMES_HOME/prime/graph — delete it to roll back completely.",
    ),
    (
        "memory-tree",
        "Provenance-carrying, contradiction-aware memory store",
        register_memory_tree_cli,
        memory_tree_command,
        "Write and retrieve durable memory with sources, confidence and "
        "freshness. Writes are policy-checked (secrets and chain-of-thought "
        "are refused, transient emotion is downgraded) and conflicting "
        "durable facts are flagged rather than silently overwritten.",
    ),
    (
        "research",
        "Evidence vault — cited, strength-graded research artifacts",
        register_research_cli,
        research_command,
        "File and search evidence artifacts. Summaries derive only from the "
        "stored excerpt, so the vault cannot fabricate a claim its source "
        "does not make.",
    ),
)


def register(ctx) -> None:
    for name, help_text, setup_fn, handler_fn, description in _CLI_COMMANDS:
        ctx.register_cli_command(
            name=name,
            help=help_text,
            setup_fn=setup_fn,
            handler_fn=handler_fn,
            description=description,
        )

    for name, schema, handler, emoji, check_fn in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="prime",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            emoji=emoji,
        )

    logger.debug(
        "prime plugin registered %d CLI command(s) and %d tool(s)",
        len(_CLI_COMMANDS),
        len(TOOL_REGISTRATIONS),
    )
