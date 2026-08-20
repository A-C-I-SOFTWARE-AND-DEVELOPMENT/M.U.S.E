"""cooking plugin — recipes and food data for Hermes (no API key).

Registers four read-only tools under the ``cooking`` toolset:

  recipe_search    — search recipes by name (TheMealDB)
  recipe_lookup    — full recipe by id (TheMealDB)
  cocktail_search  — search cocktails (TheCocktailDB)
  food_product     — packaged-food lookup by barcode (Open Food Facts)

The single gate is ``cooking.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools until it is flipped on. Hosts are pinned and
responses size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.cooking.tools import TOOL_REGISTRATIONS, check_cooking_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="cooking",
            schema=schema,
            handler=handler,
            check_fn=check_cooking_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("cooking plugin registered %d tools", len(TOOL_REGISTRATIONS))
