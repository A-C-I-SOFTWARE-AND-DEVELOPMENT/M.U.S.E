"""news plugin — headlines for Hermes.

Registers two read-only tools under the ``news`` toolset:

  news_top       — Hacker News top stories (free, no key, always on when
                   the plugin is enabled)
  news_headlines — NewsAPI.org headlines/search; the ``check_fn`` keeps it
                   hidden from the model until NEWSAPI_KEY is configured in
                   ~/.hermes/.env

Each tool carries its own ``check_fn`` and ``requires_env`` so the
key-gated tool only surfaces when usable. Hosts are pinned and the
NewsAPI key is sent as a header and redacted from any error.
"""

from __future__ import annotations

import logging

from plugins.news.tools import TOOL_REGISTRATIONS

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji, check_fn, requires_env in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="news",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            emoji=emoji,
        )
    logger.debug("news plugin registered %d tools", len(TOOL_REGISTRATIONS))
