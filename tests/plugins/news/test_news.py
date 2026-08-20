"""news plugin — registration, per-tool gating, handlers, redaction (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.news as plugin_pkg
import plugins.news.client as news_client
import plugins.news.tools as tools
from plugins.news import config as news_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        news_config, "load_config", lambda: news_config.NewsConfig(enabled=True)
    )


# ── registration ─────────────────────────────────────────────────────────────


def test_register_emits_two_tools_with_distinct_gates():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    names = [c["name"] for c in captured]
    assert names == ["news_top", "news_headlines"]
    by_name = {c["name"]: c for c in captured}
    assert by_name["news_top"]["requires_env"] == []
    assert by_name["news_headlines"]["requires_env"] == ["NEWSAPI_KEY"]
    # The two tools must NOT share a check_fn.
    assert by_name["news_top"]["check_fn"] is not by_name["news_headlines"]["check_fn"]


# ── per-tool gating ──────────────────────────────────────────────────────────


def test_newsapi_tool_hidden_without_key(enabled, monkeypatch):
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    assert tools.check_news_enabled() is True
    assert tools.check_newsapi_ready() is False


def test_newsapi_tool_visible_with_key(enabled, monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "test-key-123456")
    assert tools.check_newsapi_ready() is True


def test_headlines_refuses_when_no_key(enabled, monkeypatch):
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    out = _parse(tools.handle_news_headlines({"query": "ai"}))
    assert out["error"] == "no_key"


# ── hacker news happy path ───────────────────────────────────────────────────


def test_news_top_fetches_and_slims(enabled, monkeypatch):
    fake = MagicMock()
    fake.top_story_ids.return_value = [101, 102]
    fake.item.side_effect = [
        {
            "id": 101,
            "title": "A",
            "url": "http://a",
            "score": 5,
            "by": "u",
            "descendants": 3,
        },
        {"id": 102, "title": "B", "score": 9, "by": "v", "descendants": 1},
    ]
    monkeypatch.setattr(tools, "HackerNewsClient", lambda: fake)
    out = _parse(tools.handle_news_top({"limit": 2}))
    assert out["success"] is True
    assert out["source"] == "hacker_news"
    assert out["stories"][0]["title"] == "A"
    # item 102 has no url → fall back to the HN permalink.
    assert out["stories"][1]["url"] == "https://news.ycombinator.com/item?id=102"


# ── newsapi happy path + redaction ───────────────────────────────────────────


def test_headlines_slims_articles(enabled, monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "secret-key-ABCDEF")
    fake = MagicMock()
    fake.has_key.return_value = True
    fake.top_headlines.return_value = {
        "totalResults": 1,
        "articles": [
            {
                "title": "Headline",
                "source": {"name": "Wire"},
                "author": "Jo",
                "url": "http://x",
                "publishedAt": "2026-06-05T00:00:00Z",
                "description": "desc",
                "content": "ignored heavy field",
            }
        ],
    }
    monkeypatch.setattr(tools, "NewsApiClient", lambda: fake)
    out = _parse(tools.handle_news_headlines({"country": "us"}))
    assert out["success"] is True
    assert out["articles"][0]["source"] == "Wire"
    assert "content" not in out["articles"][0]


def test_newsapi_client_redacts_key_in_errors(monkeypatch):
    key = "newsapi-LEAK-9999"
    monkeypatch.setenv("NEWSAPI_KEY", key)
    http = MagicMock()
    http.get_json.side_effect = HttpClientError(
        "http_error", "rejected ***REDACTED***", status=401
    )
    client = news_client.NewsApiClient(http=http)
    assert client.has_key() is True
    # The header carries the key, but it must not appear in the surfaced error.
    with pytest.raises(HttpClientError) as exc:
        client.top_headlines(country="us", category=None, page_size=5)
    assert key not in str(exc.value)
