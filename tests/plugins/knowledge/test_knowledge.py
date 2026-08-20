"""knowledge plugin — registration, gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.knowledge as plugin_pkg
import plugins.knowledge.tools as tools
from plugins.knowledge import config as knowledge_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        knowledge_config,
        "load_config",
        lambda: knowledge_config.KnowledgeConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "KnowledgeClient", m)
    return instance


def test_register_emits_four_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "wikipedia_summary",
        "wikipedia_search",
        "dictionary_define",
        "country_info",
    ]
    assert all(c["toolset"] == "knowledge" for c in captured)


def test_disabled_blocks(monkeypatch, mock_client):
    monkeypatch.setattr(
        knowledge_config,
        "load_config",
        lambda: knowledge_config.KnowledgeConfig(enabled=False),
    )
    out = _parse(tools.handle_wikipedia_summary({"title": "Python"}))
    assert out["error"] == "plugin_disabled"
    mock_client.wiki_summary.assert_not_called()


def test_wikipedia_summary_slims(enabled, mock_client):
    mock_client.wiki_summary.return_value = {
        "title": "Python (programming language)",
        "description": "General-purpose language",
        "extract": "Python is a language.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Python"}},
        "thumbnail": {"source": "https://img"},
        "extra": "noise",
    }
    out = _parse(tools.handle_wikipedia_summary({"title": "Python"}))
    assert out["success"] is True
    assert out["url"].endswith("/Python")
    assert "extra" not in out


def test_wikipedia_search_slims(enabled, mock_client):
    mock_client.wiki_search.return_value = {
        "query": {
            "search": [{"title": "Foo", "pageid": 1, "snippet": "s", "wordcount": 9}]
        }
    }
    out = _parse(tools.handle_wikipedia_search({"query": "foo"}))
    assert out["results"][0]["pageid"] == 1


def test_dictionary_define_groups_meanings(enabled, mock_client):
    mock_client.define.return_value = [
        {
            "word": "test",
            "phonetics": [{"text": "/tɛst/"}, {"audio": "x"}],
            "meanings": [
                {
                    "partOfSpeech": "noun",
                    "definitions": [{"definition": "a procedure", "example": "a test"}],
                }
            ],
        }
    ]
    out = _parse(tools.handle_dictionary_define({"word": "test"}))
    assert out["phonetics"] == ["/tɛst/"]
    assert out["meanings"][0]["part_of_speech"] == "noun"


def test_dictionary_define_404_is_not_found(enabled, mock_client):
    mock_client.define.side_effect = HttpClientError("http_error", "nope", status=404)
    out = _parse(tools.handle_dictionary_define({"word": "zzzx"}))
    assert out["error"] == "not_found"


def test_country_info_slims(enabled, mock_client):
    mock_client.country.return_value = [
        {
            "name": {"common": "France", "official": "French Republic"},
            "capital": ["Paris"],
            "region": "Europe",
            "population": 67000000,
            "languages": {"fra": "French"},
            "currencies": {"EUR": {"name": "Euro"}},
            "timezones": ["UTC+01:00"],
            "cca2": "FR",
            "flags": {"png": "https://flag"},
        }
    ]
    out = _parse(tools.handle_country_info({"name": "France"}))
    assert out["country"]["capital"] == ["Paris"]
    assert out["country"]["languages"] == ["French"]
    assert out["country"]["currencies"] == ["EUR"]


def test_bad_args(enabled, mock_client):
    assert _parse(tools.handle_wikipedia_summary({}))["error"] == "bad_args"
    assert _parse(tools.handle_country_info({}))["error"] == "bad_args"
