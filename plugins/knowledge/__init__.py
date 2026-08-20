"""knowledge plugin — general-knowledge lookups for Hermes (no API key).

Registers four read-only tools under the ``knowledge`` toolset:

  wikipedia_summary  — lead summary of a Wikipedia article
  wikipedia_search   — search Wikipedia
  dictionary_define  — English word definitions
  country_info       — country facts (REST Countries)

The single gate is ``knowledge.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools until it is flipped on. Hosts are pinned and
responses size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.knowledge.tools import TOOL_REGISTRATIONS, check_knowledge_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="knowledge",
            schema=schema,
            handler=handler,
            check_fn=check_knowledge_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("knowledge plugin registered %d tools", len(TOOL_REGISTRATIONS))
