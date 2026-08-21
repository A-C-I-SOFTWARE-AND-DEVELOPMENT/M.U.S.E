"""Tests for the legacy fork environment-variable shim.

The failure this guards against is specific: a tranche renames ``MUSE_X`` to
``HERMES_X`` but forgets the shim row, so a user with ``MUSE_X`` set has the
feature silently switched off with no error anywhere. These tests pin the
mechanism's behaviour now, while the table is empty, so the contract is
already enforced when the first row lands.
"""

import pytest

from hermes_cli import env_compat
from hermes_cli.env_compat import (
    LEGACY_ENV_ALIASES,
    apply_legacy_env_aliases,
    legacy_vars_in_use,
)


class TestTableShape:
    def test_no_legacy_name_maps_to_itself(self):
        same = [k for k, v in LEGACY_ENV_ALIASES.items() if k == v]
        assert not same, f"a no-op alias hides a missed rename: {same}"

    def test_no_two_legacy_names_collide_on_one_modern_name(self):
        seen: dict[str, str] = {}
        clashes = []
        for legacy, modern in LEGACY_ENV_ALIASES.items():
            if modern in seen:
                clashes.append(f"{seen[modern]} and {legacy} both map to {modern}")
            seen[modern] = legacy
        assert not clashes, "; ".join(clashes)

    def test_modern_names_use_the_hermes_prefix(self):
        wrong = [v for v in LEGACY_ENV_ALIASES.values() if not v.startswith("HERMES_")]
        assert not wrong, f"renamed vars must land in the HERMES_ namespace: {wrong}"


class TestApply:
    def test_carries_a_legacy_value_onto_the_modern_name(self, monkeypatch):
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_SAMPLE", "HERMES_SAMPLE")
        env = {"MUSE_SAMPLE": "on"}
        assert apply_legacy_env_aliases(env, warn=False) == ["MUSE_SAMPLE"]
        assert env["HERMES_SAMPLE"] == "on"

    def test_modern_name_wins_when_both_are_set(self, monkeypatch):
        """An explicit modern setting must never be clobbered by a stale legacy one."""
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_SAMPLE", "HERMES_SAMPLE")
        env = {"MUSE_SAMPLE": "stale", "HERMES_SAMPLE": "explicit"}
        assert apply_legacy_env_aliases(env, warn=False) == []
        assert env["HERMES_SAMPLE"] == "explicit"

    def test_empty_string_is_carried_not_treated_as_unset(self, monkeypatch):
        """`FLAG=` is a deliberate empty value, distinct from absent."""
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_SAMPLE", "HERMES_SAMPLE")
        env = {"MUSE_SAMPLE": ""}
        assert apply_legacy_env_aliases(env, warn=False) == ["MUSE_SAMPLE"]
        assert env["HERMES_SAMPLE"] == ""

    def test_is_idempotent(self, monkeypatch):
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_SAMPLE", "HERMES_SAMPLE")
        env = {"MUSE_SAMPLE": "on"}
        apply_legacy_env_aliases(env, warn=False)
        assert apply_legacy_env_aliases(env, warn=False) == []

    def test_absent_legacy_var_does_nothing(self, monkeypatch):
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_SAMPLE", "HERMES_SAMPLE")
        env: dict[str, str] = {}
        assert apply_legacy_env_aliases(env, warn=False) == []
        assert env == {}

    def test_empty_table_is_a_no_op(self):
        env = {"HERMES_EXISTING": "1"}
        assert apply_legacy_env_aliases(env, warn=False) == []
        assert env == {"HERMES_EXISTING": "1"}

    def test_warns_once_for_all_carried_names(self, monkeypatch, capsys):
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_A", "HERMES_A")
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_B", "HERMES_B")
        apply_legacy_env_aliases({"MUSE_A": "1", "MUSE_B": "2"}, warn=True)
        err = capsys.readouterr().err
        assert err.count("warning:") == 1
        assert "MUSE_A -> HERMES_A" in err and "MUSE_B -> HERMES_B" in err


class TestReporting:
    def test_reports_a_legacy_var_even_when_the_modern_one_wins(self, monkeypatch):
        """A user with both set needs to know the legacy one is now ignored."""
        monkeypatch.setitem(env_compat.LEGACY_ENV_ALIASES, "MUSE_SAMPLE", "HERMES_SAMPLE")
        env = {"MUSE_SAMPLE": "stale", "HERMES_SAMPLE": "explicit"}
        assert legacy_vars_in_use(env) == ["MUSE_SAMPLE"]

    def test_reports_nothing_on_a_clean_environment(self):
        assert legacy_vars_in_use({"HERMES_ANYTHING": "1"}) == []


def test_entry_points_install_the_shim():
    """The hook is a core edit; T6 was the last tranche allowed to make one.
    If it is ever dropped, the shim becomes dead code and every legacy var
    silently stops working."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    for rel in ("hermes_cli/main.py", "gateway/run.py"):
        src = (root / rel).read_text(encoding="utf-8", errors="replace")
        assert "apply_legacy_env_aliases()" in src, (
            f"{rel} no longer calls apply_legacy_env_aliases() at startup; "
            "every legacy environment variable is silently ignored without it"
        )


if __name__ == "__main__":
    pytest.main([__file__])
