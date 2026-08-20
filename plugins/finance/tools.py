"""Three agent-facing finance tools (CoinGecko, Frankfurter, Stooq).

Uniform envelope ``{"success": bool, ...}``. The only gate is
``finance.enabled`` — every call is a read-only GET, no API key.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.finance import config as finance_config
from plugins.finance.client import FinanceClient
from tools.http_client import HttpClientError


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json(body)


def _ok(**payload: Any) -> str:
    return _json({"success": True, **payload})


def check_finance_requirements() -> bool:
    return finance_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not finance_config.load_config().enabled:
        return _err("plugin_disabled", "finance.enabled is false")
    return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── schemas ──────────────────────────────────────────────────────────────────

CRYPTO_PRICE_SCHEMA: Dict[str, Any] = {
    "name": "crypto_price",
    "description": (
        "Current cryptocurrency spot prices from CoinGecko (free, no key). "
        "Pass `coins` as tickers or CoinGecko ids (e.g. ['btc','eth'] or "
        "['bitcoin']); `vs_currencies` defaults to ['usd']. Returns price "
        "and 24h % change per coin. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "coins": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Tickers or CoinGecko ids, e.g. ['btc','eth'].",
            },
            "vs_currencies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Quote currencies, e.g. ['usd','eur']. Default ['usd'].",
            },
        },
        "required": ["coins"],
        "additionalProperties": False,
    },
}

CURRENCY_CONVERT_SCHEMA: Dict[str, Any] = {
    "name": "currency_convert",
    "description": (
        "Convert an amount between currencies using European Central Bank "
        "reference rates via Frankfurter (free, no key). Returns the "
        "converted amount and the rate. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "Amount to convert."},
            "from_currency": {"type": "string", "description": "ISO code, e.g. 'USD'."},
            "to_currency": {"type": "string", "description": "ISO code, e.g. 'EUR'."},
        },
        "required": ["amount", "from_currency", "to_currency"],
        "additionalProperties": False,
    },
}

STOCK_QUOTE_SCHEMA: Dict[str, Any] = {
    "name": "stock_quote",
    "description": (
        "Delayed stock/ETF quote from Stooq (free, no key). Pass a ticker; "
        "US symbols default to the '.us' market if no suffix is given "
        "(e.g. 'AAPL' → 'aapl.us', or pass 'aapl.us' / 'vod.uk' explicitly). "
        "Returns OHLC, volume, date/time. Read-only and delayed — not for "
        "real-time trading decisions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker, e.g. 'AAPL'."},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_crypto_price(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    coins = args.get("coins")
    if not isinstance(coins, list) or not coins:
        return _err("bad_args", "coins must be a non-empty list of tickers/ids")
    coins = [c for c in coins if isinstance(c, str) and c.strip()]
    if not coins:
        return _err("bad_args", "coins must contain at least one string")
    vs = args.get("vs_currencies")
    if not isinstance(vs, list) or not vs:
        vs = ["usd"]
    vs = [v.strip().lower() for v in vs if isinstance(v, str) and v.strip()]
    ids = FinanceClient.resolve_coin_ids(coins)
    try:
        payload = FinanceClient().crypto_price(ids, vs)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    if not payload:
        return _err("not_found", f"no prices for {coins!r}")
    return _ok(prices=payload, resolved_ids=ids)


def handle_currency_convert(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    amount = _to_float(args.get("amount"))
    base = args.get("from_currency")
    quote = args.get("to_currency")
    if amount is None:
        return _err("bad_args", "amount must be a number")
    if not isinstance(base, str) or not isinstance(quote, str) or not base or not quote:
        return _err("bad_args", "from_currency and to_currency are required ISO codes")
    try:
        payload = FinanceClient().convert(amount, base, quote)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    rates = payload.get("rates") or {}
    target = quote.upper()
    converted = rates.get(target)
    if converted is None:
        return _err("bad_args", f"unknown currency pair {base!r}->{quote!r}")
    rate = converted / amount if amount else None
    return _ok(
        amount=amount,
        from_currency=base.upper(),
        to_currency=target,
        converted=converted,
        rate=rate,
        date=payload.get("date"),
    )


def handle_stock_quote(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    symbol = args.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        return _err("bad_args", "symbol is required")
    sym = symbol.strip().lower()
    if "." not in sym:
        sym = f"{sym}.us"
    try:
        row = FinanceClient().stock_quote(sym)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    return _ok(
        quote={
            "symbol": row.get("Symbol"),
            "name": row.get("Name"),
            "date": row.get("Date"),
            "time": row.get("Time"),
            "open": _to_float(row.get("Open")),
            "high": _to_float(row.get("High")),
            "low": _to_float(row.get("Low")),
            "close": _to_float(row.get("Close")),
            "volume": _to_float(row.get("Volume")),
        }
    )


TOOL_REGISTRATIONS = (
    ("crypto_price", CRYPTO_PRICE_SCHEMA, handle_crypto_price, "🪙"),
    ("currency_convert", CURRENCY_CONVERT_SCHEMA, handle_currency_convert, "💱"),
    ("stock_quote", STOCK_QUOTE_SCHEMA, handle_stock_quote, "📈"),
)
