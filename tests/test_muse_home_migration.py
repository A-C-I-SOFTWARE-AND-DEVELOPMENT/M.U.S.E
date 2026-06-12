"""One-shot ~/.hermes -> ~/.muse state-dir migration (Phase 4 of the rename).

Contract: atomic rename + breadcrumb + compat symlink; idempotent; never
clobbers an existing ~/.muse; opts out under explicit env configuration,
context override, or managed installs.
"""

from pathlib import Path

import pytest

import muse_constants
from muse_constants import _default_native_home, get_hermes_home, migrate_legacy_home_once


@pytest.fixture
def fresh_home(monkeypatch, tmp_path):
    """Isolated $HOME with no MUSE/HERMES env config and a reset once-flag."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("MUSE_HOME", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("MUSE_MANAGED", raising=False)
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    monkeypatch.setattr(muse_constants, "_legacy_home_migrated", False)
    return tmp_path


def _seed_legacy(tmp_path: Path) -> Path:
    old = tmp_path / ".hermes"
    (old / "sessions").mkdir(parents=True)
    (old / "config.yaml").write_text("agent: {}\n", encoding="utf-8")
    (old / "sessions" / "s1.json").write_text("{}", encoding="utf-8")
    return old


class TestMigration:
    def test_migrates_rename_breadcrumb_symlink(self, fresh_home):
        old = _seed_legacy(fresh_home)
        new = fresh_home / ".muse"

        result = migrate_legacy_home_once()

        assert result == new
        assert new.is_dir()
        # data intact
        assert (new / "config.yaml").read_text(encoding="utf-8") == "agent: {}\n"
        assert (new / "sessions" / "s1.json").exists()
        # breadcrumb present
        assert (new / ".migrated_from_hermes").exists()
        # legacy path still resolves via compat symlink
        assert old.is_symlink()
        assert (old / "config.yaml").read_text(encoding="utf-8") == "agent: {}\n"

    def test_runs_twice_no_clobber(self, fresh_home, monkeypatch):
        _seed_legacy(fresh_home)
        new = fresh_home / ".muse"
        assert migrate_legacy_home_once() == new
        (new / "post-migration.marker").write_text("keep me", encoding="utf-8")

        # Second run (fresh process simulated by resetting the once-flag).
        monkeypatch.setattr(muse_constants, "_legacy_home_migrated", False)
        assert migrate_legacy_home_once() is None
        assert (new / "post-migration.marker").read_text(encoding="utf-8") == "keep me"
        assert (new / "config.yaml").exists()
        assert (new / ".migrated_from_hermes").exists()

    def test_never_clobbers_existing_muse_dir(self, fresh_home):
        _seed_legacy(fresh_home)
        new = fresh_home / ".muse"
        new.mkdir()
        (new / "mine.txt").write_text("pre-existing", encoding="utf-8")

        assert migrate_legacy_home_once() is None
        assert (new / "mine.txt").read_text(encoding="utf-8") == "pre-existing"
        assert not (new / "config.yaml").exists()
        # legacy dir untouched (still a real dir, not a symlink)
        assert (fresh_home / ".hermes").is_dir()
        assert not (fresh_home / ".hermes").is_symlink()

    def test_noop_when_env_configured(self, fresh_home, monkeypatch):
        old = _seed_legacy(fresh_home)
        monkeypatch.setenv("HERMES_HOME", str(old))
        assert migrate_legacy_home_once() is None
        assert old.is_dir() and not old.is_symlink()

        monkeypatch.setattr(muse_constants, "_legacy_home_migrated", False)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setenv("MUSE_HOME", str(old))
        assert migrate_legacy_home_once() is None

    def test_noop_when_managed(self, fresh_home, monkeypatch):
        _seed_legacy(fresh_home)
        monkeypatch.setenv("HERMES_MANAGED", "1")
        assert migrate_legacy_home_once() is None

    def test_noop_on_managed_marker_in_dir(self, fresh_home):
        old = _seed_legacy(fresh_home)
        (old / ".managed").write_text("", encoding="utf-8")
        assert migrate_legacy_home_once() is None
        assert not (fresh_home / ".muse").exists()

    def test_noop_when_old_is_already_symlink(self, fresh_home):
        new = fresh_home / ".muse2-target"
        new.mkdir()
        (fresh_home / ".hermes").symlink_to(new)
        assert migrate_legacy_home_once() is None

    def test_noop_when_nothing_exists(self, fresh_home):
        assert migrate_legacy_home_once() is None
        assert not (fresh_home / ".muse").exists()
        assert not (fresh_home / ".hermes").exists()


class TestDefaultResolution:
    """get_hermes_home() default branch: ~/.muse wins, ~/.hermes legacy."""

    def test_prefers_existing_muse(self, fresh_home):
        (fresh_home / ".muse").mkdir()
        (fresh_home / ".hermes").mkdir()
        assert get_hermes_home() == fresh_home / ".muse"
        assert _default_native_home() == fresh_home / ".muse"

    def test_falls_back_to_existing_hermes(self, fresh_home):
        (fresh_home / ".hermes").mkdir()
        assert get_hermes_home() == fresh_home / ".hermes"

    def test_fresh_install_defaults_to_muse(self, fresh_home):
        assert get_hermes_home() == fresh_home / ".muse"

    def test_env_still_outranks_default(self, fresh_home, monkeypatch):
        (fresh_home / ".muse").mkdir()
        monkeypatch.setenv("HERMES_HOME", "/tmp/env-home")
        assert get_hermes_home() == Path("/tmp/env-home")
