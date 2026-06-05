"""webutils plugin — small web utilities for Hermes (no API key).

Registers four read-only tools under the ``webutils`` toolset:

  qr_code        — build a QR-code image URL (no request)
  ip_info        — IP geolocation (ipapi.co)
  public_ip      — host's public IP (ipify)
  sunrise_sunset — sun times for a lat/lng (SunriseSunset.io)

The single gate is ``webutils.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools until it is flipped on. Hosts are pinned and
responses size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.webutils.tools import TOOL_REGISTRATIONS, check_webutils_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="webutils",
            schema=schema,
            handler=handler,
            check_fn=check_webutils_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("webutils plugin registered %d tools", len(TOOL_REGISTRATIONS))
