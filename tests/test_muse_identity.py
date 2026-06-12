"""MUSE is the default-and-only baseline identity (Phase 5 of the rename).

Invariants pinned here:

* ``DEFAULT_AGENT_IDENTITY`` and ``DEFAULT_SOUL_MD`` are the MUSE identity
  and stay word-for-word identical (no cross-package import in production
  code — this test is the lock).
* The baseline system prompt is MUSE with no flag, mode, or SOUL.md needed;
  clearing the ``/personality`` overlay still yields MUSE.
* A never-edited legacy default SOUL.md is upgraded in place at startup;
  an edited SOUL.md is never touched.
"""

from unittest.mock import MagicMock

from agent.prompt_builder import DEFAULT_AGENT_IDENTITY
from muse_cli.default_soul import _LEGACY_DEFAULT_SOUL_MD, DEFAULT_SOUL_MD


class TestIdentityConstants:
    def test_soul_and_agent_identity_are_identical(self):
        assert DEFAULT_AGENT_IDENTITY == DEFAULT_SOUL_MD

    def test_identity_is_muse(self):
        assert "You are MUSE" in DEFAULT_AGENT_IDENTITY
        assert "Hermes Agent" not in DEFAULT_AGENT_IDENTITY

    def test_legacy_constant_is_the_old_text(self):
        assert _LEGACY_DEFAULT_SOUL_MD.startswith("You are Hermes Agent")
        assert _LEGACY_DEFAULT_SOUL_MD != DEFAULT_SOUL_MD


class TestBaselineSystemPromptIsMuse:
    """The identity slot of the system prompt (agent/system_prompt.py: SOUL.md
    if present, else DEFAULT_AGENT_IDENTITY) yields MUSE in both branches —
    no flag, mode, or command required."""

    def test_empty_home_identity_is_muse(self, monkeypatch, tmp_path):
        """load_soul_md() seeds the default SOUL.md on first run — an empty
        home still yields the MUSE identity with no flag required."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from agent.prompt_builder import load_soul_md

        soul = load_soul_md()
        assert soul and "You are MUSE" in soul
        # And the hardcoded fallback slot is MUSE too.
        assert "You are MUSE" in DEFAULT_AGENT_IDENTITY

    def test_seeded_soul_md_identity_is_muse(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from muse_cli.config import _ensure_default_soul_md

        _ensure_default_soul_md(tmp_path)
        from agent.prompt_builder import load_soul_md

        soul = load_soul_md()
        assert soul and "You are MUSE" in soul

    def test_personality_none_still_yields_muse(self, monkeypatch, tmp_path):
        """`/personality none` clears the additive overlay; the baseline
        identity underneath is MUSE — requesting 'none' yields MUSE."""
        from unittest.mock import patch as _patch

        from cli import HermesCLI

        cli = HermesCLI.__new__(HermesCLI)
        cli.personalities = {"helpful": "You are helpful."}
        cli.system_prompt = "You are kawaii~"
        cli.agent = MagicMock()
        cli.console = MagicMock()
        with _patch("cli.save_config_value", return_value=True):
            cli._handle_personality_command("/personality none")
        # Overlay cleared...
        assert cli.system_prompt == ""
        # ...and the baseline identity the next agent init builds on is MUSE
        # (seeded SOUL.md, or the hardcoded fallback — both MUSE).
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from agent.prompt_builder import load_soul_md

        soul = load_soul_md()
        assert soul and "You are MUSE" in soul
        assert "You are MUSE" in DEFAULT_AGENT_IDENTITY


class TestLegacySoulUpgrade:
    def test_fresh_seed_writes_muse_soul(self, monkeypatch, tmp_path):
        from muse_cli.config import _ensure_default_soul_md

        _ensure_default_soul_md(tmp_path)
        content = (tmp_path / "SOUL.md").read_text(encoding="utf-8")
        assert content == DEFAULT_SOUL_MD

    def test_unedited_legacy_default_is_upgraded(self, tmp_path):
        from muse_cli.config import _ensure_default_soul_md

        (tmp_path / "SOUL.md").write_text(_LEGACY_DEFAULT_SOUL_MD, encoding="utf-8")
        _ensure_default_soul_md(tmp_path)
        content = (tmp_path / "SOUL.md").read_text(encoding="utf-8")
        assert content == DEFAULT_SOUL_MD

    def test_edited_soul_is_never_touched(self, tmp_path):
        from muse_cli.config import _ensure_default_soul_md

        custom = "You are my heavily customized agent. Do not change me."
        (tmp_path / "SOUL.md").write_text(custom, encoding="utf-8")
        _ensure_default_soul_md(tmp_path)
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == custom
