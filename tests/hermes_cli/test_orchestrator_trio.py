"""Tests for hermes_cli.orchestrator_trio — the GLM/LongCat/Grok preset."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hermes_cli.orchestrator_trio import (
    EXTENDED_ROLES,
    FULL_ROSTER,
    TRIO_ROLES,
    install_trio,
    trio_status,
)


@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    """Isolate Path.home() and HERMES_HOME so profiles/config land in tmp_path."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    default_home = tmp_path / ".hermes"
    default_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(default_home))
    return tmp_path


def _profile_dir(tmp_path: Path, name: str) -> Path:
    return tmp_path / ".hermes" / "profiles" / name


def _read_model_block(profile_dir: Path) -> dict:
    data = yaml.safe_load((profile_dir / "config.yaml").read_text(encoding="utf-8"))
    return data["model"]


class TestInstall:
    def test_creates_all_role_profiles_with_models_and_descriptions(self, profile_env):
        summary = install_trio()

        assert sorted(summary["created"]) == sorted(r.profile for r in TRIO_ROLES)
        assert summary["existing"] == []

        for role in TRIO_ROLES:
            pdir = _profile_dir(profile_env, role.profile)
            assert pdir.is_dir()
            model_block = _read_model_block(pdir)
            assert model_block["provider"] == role.provider
            assert model_block["default"] == role.model
            meta = yaml.safe_load((pdir / "profile.yaml").read_text(encoding="utf-8"))
            assert meta["description"].strip()
            assert meta["description_auto"] is False

    def test_wires_kanban_routing(self, profile_env):
        install_trio()

        from hermes_cli.config import load_config

        config = load_config()
        assert config["kanban"]["orchestrator_profile"] == "orchestrator"
        assert config["kanban"]["default_assignee"] == "executor"

    def test_idempotent_second_run(self, profile_env):
        install_trio()
        summary = install_trio()

        assert summary["created"] == []
        assert sorted(summary["existing"]) == sorted(r.profile for r in TRIO_ROLES)
        # Models were already pinned on the first run — nothing rewritten.
        assert summary["models_set"] == []

    def test_status_reflects_install(self, profile_env):
        before = trio_status()
        assert all(not entry["installed"] for entry in before.values())

        install_trio()

        after = trio_status()
        for role in TRIO_ROLES:
            assert after[role.profile]["installed"] is True
            assert after[role.profile]["model"] == role.model

    def test_core_install_leaves_extended_seats_absent(self, profile_env):
        install_trio()

        status = trio_status()
        for role in EXTENDED_ROLES:
            assert status[role.profile]["installed"] is False

    def test_extended_install_creates_full_roster(self, profile_env):
        summary = install_trio(extended=True)

        assert sorted(summary["created"]) == sorted(r.profile for r in FULL_ROSTER)
        for role in EXTENDED_ROLES:
            pdir = _profile_dir(profile_env, role.profile)
            model_block = _read_model_block(pdir)
            assert model_block["provider"] == role.provider
            assert model_block["default"] == role.model
            meta = yaml.safe_load((pdir / "profile.yaml").read_text(encoding="utf-8"))
            assert meta["description"].strip()

    def test_extended_install_is_idempotent(self, profile_env):
        install_trio(extended=True)
        summary = install_trio(extended=True)

        assert summary["created"] == []
        assert sorted(summary["existing"]) == sorted(r.profile for r in FULL_ROSTER)
        assert summary["models_set"] == []


class TestConservativeDefaults:
    """The preset never silently overwrites choices the user already made."""

    def test_preserves_existing_profile_model(self, profile_env):
        from hermes_cli import profiles as profiles_mod

        pdir = profiles_mod.create_profile("executor", no_alias=True)
        (pdir / "config.yaml").write_text(
            yaml.safe_dump({"model": {"provider": "custom", "default": "my/model"}}),
            encoding="utf-8",
        )

        install_trio()

        model_block = _read_model_block(pdir)
        assert model_block == {"provider": "custom", "default": "my/model"}

    def test_force_repins_existing_profile_model(self, profile_env):
        from hermes_cli import profiles as profiles_mod

        pdir = profiles_mod.create_profile("executor", no_alias=True)
        (pdir / "config.yaml").write_text(
            yaml.safe_dump({"model": {"provider": "custom", "default": "my/model"}}),
            encoding="utf-8",
        )

        install_trio(force=True)

        model_block = _read_model_block(pdir)
        assert model_block["provider"] == "openrouter"
        assert model_block["default"] == "meituan/longcat-2.0"

    def test_model_write_preserves_other_config_keys(self, profile_env):
        from hermes_cli import profiles as profiles_mod

        pdir = profiles_mod.create_profile("critic", no_alias=True)
        (pdir / "config.yaml").write_text(
            yaml.safe_dump({"toolsets": ["hermes-cli"], "model": ""}),
            encoding="utf-8",
        )

        install_trio()

        data = yaml.safe_load((pdir / "config.yaml").read_text(encoding="utf-8"))
        assert data["toolsets"] == ["hermes-cli"]
        assert data["model"]["default"] == "x-ai/grok-4.5"

    def test_preserves_existing_kanban_routing(self, profile_env):
        from hermes_cli.config import load_config, save_config

        config = load_config()
        config.setdefault("kanban", {})["orchestrator_profile"] = "my-planner"
        save_config(config)

        summary = install_trio()

        config = load_config()
        assert config["kanban"]["orchestrator_profile"] == "my-planner"
        # default_assignee was unset, so the preset may still wire that one.
        assert config["kanban"]["default_assignee"] == "executor"
        assert "orchestrator_profile" not in summary["kanban"]

    def test_preserves_existing_profile_description(self, profile_env):
        from hermes_cli import profiles as profiles_mod

        profiles_mod.create_profile(
            "orchestrator", no_alias=True, description="my own planner blurb"
        )

        install_trio()

        pdir = _profile_dir(profile_env, "orchestrator")
        meta = profiles_mod.read_profile_meta(pdir)
        assert meta["description"] == "my own planner blurb"


class TestCatalogIntegration:
    def test_roster_models_resolve_in_model_catalog(self):
        """Every roster catalog_ref must exist in config/model-catalog.yaml."""
        from hermes_model_catalog import load_catalog

        catalog = load_catalog()
        for role in FULL_ROSTER:
            entry = catalog.by_ref(role.catalog_ref)
            assert entry is not None, f"{role.catalog_ref} missing from catalog"
            assert entry.model == role.model

    def test_trio_is_registered_as_setup_section(self):
        from hermes_cli.setup import SETUP_SECTIONS

        assert any(key == "trio" for key, _label, _func in SETUP_SECTIONS)
