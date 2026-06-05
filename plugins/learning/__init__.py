"""learning plugin — learning aids for Hermes.

Registers four read-only tools under the ``learning`` toolset:

  books_search      — Open Library book search (no key)
  gutenberg_search  — Project Gutenberg free ebooks (no key)
  quote_random      — random quote (no key)
  wolfram_answer    — Wolfram|Alpha short answer; its ``check_fn`` keeps it
                      hidden until WOLFRAM_APP_ID is set in ~/.hermes/.env

Per-tool ``check_fn``/``requires_env`` so the key-gated tool only surfaces
when usable. Hosts are pinned and the Wolfram app id is redacted from errors.
"""

from __future__ import annotations

import logging

from plugins.learning.tools import TOOL_REGISTRATIONS

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji, check_fn, requires_env in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="learning",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            emoji=emoji,
        )
    logger.debug("learning plugin registered %d tools", len(TOOL_REGISTRATIONS))
