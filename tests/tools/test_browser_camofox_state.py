"""Tests for Hermes-managed Camofox state helpers."""

from unittest.mock import patch


def _load_module():
    from tools import browser_camofox_state as state
    return state


class TestCamofoxStatePaths:
    def test_paths_are_profile_scoped(self, tmp_path):
        state = _load_module()
        with patch.object(state, "get_hermes_home", return_value=tmp_path):
            assert state.get_camofox_state_dir() == tmp_path / "browser_auth" / "camofox"


class TestCamofoxIdentity:
    def test_identity_is_deterministic(self, tmp_path):
        state = _load_module()
        with patch.object(state, "get_hermes_home", return_value=tmp_path):
            first = state.get_camofox_identity("task-1")
            second = state.get_camofox_identity("task-1")
            assert first == second


    def test_default_task_id(self, tmp_path):
        state = _load_module()
        with patch.object(state, "get_hermes_home", return_value=tmp_path):
            identity = state.get_camofox_identity()
            assert "user_id" in identity
            assert "session_key" in identity
            assert identity["user_id"].startswith("hermes_")
            assert identity["session_key"].startswith("task_")


class TestCamofoxConfigDefaults:
    def test_default_config_includes_camofox_controls(self):
        from hermes_cli.config import DEFAULT_CONFIG

        browser_cfg = DEFAULT_CONFIG["browser"]
        assert isinstance(browser_cfg, dict)
        camofox_cfg = browser_cfg["camofox"]
        assert isinstance(camofox_cfg, dict)
        assert camofox_cfg["managed_persistence"] is False
        assert camofox_cfg["user_id"] == ""
        assert camofox_cfg["session_key"] == ""
        assert camofox_cfg["adopt_existing_tab"] is False
