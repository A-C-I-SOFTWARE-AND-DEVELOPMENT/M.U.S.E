"""recommend plugin — recommend the right MUSE surface for a task (pure, offline).

Registers one tool under the ``recommend`` toolset:

  recommend_surfaces  — use-case → most relevant MUSE surfaces (why + how to reach)

No network and no API key. The single gate is ``recommend.enabled`` in
~/.hermes/config.yaml; the ``check_fn`` hides the tool until it is flipped on.
"""

from __future__ import annotations

import logging

from plugins.recommend.tools import TOOL_REGISTRATIONS, check_recommend_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="recommend",
            schema=schema,
            handler=handler,
            check_fn=check_recommend_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("recommend plugin registered %d tools", len(TOOL_REGISTRATIONS))
