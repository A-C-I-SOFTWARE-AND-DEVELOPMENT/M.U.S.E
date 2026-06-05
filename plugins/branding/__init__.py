"""branding plugin — design / branding helpers for Hermes.

Registers five read-only tools under the ``branding`` toolset:

  color_info         — name + conversions for a hex colour (no key)
  color_scheme       — palette generation (no key)
  placeholder_image  — Lorem Picsum URL builder (no key, no request)
  stock_photo_search — Unsplash; hidden until UNSPLASH_ACCESS_KEY is set
  google_fonts       — Google Fonts; hidden until GOOGLE_FONTS_API_KEY is set

Per-tool ``check_fn``/``requires_env`` so each key-gated tool only surfaces
when usable. Hosts are pinned; keys are redacted from errors; image tools
return URLs, never binary blobs.
"""

from __future__ import annotations

import logging

from plugins.branding.tools import TOOL_REGISTRATIONS

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji, check_fn, requires_env in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="branding",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            emoji=emoji,
        )
    logger.debug("branding plugin registered %d tools", len(TOOL_REGISTRATIONS))
