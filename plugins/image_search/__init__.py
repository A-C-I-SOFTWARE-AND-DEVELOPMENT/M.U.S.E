"""image_search plugin — free, openly-licensed image search for Hermes (Openverse).

Registers one read-only tool under the ``image_search`` toolset:

  image_search  — query → Creative-Commons / public-domain images with attribution

No API key is required (Openverse is free for modest use). The single gate is
``image_search.enabled`` in ~/.hermes/config.yaml; the ``check_fn`` hides the
tool from the model until it is flipped on. Search is host-pinned to
api.openverse.org and size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.image_search.tools import (
    TOOL_REGISTRATIONS,
    check_image_search_requirements,
)

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="image_search",
            schema=schema,
            handler=handler,
            check_fn=check_image_search_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("image_search plugin registered %d tools", len(TOOL_REGISTRATIONS))
