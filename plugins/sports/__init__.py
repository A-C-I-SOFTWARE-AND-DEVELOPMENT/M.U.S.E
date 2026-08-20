"""sports plugin — free sports scores + standings for Hermes (ESPN public JSON).

Registers two read-only tools under the ``sports`` toolset:

  sports_scores     — league → recent/live/upcoming games
  sports_standings  — league → standings / league table

No API key is required (ESPN's public scoreboard/standings JSON is free). The
single gate is ``sports.enabled`` in ~/.hermes/config.yaml; the ``check_fn``
hides the tools from the model until it is flipped on. Requests are host-pinned
to site.api.espn.com and size-capped by the shared :mod:`tools.http_client`
helper.
"""

from __future__ import annotations

import logging

from plugins.sports.tools import TOOL_REGISTRATIONS, check_sports_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="sports",
            schema=schema,
            handler=handler,
            check_fn=check_sports_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("sports plugin registered %d tools", len(TOOL_REGISTRATIONS))
