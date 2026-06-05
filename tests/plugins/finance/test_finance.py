"""finance plugin — registration, gating, handlers, CSV parsing (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.finance as plugin_pkg
import plugins.finance.tools as tools
from plugins.finance import config as finance_config
from plugins.finance.client import FinanceClient
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        finance_config,
        "load_config",
        lambda: finance_config.FinanceConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    # resolve_coin_ids is a staticmethod used via the class, keep it real.
    m.resolve_coin_ids = FinanceClient.resolve_coin_ids
    monkeypatch.setattr(tools, "FinanceClient", m)
    return instance


# ── registration ─────────────────────────────────────────────────────────────


def test_register_emits_three_finance_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "crypto_price",
        "currency_convert",
        "stock_quote",
    ]
    assert all(c["toolset"] == "finance" for c in captured)


# ── gating ───────────────────────────────────────────────────────────────────


def test_disabled_blocks_calls(monkeypatch, mock_client):
    monkeypatch.setattr(
        finance_config,
        "load_config",
        lambda: finance_config.FinanceConfig(enabled=False),
    )
    out = _parse(tools.handle_crypto_price({"coins": ["btc"]}))
    assert out["error"] == "plugin_disabled"
    mock_client.crypto_price.assert_not_called()


# ── crypto ───────────────────────────────────────────────────────────────────


def test_crypto_resolves_ticker_to_id(enabled, mock_client):
    mock_client.crypto_price.return_value = {
        "bitcoin": {"usd": 65000, "usd_24h_change": 1.5}
    }
    out = _parse(tools.handle_crypto_price({"coins": ["btc"]}))
    assert out["success"] is True
    assert out["resolved_ids"] == ["bitcoin"]
    # client was called with the resolved id and default vs=usd.
    args, kwargs = mock_client.crypto_price.call_args
    assert args[0] == ["bitcoin"]
    assert args[1] == ["usd"]


def test_crypto_rejects_empty_coins(enabled, mock_client):
    out = _parse(tools.handle_crypto_price({"coins": []}))
    assert out["error"] == "bad_args"


# ── FX ───────────────────────────────────────────────────────────────────────


def test_currency_convert_computes_rate(enabled, mock_client):
    mock_client.convert.return_value = {"date": "2026-06-05", "rates": {"EUR": 92.0}}
    out = _parse(
        tools.handle_currency_convert({
            "amount": 100,
            "from_currency": "usd",
            "to_currency": "eur",
        })
    )
    assert out["success"] is True
    assert out["converted"] == 92.0
    assert out["rate"] == pytest.approx(0.92)
    assert out["to_currency"] == "EUR"


def test_currency_convert_unknown_pair(enabled, mock_client):
    mock_client.convert.return_value = {"date": "2026-06-05", "rates": {}}
    out = _parse(
        tools.handle_currency_convert({
            "amount": 100,
            "from_currency": "usd",
            "to_currency": "zzz",
        })
    )
    assert out["error"] == "bad_args"


# ── stocks ───────────────────────────────────────────────────────────────────


def test_stock_quote_defaults_us_market(enabled, mock_client):
    mock_client.stock_quote.return_value = {
        "Symbol": "AAPL.US",
        "Name": "APPLE",
        "Date": "2026-06-05",
        "Time": "22:00:00",
        "Open": "200.0",
        "High": "205.0",
        "Low": "199.0",
        "Close": "204.5",
        "Volume": "50000000",
    }
    out = _parse(tools.handle_stock_quote({"symbol": "AAPL"}))
    assert out["success"] is True
    assert out["quote"]["close"] == 204.5
    # the handler appended .us before calling the client.
    assert mock_client.stock_quote.call_args.args[0] == "aapl.us"


def test_stock_quote_propagates_not_found(enabled, mock_client):
    mock_client.stock_quote.side_effect = HttpClientError(
        "not_found", "no quote for 'zzzz.us'"
    )
    out = _parse(tools.handle_stock_quote({"symbol": "zzzz"}))
    assert out["error"] == "not_found"


# ── CSV parsing in the real client (with a stub PublicApiClient) ─────────────


def test_client_parses_stooq_csv():
    csv_text = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume,Name\n"
        "AAPL.US,2026-06-05,22:00:00,200.0,205.0,199.0,204.5,50000000,APPLE\n"
    )
    http = MagicMock()
    http.get_text.return_value = csv_text
    row = FinanceClient(http=http).stock_quote("aapl.us")
    assert row["Close"] == "204.5"
    assert row["Name"] == "APPLE"


def test_client_raises_not_found_on_nd():
    csv_text = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume,Name\n"
        "ZZZZ.US,N/D,N/D,N/D,N/D,N/D,N/D,N/D,ZZZZ\n"
    )
    http = MagicMock()
    http.get_text.return_value = csv_text
    with pytest.raises(HttpClientError) as exc:
        FinanceClient(http=http).stock_quote("zzzz.us")
    assert exc.value.error == "not_found"
