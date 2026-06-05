"""devtools plugin — developer-reference lookups for Hermes (no API key).

Registers four read-only tools under the ``devtools`` toolset:

  pypi_package          — PyPI package metadata
  npm_package           — npm registry package metadata
  crates_package        — crates.io crate metadata
  stackoverflow_search  — Stack Exchange (Stack Overflow) question search

The single gate is ``devtools.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools until it is flipped on. Hosts are pinned and
responses size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.devtools.tools import TOOL_REGISTRATIONS, check_devtools_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="devtools",
            schema=schema,
            handler=handler,
            check_fn=check_devtools_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("devtools plugin registered %d tools", len(TOOL_REGISTRATIONS))
