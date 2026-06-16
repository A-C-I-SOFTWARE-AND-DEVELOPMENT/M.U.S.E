"""recommend plugin — registration, gating, and matching behaviour (pure)."""

from __future__ import annotations

import json

import pytest

import plugins.recommend as plugin_pkg
import plugins.recommend.tools as tools
from plugins.recommend import config as recommend_config


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        recommend_config,
        "load_config",
        lambda: recommend_config.RecommendConfig(enabled=True),
    )


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(
        recommend_config,
        "load_config",
        lambda: recommend_config.RecommendConfig(enabled=False),
    )


def test_register_emits_one_tool():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == ["recommend_surfaces"]
    assert captured[0]["toolset"] == "recommend"


def test_check_fn_enabled(enabled):
    assert tools.check_recommend_requirements() is True


def test_check_fn_disabled(disabled):
    assert tools.check_recommend_requirements() is False


def test_blocked_when_disabled(disabled):
    assert _parse(tools.handle_recommend({"use_case": "x"}))["error"] == "plugin_disabled"


def test_requires_use_case(enabled):
    assert _parse(tools.handle_recommend({"use_case": "  "}))["error"] == "bad_args"


def test_matches_phone_to_android(enabled):
    out = _parse(tools.handle_recommend({"use_case": "approve actions from my phone on the lockscreen"}))
    assert out["matched"] is True
    assert out["results"][0]["id"] == "android_app"


def test_matches_voice_use_case(enabled):
    out = _parse(tools.handle_recommend({"use_case": "talk to it hands-free while driving"}))
    assert out["results"][0]["id"] == "voice"


def test_matches_multiword_keyword(enabled):
    out = _parse(tools.handle_recommend({"use_case": "connect it to home assistant"}))
    ids = [r["id"] for r in out["results"]]
    assert "gateway" in ids


def test_no_match_returns_defaults(enabled):
    out = _parse(tools.handle_recommend({"use_case": "zzqq nonsense xyzzy"}))
    assert out["matched"] is False
    assert [r["id"] for r in out["results"]] == ["cockpit", "tui", "orchestration"]


def test_limit_respected(enabled):
    out = _parse(tools.handle_recommend({"use_case": "build a complex parallel project pipeline", "limit": 1}))
    assert out["count"] == 1
