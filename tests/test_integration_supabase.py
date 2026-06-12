"""Tests for the Supabase integration adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from muse_cli.integrations import supabase as sb


@pytest.fixture
def users_table() -> sb.TableSpec:
    return sb.TableSpec(
        name="users",
        columns=[
            sb.ColumnSpec("id", "uuid", primary_key=True, default="gen_random_uuid()"),
            sb.ColumnSpec("email", "text", nullable=False, unique=True),
            sb.ColumnSpec("created_at", "timestamptz", nullable=False, default="now()"),
        ],
        comment="Application users.",
    )


class TestDetect:
    def test_detect_returns_detection(self, tmp_path: Path) -> None:
        det = sb.detect(project_root=tmp_path)
        assert isinstance(det, sb.Detection)
        assert isinstance(det.cli_present, bool)
        assert det.project_root == tmp_path.resolve()
        assert det.has_supabase_dir is False

    def test_detect_finds_supabase_dir(self, tmp_path: Path) -> None:
        (tmp_path / "supabase").mkdir()
        det = sb.detect(project_root=tmp_path)
        assert det.has_supabase_dir is True

    def test_detect_notes_missing_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sb.shutil, "which", lambda name: None)
        det = sb.detect(project_root=tmp_path)
        assert det.cli_present is False
        assert any("supabase" in n.lower() for n in det.notes)

    def test_detect_makes_no_network_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import socket

        def _no(*a, **kw):  # noqa: ANN001, ANN002, ANN003
            raise AssertionError("detect() must not open sockets")

        monkeypatch.setattr(socket, "socket", _no)
        sb.detect(project_root=tmp_path)


class TestColumnSpec:
    def test_render_basic(self) -> None:
        c = sb.ColumnSpec("name", "text")
        assert c.render() == "  name text"

    def test_render_primary_key(self) -> None:
        c = sb.ColumnSpec("id", "uuid", primary_key=True, default="gen_random_uuid()")
        rendered = c.render()
        assert "primary key" in rendered
        assert "default gen_random_uuid()" in rendered
        # PK should NOT also emit "not null" — it's implied.
        assert "not null" not in rendered

    def test_render_not_null_unique_default(self) -> None:
        c = sb.ColumnSpec(
            "email", "text", nullable=False, unique=True, default="''"
        )
        rendered = c.render()
        assert "unique" in rendered
        assert "not null" in rendered
        assert "default ''" in rendered

    def test_render_foreign_key(self) -> None:
        c = sb.ColumnSpec("org_id", "uuid", references="organizations(id)")
        assert "references organizations(id)" in c.render()


class TestRenderMigrationSql:
    def test_renders_create_table_idempotent(self, users_table: sb.TableSpec) -> None:
        sql = sb.render_migration_sql([users_table])
        assert "create table if not exists public.users" in sql
        assert "primary key" in sql
        assert "alter table public.users enable row level security;" in sql
        assert sql.endswith("\n")

    def test_renders_multiple_tables(self, users_table: sb.TableSpec) -> None:
        posts = sb.TableSpec(
            name="posts",
            columns=[
                sb.ColumnSpec("id", "uuid", primary_key=True),
                sb.ColumnSpec("user_id", "uuid", references="public.users(id)"),
            ],
        )
        sql = sb.render_migration_sql([users_table, posts])
        assert "public.users" in sql
        assert "public.posts" in sql
        assert sql.count("enable row level security") == 2

    def test_rls_can_be_disabled(self) -> None:
        t = sb.TableSpec(
            name="cache",
            columns=[sb.ColumnSpec("k", "text", primary_key=True)],
            enable_rls=False,
        )
        sql = sb.render_migration_sql([t])
        assert "enable row level security" not in sql

    def test_includes_header_as_sql_comments(self, users_table: sb.TableSpec) -> None:
        sql = sb.render_migration_sql([users_table], header="Add users table\nfor auth flow")
        assert "-- Add users table" in sql
        assert "-- for auth flow" in sql


class TestPlan:
    def test_plan_requires_at_least_one_table(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            sb.plan(migration_name="empty", tables=[], project_root=tmp_path)

    def test_plan_builds_full_artifact(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="add users table",
            tables=[users_table],
            project_root=tmp_path,
            timestamp="20260523120000",
        )
        assert isinstance(plan, sb.SupabasePlan)
        assert plan.migration_name == "add_users_table"
        assert plan.timestamp == "20260523120000"
        assert plan.migration_path == (
            tmp_path / "supabase" / "migrations" / "20260523120000_add_users_table.sql"
        )
        assert "create table" in plan.sql

    def test_plan_defaults_to_dry_run_and_requires_approval(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        assert plan.dry_run is True
        assert plan.approval_required is True

    def test_plan_emits_local_and_remote_argv_lists(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        assert plan.local_commands
        assert plan.remote_commands
        # argv lists, not strings
        for cmd in plan.local_commands + plan.remote_commands:
            assert isinstance(cmd, list)
            assert cmd[0] == "supabase"

    def test_plan_emits_rollback_and_validation(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        assert plan.rollback_notes
        assert plan.validation_steps
        # The "no edits to pushed migrations" rule must be present.
        assert any("already been pushed" in n for n in plan.rollback_notes)

    def test_plan_emits_secrets_policy(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        assert plan.secrets_policy
        joined = " ".join(plan.secrets_policy).lower()
        assert "service-role" in joined or "service role" in joined

    def test_plan_does_not_write_file(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        assert not plan.migration_path.exists()


class TestExplain:
    def test_explain_is_markdown(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        rendered = sb.explain(plan)
        assert isinstance(rendered, str)
        assert rendered.startswith("### Supabase migration plan")
        assert "Approval required" in rendered
        assert "Rollback" in rendered
        assert "Validation" in rendered
        assert "Secrets policy" in rendered

    def test_explain_lists_target_tables(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        rendered = sb.explain(plan)
        assert "public.users" in rendered


class TestExecute:
    def test_execute_refuses_without_approval(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        result = sb.execute(plan)
        assert result.executed is False
        assert result.wrote_migration is False
        assert result.migration_path is None
        assert any("approve=False" in e for e in result.errors)
        assert not plan.migration_path.exists()

    def test_execute_with_approval_writes_migration(
        self, tmp_path: Path, users_table: sb.TableSpec
    ) -> None:
        plan = sb.plan(
            migration_name="m", tables=[users_table], project_root=tmp_path
        )
        result = sb.execute(plan, approve=True)
        assert result.executed is True
        assert result.wrote_migration is True
        assert result.migration_path == plan.migration_path
        assert plan.migration_path.exists()
        text = plan.migration_path.read_text(encoding="utf-8")
        assert "create table if not exists public.users" in text
