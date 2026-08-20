"""sports plugin — registration, gating, and handler behaviour (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.sports as plugin_pkg
import plugins.sports.tools as tools
import plugins.sports.config as sports_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        sports_config, "load_config", lambda: sports_config.SportsConfig(enabled=True)
    )


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(
        sports_config, "load_config", lambda: sports_config.SportsConfig(enabled=False)
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "EspnClient", m)
    return instance


def test_register_emits_two_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == ["sports_scores", "sports_standings"]
    assert all(c["toolset"] == "sports" for c in captured)


def test_check_fn_enabled(enabled):
    assert tools.check_sports_requirements() is True


def test_check_fn_disabled(disabled):
    assert tools.check_sports_requirements() is False


def test_blocked_when_disabled(disabled):
    assert _parse(tools.handle_scores({"league": "nfl"}))["error"] == "plugin_disabled"
    assert _parse(tools.handle_standings({"league": "nfl"}))["error"] == "plugin_disabled"


def test_unknown_league_rejected(enabled):
    out = _parse(tools.handle_scores({"league": "quidditch"}))
    assert out["error"] == "bad_args"


def test_scores_parse_and_team_filter(enabled, mock_client):
    mock_client.scoreboard.return_value = {
        "events": [
            {
                "name": "A vs B",
                "shortName": "A @ B",
                "date": "2026-06-16T00:00Z",
                "status": {"type": {"state": "post", "completed": True, "detail": "Final"}},
                "competitions": [
                    {
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "B Team", "abbreviation": "BBB"}, "score": "3"},
                            {"homeAway": "away", "team": {"displayName": "A Team", "abbreviation": "AAA"}, "score": "1"},
                        ]
                    }
                ],
            },
            {
                "name": "C vs D",
                "competitions": [
                    {
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "D Team", "abbreviation": "DDD"}, "score": "0"},
                            {"homeAway": "away", "team": {"displayName": "C Team", "abbreviation": "CCC"}, "score": "0"},
                        ]
                    }
                ],
                "status": {"type": {"state": "pre"}},
            },
        ]
    }
    out = _parse(tools.handle_scores({"league": "nba"}))
    assert out["count"] == 2
    g0 = out["games"][0]
    assert g0["home"]["team"] == "B Team" and g0["home"]["score"] == "3"
    assert g0["away"]["team"] == "A Team"
    assert g0["state"] == "post" and g0["completed"] is True

    # team filter matches abbreviation, case-insensitive
    filtered = _parse(tools.handle_scores({"league": "nba", "team": "aaa"}))
    assert filtered["count"] == 1
    assert filtered["games"][0]["name"] == "A vs B"
    mock_client.scoreboard.assert_called_with("nba")


def test_standings_parse_groups(enabled, mock_client):
    mock_client.standings.return_value = {
        "children": [
            {
                "name": "Eastern",
                "standings": {
                    "entries": [
                        {
                            "team": {"displayName": "East One"},
                            "stats": [
                                {"name": "wins", "displayValue": "10"},
                                {"name": "losses", "displayValue": "2"},
                            ],
                        }
                    ]
                },
            }
        ]
    }
    out = _parse(tools.handle_standings({"league": "nba"}))
    assert out["count"] == 1
    grp = out["groups"][0]
    assert grp["name"] == "Eastern"
    assert grp["entries"][0]["team"] == "East One"
    assert grp["entries"][0]["stats"]["wins"] == "10"


def test_scores_http_error(enabled, mock_client):
    mock_client.scoreboard.side_effect = HttpClientError("down", "boom", status=500)
    out = _parse(tools.handle_scores({"league": "nfl"}))
    assert out["success"] is False
    assert out["status"] == 500
