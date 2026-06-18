"""Tests for the MUSE feature-toggle registry (hermes_cli/jarvis_prime/toggles.py).

The registry is the single source of truth for every opt-in / owner-gated
environment toggle MUSE honours. These tests enforce its integrity *and* the
"no drift" guarantee: every toggle the registry claims is wired must have a
read_site that exists and actually mentions the env var — so the registry can
never advertise a toggle the code does not honour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import toggles as tog

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Every toggle that MUST be in the registry, grouped. Keeps the inventory from
# silently regressing (a deleted row fails here instead of going unnoticed).
_EXPECTED = {
    "B1": {
        "MUSE_SYSTEM_CONTRACT",
        "HERMES_COCKPIT_SECRET_IMPORT",
        "HERMES_JARVIS_ENABLE_PAID",
        "HERMES_PUBLISH_LIVE",
        "HERMES_RELEASE_GATE_STRICT",
        "HERMES_CAPABILITY_GATE",
        "HERMES_ORCHESTRATOR_DISPATCH",
        "HERMES_CODEX_WORKER_EXECUTE",
        "HERMES_COCKPIT_AUTONOMY_LOCKED",
    },
    "B2": {
        "MUSE_AUTORESEARCH_ALLOW_SPAWN",
        "MUSE_UE5_ALLOW_SPAWN",
        "MUSE_PS_ALLOW_SPAWN",
        "HERMES_JARVIS_GEMMA_AUTO_RUNNER",
    },
    "B3": {
        "MUSE_SECOND_BRAIN",
        "MUSE_OBSERVATORY",
        "MUSE_TEMPLATES",
        "MUSE_TEMPLATES_SERVER",
    },
    "B4": {
        "HERMES_YOLO_MODE",
        "HERMES_ACCEPT_HOOKS",
        "HERMES_EXEC_ASK",
        "HERMES_ALLOW_ROOT_GATEWAY",
        "HERMES_ALLOW_PRIVATE_URLS",
        "HERMES_ENABLE_PROJECT_PLUGINS",
        "HERMES_DISABLE_FILE_STATE_GUARD",
        "HERMES_REDACT_SECRETS",
    },
    "B5": {
        "HERMES_OFFLINE",
        "HERMES_GATEWAY_FORCE_STARTUP",
        "HERMES_DASHBOARD",
        "HERMES_DASHBOARD_TUI",
        "HERMES_TUI",
        "HERMES_TUI_RESUME",
        "HERMES_BOOTSTRAP_MODELS",
        "HERMES_TERMUX_GATEWAY",
        "HERMES_TERMUX_NO_WAKELOCK",
        "HERMES_CRON_MAX_PARALLEL",
        "HERMES_GATEWAY_DETACHED",
        "HERMES_DEV",
        "HERMES_IGNORE_USER_CONFIG",
        "HERMES_IGNORE_RULES",
        "HERMES_NO_CONSOLIDATE",
        "HERMES_SKIP_NODE_BOOTSTRAP",
        "MUSE_NO_SECRET_IMPORT",
    },
}


@pytest.fixture(scope="module")
def all_toggles():
    return tog.load_toggles()


def test_registry_loads_and_is_sorted(all_toggles):
    assert all_toggles, "registry is empty"
    keys = [(t.group, t.env) for t in all_toggles]
    assert keys == sorted(keys), "toggles must be sorted by (group, env)"


def test_no_duplicate_env(all_toggles):
    envs = [t.env for t in all_toggles]
    assert len(envs) == len(set(envs))


def test_expected_inventory_present(all_toggles):
    by_env = {t.env: t for t in all_toggles}
    for group, envs in _EXPECTED.items():
        for env in envs:
            assert env in by_env, f"missing toggle {env} ({group})"
            assert by_env[env].group == group, (
                f"{env} should be in {group}, got {by_env[env].group}"
            )


def test_b1_toggles_are_owner_gated(all_toggles):
    for t in all_toggles:
        if t.group == "B1":
            assert t.owner_gated, f"B1 toggle {t.env} must be owner_gated"


def test_env_naming_and_groups(all_toggles):
    for t in all_toggles:
        assert tog._ENV_RE.match(t.env), f"bad env name {t.env!r}"
        assert t.group in tog.VALID_GROUPS
        assert t.summary, f"{t.env} has no summary"


def test_owner_gated_partition(all_toggles):
    gated = {t.env for t in tog.owner_gated_toggles(all_toggles)}
    assert gated == _EXPECTED["B1"], (
        "owner-gated set should equal the B1 band exactly"
    )


# --- the "no drift" guarantee ----------------------------------------------


def test_every_toggle_is_actually_wired(all_toggles):
    """Each read_site must exist and contain the env name — proof of wiring."""
    problems: list[str] = []
    for t in all_toggles:
        assert t.read_sites, f"{t.env} declares no read_sites"
        for rel, path in zip(t.read_sites, t.read_site_paths(_REPO_ROOT)):
            if not path.exists():
                problems.append(f"{t.env}: missing read_site {rel}")
            elif t.env not in path.read_text(encoding="utf-8", errors="ignore"):
                problems.append(f"{t.env}: {rel} does not mention {t.env}")
    assert not problems, "toggle registry drift:\n" + "\n".join(problems)


# --- resolution ------------------------------------------------------------


def test_is_enabled_resolves_truthy(all_toggles):
    t = tog.get("HERMES_OFFLINE", toggles=all_toggles)
    assert t is not None
    assert t.is_enabled({"HERMES_OFFLINE": "1"}) is True
    assert t.is_enabled({"HERMES_OFFLINE": "true"}) is True
    assert t.is_enabled({"HERMES_OFFLINE": "0"}) is False
    assert t.is_enabled({}) is False  # default off


def test_default_true_toggle_resolves_on_when_unset(all_toggles):
    t = tog.get("HERMES_REDACT_SECRETS", toggles=all_toggles)
    assert t is not None
    assert t.default is True
    assert t.is_enabled({}) is True
    assert t.is_enabled({"HERMES_REDACT_SECRETS": "false"}) is False


def test_module_is_enabled_unknown_is_false(all_toggles):
    assert tog.is_enabled("MUSE_NOT_A_REAL_TOGGLE", toggles=all_toggles) is False


def test_evaluate_all_covers_every_toggle(all_toggles):
    results = tog.evaluate_all({}, toggles=all_toggles)
    assert len(results) == len(all_toggles)
    assert all(isinstance(on, bool) for _, on in results)


def test_by_group(all_toggles):
    for group in tog.VALID_GROUPS:
        members = tog.by_group(group, toggles=all_toggles)
        assert all(t.group == group for t in members)


# --- validation failure modes ----------------------------------------------


def test_b1_without_owner_gated_rejected():
    with pytest.raises(ValueError):
        tog.Toggle.from_dict(
            {"env": "MUSE_FOO", "group": "B1", "summary": "x", "owner_gated": False}
        )


def test_bad_env_name_rejected():
    with pytest.raises(ValueError):
        tog.Toggle.from_dict({"env": "lowercase", "group": "B5", "summary": "x"})


def test_bad_group_rejected():
    with pytest.raises(ValueError):
        tog.Toggle.from_dict({"env": "MUSE_FOO", "group": "Z9", "summary": "x"})
