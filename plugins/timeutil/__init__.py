"""timeutil plugin — time and calendar awareness for Hermes (no API key).

Registers three read-only tools under the ``timeutil`` toolset:

  time_now        — current time in a single IANA timezone
  world_clock     — current time across several timezones at once
  public_holidays — public holidays for a country/year (Nager.Date)

The single gate is ``timeutil.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools until it is flipped on. Hosts are pinned and
responses size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.timeutil.tools import TOOL_REGISTRATIONS, check_timeutil_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="timeutil",
            schema=schema,
            handler=handler,
            check_fn=check_timeutil_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("timeutil plugin registered %d tools", len(TOOL_REGISTRATIONS))
