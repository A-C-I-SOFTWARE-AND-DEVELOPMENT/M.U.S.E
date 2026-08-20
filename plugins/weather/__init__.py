"""weather plugin — free Open-Meteo weather + geocoding for Hermes.

Registers three read-only tools under the ``weather`` toolset:

  weather_geocode   — place name → coordinates
  weather_current   — current conditions at lat/lon
  weather_forecast  — daily forecast at lat/lon

No API key is required (Open-Meteo is free and unauthenticated). The
single gate is ``weather.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools from the model until it is flipped on.
Requests are host-pinned to *.open-meteo.com and size-capped by the
shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.weather.tools import TOOL_REGISTRATIONS, check_weather_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="weather",
            schema=schema,
            handler=handler,
            check_fn=check_weather_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("weather plugin registered %d tools", len(TOOL_REGISTRATIONS))
