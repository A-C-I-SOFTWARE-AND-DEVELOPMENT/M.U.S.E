"""recipe plugin — structured, scalable recipe cards for Hermes (pure, offline).

Registers one tool under the ``recipe`` toolset:

  recipe_card  — structured ingredients/steps → validated, id-stamped, serving-scaled card

No network and no API key — ``recipe_card`` is a pure function over the model's
structured input. The single gate is ``recipe.enabled`` in
~/.hermes/config.yaml; the ``check_fn`` hides the tool until it is flipped on.
"""

from __future__ import annotations

import logging

from plugins.recipe.tools import TOOL_REGISTRATIONS, check_recipe_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="recipe",
            schema=schema,
            handler=handler,
            check_fn=check_recipe_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("recipe plugin registered %d tools", len(TOOL_REGISTRATIONS))
