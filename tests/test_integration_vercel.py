"""Tests for the Vercel integration adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from muse_cli.integrations import vercel as vc


class TestDetect:
    def test_detect_returns_detection(self, tmp_path: Path) -> None:
        det = vc.detect(project_root=tmp_path)
        assert isinstance(det, vc.Detection)
        assert isinstance(det.cli_present, bool)
        assert det.project_root == tmp_path.resolve()
        assert det.has_vercel_json is False
        assert det.has_dot_vercel is False

    def test_detect_finds_vercel_json(self, tmp_path: Path) -> None:
        (tmp_path / "vercel.json").write_text("{}", encoding="utf-8")
        det = vc.detect(project_root=tmp_path)
        assert det.has_vercel_json is True

    def test_detect_finds_dot_vercel(self, tmp_path: Path) -> None:
        (tmp_path / ".vercel").mkdir()
        (tmp_path / ".vercel" / "project.json").write_text("{}", encoding="utf-8")
        det = vc.detect(project_root=tmp_path)
        assert det.has_dot_vercel is True

    def test_detect_notes_when_cli_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(vc.shutil, "which", lambda name: None)
        det = vc.detect(project_root=tmp_path)
        assert det.cli_present is False
        assert any("vercel" in n.lower() for n in det.notes)

    def test_detect_makes_no_network_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import socket

        def _no(*a, **kw):  # noqa: ANN001, ANN002, ANN003
            raise AssertionError("detect() must not open sockets")

        monkeypatch.setattr(socket, "socket", _no)
        vc.detect(project_root=tmp_path)


class TestEnvVarSpec:
    def test_valid_env_var(self) -> None:
        ev = vc.EnvVarSpec("DATABASE_URL")
        assert ev.name == "DATABASE_URL"
        assert "preview" in ev.targets
        assert ev.secret is True

    def test_invalid_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            vc.EnvVarSpec("not a valid env var")
        with pytest.raises(ValueError):
            vc.EnvVarSpec("")
        with pytest.raises(ValueError):
            vc.EnvVarSpec("123-NO-LEADING-DIGIT")  # not a valid identifier

    def test_invalid_target_rejected(self) -> None:
        with pytest.raises(ValueError):
            vc.EnvVarSpec("X", targets=("preview", "staging"))


class TestPlan:
    def test_plan_defaults_to_preview(self) -> None:
        p = vc.plan(project_name="hermes-web")
        assert p.target == "preview"
        assert p.requires_double_approval is False
        assert p.approval_required is True
        assert p.dry_run is True

    def test_plan_production_requires_double_approval(self) -> None:
        p = vc.plan(project_name="hermes-web", target="production")
        assert p.target == "production"
        assert p.requires_double_approval is True

    def test_plan_validates_project_name(self) -> None:
        with pytest.raises(ValueError):
            vc.plan(project_name="Has Spaces")
        with pytest.raises(ValueError):
            vc.plan(project_name="")
        with pytest.raises(ValueError):
            vc.plan(project_name="-leading-dash")

    def test_plan_lowercases_project_name(self) -> None:
        p = vc.plan(project_name="MyApp")
        assert p.project_name == "myapp"

    def test_plan_rejects_unknown_target(self) -> None:
        with pytest.raises(ValueError):
            vc.plan(project_name="hermes-web", target="staging")

    def test_plan_deploy_command_is_argv_list(self) -> None:
        p = vc.plan(project_name="hermes-web", target="preview")
        assert isinstance(p.deploy_command, list)
        assert p.deploy_command[0:2] == ["vercel", "deploy"]
        assert "--prod" not in p.deploy_command

    def test_plan_production_argv_has_prod_flag(self) -> None:
        p = vc.plan(project_name="hermes-web", target="production")
        assert "--prod" in p.deploy_command

    def test_plan_env_vars_attached(self) -> None:
        evs = [
            vc.EnvVarSpec("PUBLIC_URL", secret=False),
            vc.EnvVarSpec("SECRET_KEY"),
        ]
        p = vc.plan(project_name="hermes-web", env_vars=evs)
        assert p.env_vars == evs

    def test_plan_emits_rollback_and_validation(self) -> None:
        p = vc.plan(project_name="hermes-web")
        assert p.rollback_notes
        assert p.validation_steps
        # Rollback must mention promotion (never deletion).
        joined = " ".join(p.rollback_notes).lower()
        assert "promote" in joined or "rollback" in joined
        assert "never delete" in joined

    def test_plan_emits_env_policy(self) -> None:
        p = vc.plan(project_name="hermes-web")
        assert p.env_policy
        joined = " ".join(p.env_policy).lower()
        assert "name" in joined
        assert "value" in joined


class TestExplain:
    def test_explain_is_markdown(self) -> None:
        p = vc.plan(project_name="hermes-web")
        rendered = vc.explain(p)
        assert isinstance(rendered, str)
        assert rendered.startswith("### Vercel deploy plan")
        assert "Approval required" in rendered
        assert "Rollback" in rendered
        assert "Validation" in rendered

    def test_explain_warns_on_production(self) -> None:
        p = vc.plan(project_name="hermes-web", target="production")
        rendered = vc.explain(p)
        # Production must be visibly highlighted.
        assert "PRODUCTION" in rendered
        assert "Double approval" in rendered

    def test_explain_lists_env_var_names_only(self) -> None:
        ev = vc.EnvVarSpec("SECRET_KEY", description="API key for service X")
        p = vc.plan(project_name="hermes-web", env_vars=[ev])
        rendered = vc.explain(p)
        assert "SECRET_KEY" in rendered
        # Description ok; value never appears (we don't store one).
        assert "API key for service X" in rendered


class TestExecute:
    def test_execute_refuses_without_approval(self) -> None:
        p = vc.plan(project_name="hermes-web")
        result = vc.execute(p)
        assert result.executed is False
        assert result.deployed is False
        assert any("approve=False" in e for e in result.errors)

    def test_execute_preview_with_approval_clears_gate(self) -> None:
        p = vc.plan(project_name="hermes-web", target="preview")
        result = vc.execute(p, approve=True)
        assert result.executed is True
        # Adapter never runs the actual deploy.
        assert result.deployed is False
        assert result.target == "preview"
        assert result.errors == []

    def test_execute_production_without_double_approval_refuses(self) -> None:
        p = vc.plan(project_name="hermes-web", target="production")
        result = vc.execute(p, approve=True)
        assert result.executed is False
        assert any("approve_production" in e for e in result.errors)

    def test_execute_production_with_double_approval_clears_gate(self) -> None:
        p = vc.plan(project_name="hermes-web", target="production")
        result = vc.execute(p, approve=True, approve_production=True)
        assert result.executed is True
        assert result.deployed is False
        assert result.target == "production"
        assert result.errors == []
