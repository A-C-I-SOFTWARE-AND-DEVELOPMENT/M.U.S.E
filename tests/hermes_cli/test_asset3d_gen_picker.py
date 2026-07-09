"""Tests for plugin asset3d_gen providers in the tools picker.

Mirrors test_video_gen_picker: selecting a plugin-backed 3D provider through
`hermes tools` → 3D Generation must persist `asset3d_gen.provider`, and the
picker must recognize the active provider and surface rows.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from agent import asset3d_gen_registry
from agent.asset3d_gen_provider import Asset3DGenProvider


class _FakeAsset3DProvider(Asset3DGenProvider):
    def __init__(self, name: str, available: bool = True, schema: Optional[Dict[str, Any]] = None):
        self._name = name
        self._available = available
        self._schema = schema or {
            "name": name.title(),
            "badge": "test",
            "tag": f"{name} test tag",
            "env_vars": [{"key": f"{name.upper()}_API_KEY", "prompt": f"{name} key"}],
        }

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def get_setup_schema(self):
        return dict(self._schema)

    def generate(self, prompt: str, **kw: Any) -> Dict[str, Any]:
        return {"success": True, "mesh": f"{self._name}://{prompt}"}


@pytest.fixture(autouse=True)
def _reset_registry():
    asset3d_gen_registry._reset_for_tests()
    yield
    asset3d_gen_registry._reset_for_tests()


class TestPluginAsset3DProvidersRow:
    def test_rows_carry_plugin_marker(self):
        from hermes_cli import tools_config

        asset3d_gen_registry.register_provider(_FakeAsset3DProvider("meshy_fake"))
        rows = tools_config._plugin_asset3d_gen_providers()
        match = next(r for r in rows if r.get("asset3d_gen_plugin_name") == "meshy_fake")
        assert match["name"] == "Meshy_Fake"
        assert "asset3d_gen_plugin_name" in match

    def test_post_setup_propagated(self):
        from hermes_cli import tools_config

        asset3d_gen_registry.register_provider(_FakeAsset3DProvider(
            "oauth3d",
            schema={"name": "OAuth3D", "badge": "paid", "tag": "", "env_vars": [], "post_setup": "some_hook"},
        ))
        rows = tools_config._plugin_asset3d_gen_providers()
        match = next(r for r in rows if r.get("asset3d_gen_plugin_name") == "oauth3d")
        assert match["post_setup"] == "some_hook"


class TestAsset3DProviderActive:
    def test_active_when_provider_matches(self):
        from hermes_cli import tools_config

        config = {"asset3d_gen": {"provider": "meshy"}}
        row = {"name": "Meshy", "asset3d_gen_plugin_name": "meshy"}
        assert tools_config._is_provider_active(row, config) is True

    def test_inactive_when_provider_differs(self):
        from hermes_cli import tools_config

        config = {"asset3d_gen": {"provider": "hunyuan3d"}}
        row = {"name": "Meshy", "asset3d_gen_plugin_name": "meshy"}
        assert tools_config._is_provider_active(row, config) is False

    def test_inactive_when_section_missing(self):
        from hermes_cli import tools_config

        row = {"name": "Meshy", "asset3d_gen_plugin_name": "meshy"}
        assert tools_config._is_provider_active(row, {}) is False


class TestSelectPersistsProvider:
    def test_select_writes_provider(self):
        from hermes_cli import tools_config

        config: dict = {}
        tools_config._select_plugin_asset3d_gen_provider("meshy", config)
        assert config["asset3d_gen"]["provider"] == "meshy"

    def test_category_registered(self):
        from hermes_cli.tools_config import TOOL_CATEGORIES

        assert "asset3d_gen" in TOOL_CATEGORIES
        assert TOOL_CATEGORIES["asset3d_gen"]["name"] == "3D Generation"
