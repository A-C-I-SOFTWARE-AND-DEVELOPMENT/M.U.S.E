"""learning plugin — registration, key gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.learning as plugin_pkg
import plugins.learning.tools as tools
from plugins.learning import config as learning_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        learning_config,
        "load_config",
        lambda: learning_config.LearningConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "LearningClient", m)
    return instance


def test_register_emits_four_tools_with_wolfram_gated():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    by_name = {c["name"]: c for c in captured}
    assert set(by_name) == {
        "books_search",
        "gutenberg_search",
        "quote_random",
        "wolfram_answer",
    }
    assert by_name["wolfram_answer"]["requires_env"] == ["WOLFRAM_APP_ID"]
    assert by_name["books_search"]["requires_env"] == []
    assert (
        by_name["wolfram_answer"]["check_fn"] is not by_name["books_search"]["check_fn"]
    )


def test_wolfram_hidden_without_key(enabled, monkeypatch):
    monkeypatch.delenv("WOLFRAM_APP_ID", raising=False)
    assert tools.check_learning_enabled() is True
    assert tools.check_wolfram_ready() is False


def test_wolfram_visible_with_key(enabled, monkeypatch):
    monkeypatch.setenv("WOLFRAM_APP_ID", "ABCDEF-1234567890")
    assert tools.check_wolfram_ready() is True


def test_wolfram_refuses_without_key(enabled, monkeypatch):
    monkeypatch.delenv("WOLFRAM_APP_ID", raising=False)
    out = _parse(tools.handle_wolfram_answer({"query": "2+2"}))
    assert out["error"] == "no_key"


def test_books_search_slims(enabled, mock_client):
    mock_client.books.return_value = {
        "numFound": 2,
        "docs": [
            {
                "title": "Dune",
                "author_name": ["Frank Herbert"],
                "first_publish_year": 1965,
                "edition_count": 50,
                "key": "/works/OL1W",
            }
        ],
    }
    out = _parse(tools.handle_books_search({"query": "dune", "limit": 1}))
    assert out["books"][0]["authors"] == ["Frank Herbert"]
    assert out["total"] == 2


def test_gutenberg_extracts_formats(enabled, mock_client):
    mock_client.gutenberg.return_value = {
        "count": 1,
        "results": [
            {
                "id": 1342,
                "title": "Pride and Prejudice",
                "authors": [{"name": "Austen, Jane"}],
                "download_count": 99999,
                "formats": {
                    "text/plain; charset=utf-8": "https://gutenberg/1342.txt",
                    "text/html": "https://gutenberg/1342.html",
                },
            }
        ],
    }
    out = _parse(tools.handle_gutenberg_search({"query": "pride"}))
    assert out["books"][0]["text_url"].endswith(".txt")
    assert out["books"][0]["authors"] == ["Austen, Jane"]


def test_quote_random_extracts_qa(enabled, mock_client):
    mock_client.quote.return_value = [{"q": "Be water.", "a": "Bruce Lee"}]
    out = _parse(tools.handle_quote_random({}))
    assert out["quote"] == "Be water."
    assert out["author"] == "Bruce Lee"


def test_wolfram_answer_returns_text(enabled, monkeypatch):
    monkeypatch.setenv("WOLFRAM_APP_ID", "KEY-123456")
    fake = MagicMock()
    fake.has_key.return_value = True
    fake.short_answer.return_value = "4"
    monkeypatch.setattr(tools, "WolframClient", lambda: fake)
    out = _parse(tools.handle_wolfram_answer({"query": "2+2"}))
    assert out["answer"] == "4"


def test_wolfram_501_is_not_found(enabled, monkeypatch):
    monkeypatch.setenv("WOLFRAM_APP_ID", "KEY-123456")
    fake = MagicMock()
    fake.has_key.return_value = True
    fake.short_answer.side_effect = HttpClientError("http_error", "no", status=501)
    monkeypatch.setattr(tools, "WolframClient", lambda: fake)
    out = _parse(tools.handle_wolfram_answer({"query": "asdf"}))
    assert out["error"] == "not_found"
