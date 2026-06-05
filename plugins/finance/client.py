"""Thin clients for the three free finance data sources.

  * CoinGecko    — crypto spot prices  (api.coingecko.com)
  * Frankfurter  — FX / ECB reference rates  (api.frankfurter.app)
  * Stooq        — delayed stock quotes as CSV  (stooq.com)

All key-less and read-only. Hosts are pinned in :data:`ALLOWED_HOSTS`
and enforced by the shared :class:`~tools.http_client.PublicApiClient`.
Methods raise :class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Optional

from tools.http_client import HttpClientError, PublicApiClient

COINGECKO_HOST = "api.coingecko.com"
FRANKFURTER_HOST = "api.frankfurter.app"
STOOQ_HOST = "stooq.com"
ALLOWED_HOSTS = (COINGECKO_HOST, FRANKFURTER_HOST, STOOQ_HOST)

COINGECKO_PRICE_URL = f"https://{COINGECKO_HOST}/api/v3/simple/price"
FRANKFURTER_LATEST_URL = f"https://{FRANKFURTER_HOST}/latest"
STOOQ_QUOTE_URL = f"https://{STOOQ_HOST}/q/l/"

# Common ticker → CoinGecko id, so the agent can pass "btc" not "bitcoin".
SYMBOL_TO_ID = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "xrp": "ripple",
    "doge": "dogecoin",
    "ltc": "litecoin",
    "bnb": "binancecoin",
    "dot": "polkadot",
    "matic": "matic-network",
    "avax": "avalanche-2",
    "link": "chainlink",
}


class FinanceClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    # -- crypto --------------------------------------------------------------

    @staticmethod
    def resolve_coin_ids(coins: list[str]) -> list[str]:
        out: list[str] = []
        for c in coins:
            key = c.strip().lower()
            out.append(SYMBOL_TO_ID.get(key, key))
        return out

    def crypto_price(self, ids: list[str], vs: list[str]) -> Any:
        return self._http.get_json(
            COINGECKO_PRICE_URL,
            params={
                "ids": ",".join(ids),
                "vs_currencies": ",".join(vs),
                "include_24hr_change": "true",
            },
        )

    # -- FX ------------------------------------------------------------------

    def convert(self, amount: float, base: str, quote: str) -> Any:
        return self._http.get_json(
            FRANKFURTER_LATEST_URL,
            params={"amount": amount, "from": base.upper(), "to": quote.upper()},
        )

    # -- stocks --------------------------------------------------------------

    def stock_quote(self, symbol: str) -> dict[str, Any]:
        """Return a single delayed quote parsed from Stooq's CSV."""
        # f=sd2t2ohlcvn → symbol, date, time, open, high, low, close, volume, name
        text = self._http.get_text(
            STOOQ_QUOTE_URL,
            params={"s": symbol, "f": "sd2t2ohlcvn", "h": "", "e": "csv"},
        )
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            raise HttpClientError("bad_response", "empty quote response")
        row = rows[0]
        # Stooq returns the literal string "N/D" for unknown symbols.
        if (row.get("Close") or "").upper() in {"N/D", ""}:
            raise HttpClientError("not_found", f"no quote for {symbol!r}")
        return row
