"""MUSE_HOME / MUSE_QUIET env vars with permanent HERMES_* fallback.

Phase 3 of the Hermes->MUSE rename: the canonical env names are MUSE_*, the
legacy HERMES_* names are honored forever, and MUSE_* wins when both are set.
"""

from pathlib import Path

import muse_constants
from muse_constants import env_first, get_hermes_home, get_muse_home


class TestHomeEnvPrecedence:
    def test_muse_home_wins_over_hermes_home(self, monkeypatch):
        monkeypatch.setenv("MUSE_HOME", "/tmp/muse-home-new")
        monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-home-old")
        assert get_hermes_home() == Path("/tmp/muse-home-new")

    def test_hermes_home_alone_still_works(self, monkeypatch):
        monkeypatch.delenv("MUSE_HOME", raising=False)
        monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-home-old")
        assert get_hermes_home() == Path("/tmp/hermes-home-old")

    def test_muse_home_alone_works(self, monkeypatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setenv("MUSE_HOME", "/tmp/muse-home-only")
        assert get_hermes_home() == Path("/tmp/muse-home-only")

    def test_get_muse_home_is_the_same_function(self):
        assert get_muse_home is get_hermes_home

    def test_default_root_honors_muse_home(self, monkeypatch):
        monkeypatch.setenv("MUSE_HOME", "/opt/musedata/profiles/coder")
        monkeypatch.setenv("HERMES_HOME", "/opt/otherdata")
        root = muse_constants.get_default_hermes_root()
        assert root == Path("/opt/musedata")


class TestEnvFirst:
    def test_new_wins(self, monkeypatch):
        monkeypatch.setenv("MUSE_X_TEST", "new")
        monkeypatch.setenv("HERMES_X_TEST", "old")
        assert env_first("MUSE_X_TEST", "HERMES_X_TEST") == "new"

    def test_falls_back_to_old(self, monkeypatch):
        monkeypatch.delenv("MUSE_X_TEST", raising=False)
        monkeypatch.setenv("HERMES_X_TEST", "old")
        assert env_first("MUSE_X_TEST", "HERMES_X_TEST") == "old"

    def test_empty_counts_as_unset(self, monkeypatch):
        monkeypatch.setenv("MUSE_X_TEST", "   ")
        monkeypatch.setenv("HERMES_X_TEST", "old")
        assert env_first("MUSE_X_TEST", "HERMES_X_TEST") == "old"

    def test_neither_set(self, monkeypatch):
        monkeypatch.delenv("MUSE_X_TEST", raising=False)
        monkeypatch.delenv("HERMES_X_TEST", raising=False)
        assert env_first("MUSE_X_TEST", "HERMES_X_TEST") is None


class TestLegacyAliasSync:
    def test_mirrors_new_onto_old_when_old_unset(self, monkeypatch):
        monkeypatch.setenv("MUSE_HOME", "/tmp/sync-home")
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setenv("MUSE_QUIET", "1")
        monkeypatch.delenv("HERMES_QUIET", raising=False)
        muse_constants._sync_legacy_env_aliases()
        import os

        assert os.environ["HERMES_HOME"] == "/tmp/sync-home"
        assert os.environ["HERMES_QUIET"] == "1"

    def test_never_overwrites_an_existing_old_value(self, monkeypatch):
        monkeypatch.setenv("MUSE_HOME", "/tmp/sync-new")
        monkeypatch.setenv("HERMES_HOME", "/tmp/sync-old")
        muse_constants._sync_legacy_env_aliases()
        import os

        assert os.environ["HERMES_HOME"] == "/tmp/sync-old"

    def test_noop_when_new_unset(self, monkeypatch):
        monkeypatch.delenv("MUSE_HOME", raising=False)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        muse_constants._sync_legacy_env_aliases()
        import os

        assert "HERMES_HOME" not in os.environ


class TestCanonicalAliases:
    def test_constants_aliases_are_identities(self):
        assert muse_constants.display_muse_home is muse_constants.display_hermes_home
        assert muse_constants.get_default_muse_root is muse_constants.get_default_hermes_root
        assert muse_constants.set_muse_home_override is muse_constants.set_hermes_home_override
        assert muse_constants.get_muse_dir is muse_constants.get_hermes_dir

    def test_dotenv_alias(self):
        from muse_cli.env_loader import load_hermes_dotenv, load_muse_dotenv

        assert load_muse_dotenv is load_hermes_dotenv

    def test_dotenv_defaults_to_resolved_native_home(self, monkeypatch, tmp_path):
        """With no env config at all, the dotenv loader follows the resolved
        native home (~/.muse on fresh post-rename installs), not a hardcoded
        ~/.hermes."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("MUSE_HOME", raising=False)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.delenv("MUSE_ENV_PROBE2", raising=False)
        muse_home = tmp_path / ".muse"
        muse_home.mkdir()
        (muse_home / ".env").write_text(
            "MUSE_ENV_PROBE2=from-native-muse\n", encoding="utf-8"
        )
        from muse_cli.env_loader import load_muse_dotenv

        loaded = load_muse_dotenv()
        import os

        assert muse_home / ".env" in loaded
        assert os.environ.get("MUSE_ENV_PROBE2") == "from-native-muse"

    def test_dotenv_reads_muse_home(self, monkeypatch, tmp_path):
        home = tmp_path / "musehome"
        home.mkdir()
        (home / ".env").write_text("MUSE_ENV_PROBE=from-muse-home\n", encoding="utf-8")
        monkeypatch.setenv("MUSE_HOME", str(home))
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.delenv("MUSE_ENV_PROBE", raising=False)
        from muse_cli.env_loader import load_muse_dotenv

        loaded = load_muse_dotenv()
        import os

        assert home / ".env" in loaded
        assert os.environ.get("MUSE_ENV_PROBE") == "from-muse-home"
