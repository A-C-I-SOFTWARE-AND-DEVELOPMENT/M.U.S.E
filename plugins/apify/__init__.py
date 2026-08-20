"""apify plugin — Apify web-scraping & automation for Hermes

Registers four tools under the ``apify`` toolset:

  read   — apify_list_actors, apify_get_dataset_items, apify_get_run
  run    — apify_run_actor  (starts a billable Actor run)

Three independently-toggled safety gates (mirroring github_assistant):

  * ``apify.enabled``        — the master switch (default False)
  * ``apify.allow_runs``     — apify_run_actor stays hidden + refuses
                               without it (default False), because a run
                               consumes paid Apify compute units
  * ``apify.allowed_actors`` — when non-empty, only listed Actor ids/slugs
                               may be run

The token lives in ``APIFY_TOKEN`` (env or ``~/.hermes/.env``); it is sent
as a Bearer header, never returned to the model, never echoed in tool
output, and never logged in plain text.

This is the *native plugin* path. If you'd rather use Apify's official MCP
server, wire it up under ``mcp_servers.apify`` in ``~/.hermes/config.yaml``
— the two paths coexist cleanly. See docs/integrations/apify-plugin.md.
"""

from __future__ import annotations

import logging

from plugins.apify.tools import TOOL_REGISTRATIONS

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register every tool under the apify toolset.

    We register unconditionally so ``hermes tools list`` still surfaces the
    tools when the plugin is disabled. Each tool's ``check_fn`` guards
    actual visibility to the model — read tools hide until apify.enabled +
    APIFY_TOKEN; apify_run_actor additionally hides until apify.allow_runs.
    """
    for name, schema, handler, emoji, check_fn, requires_env in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="apify",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            emoji=emoji,
        )
    logger.debug("apify plugin registered %d tools", len(TOOL_REGISTRATIONS))
