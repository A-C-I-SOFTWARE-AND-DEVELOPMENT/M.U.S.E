"""finance plugin — free market data for Hermes (no API key).

Registers three read-only tools under the ``finance`` toolset:

  crypto_price      — CoinGecko spot prices + 24h change
  currency_convert  — Frankfurter / ECB reference-rate FX conversion
  stock_quote       — Stooq delayed OHLC quote

The single gate is ``finance.enabled`` in ~/.hermes/config.yaml; the
``check_fn`` hides the tools until it is flipped on. Hosts are pinned and
responses size-capped by the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.finance.tools import TOOL_REGISTRATIONS, check_finance_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="finance",
            schema=schema,
            handler=handler,
            check_fn=check_finance_requirements,
            requires_env=[],
            emoji=emoji,
        )
    logger.debug("finance plugin registered %d tools", len(TOOL_REGISTRATIONS))
