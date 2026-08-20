"""places plugin — free OpenStreetMap places search + map links for Hermes.

Registers two read-only tools under the ``places`` toolset:

  places_search  — name/query → matching places with coordinates (Nominatim)
  places_map     — coordinates → shareable OpenStreetMap map + directions URL

No API key is required (Nominatim is free and unauthenticated). The single gate
is ``places.enabled`` in ~/.hermes/config.yaml; the ``check_fn`` hides the tools
from the model until it is flipped on. Search is host-pinned to
nominatim.openstreetmap.org and size-capped by the shared
:mod:`tools.http_client` helper; ``places_map`` builds URLs locally with no
network call.
"""

from __future__ import annotations

import logging

from plugins.places.tools import TOOL_REGISTRATIONS, check_places_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="places",
            schema=schema,
            handler=handler,
            check_fn=check_places_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("places plugin registered %d tools", len(TOOL_REGISTRATIONS))
