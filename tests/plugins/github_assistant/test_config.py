"""Config loader + allowlist + path-traversal defence."""

from __future__ import annotations

from typing import Any, Mapping, cast

import pytest

from plugins.github_assistant.config import (
    ConfigError,
    GithubConfig,
    from_mapping,
    validate_owner_name,
)


def test_defaults_are_off_off_empty():
    cfg = GithubConfig()
    assert cfg.enabled is False
    assert cfg.allow_writes is False
    assert cfg.allowed_repositories == ()


def test_from_mapping_none_returns_defaults():
    assert from_mapping(None) == GithubConfig()


def test_from_mapping_full():
    cfg = from_mapping({
        "enabled": True,
        "allow_writes": True,
        "allowed_repositories": ["echerd27-design/hermes-agent", "octo/cat"],
    })
    assert cfg.enabled is True
    assert cfg.allow_writes is True
    assert cfg.allowed_repositories == (
        "echerd27-design/hermes-agent",
        "octo/cat",
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"enabled": "yes"}, True),
        ({"enabled": "on"}, True),
        ({"enabled": "off"}, False),
        ({"enabled": "0"}, False),
    ],
)
def test_bool_coercion(raw, expected):
    assert from_mapping(raw).enabled is expected


def test_bad_bool_raises():
    with pytest.raises(ConfigError):
        from_mapping({"enabled": "maybe"})


def test_allowed_repositories_must_be_a_list():
    with pytest.raises(ConfigError):
        from_mapping({"allowed_repositories": "echerd27-design/hermes-agent"})


def test_allowed_repositories_entry_must_be_owner_slash_name():
    with pytest.raises(ConfigError):
        from_mapping({"allowed_repositories": ["just-name"]})


def test_allowed_repositories_entry_must_be_valid_chars():
    with pytest.raises(ConfigError):
        from_mapping({"allowed_repositories": ["owner/../escape"]})


def test_top_level_must_be_mapping():
    # from_mapping is typed to accept Mapping | None; cast() suppresses the
    # type checker while keeping the runtime value a plain string so the
    # production code path that rejects non-Mapping values gets exercised.
    bogus = cast(Mapping[str, Any], "not a dict")
    with pytest.raises(ConfigError):
        from_mapping(bogus)


def test_is_repo_allowed_empty_means_no_allowlist():
    cfg = GithubConfig(allowed_repositories=())
    assert cfg.is_repo_allowed("anyone", "anyrepo") is True


def test_is_repo_allowed_populated_means_deny_by_default():
    cfg = GithubConfig(allowed_repositories=("a/b",))
    assert cfg.is_repo_allowed("a", "b") is True
    assert cfg.is_repo_allowed("a", "c") is False
    assert cfg.is_repo_allowed("x", "b") is False


@pytest.mark.parametrize(
    "owner,name",
    [
        ("echerd27-design", "hermes-agent"),
        ("oct", "cat-1"),
        ("a.b", "c_d"),
    ],
)
def test_validate_owner_name_accepts_safe(owner, name):
    validate_owner_name(owner, name)  # does not raise


@pytest.mark.parametrize(
    "owner,name",
    [
        ("../etc", "passwd"),
        ("owner", "a/b"),
        ("", "name"),
        ("owner", ""),
        ("owner\x00", "name"),
        ("owner!", "name"),
    ],
)
def test_validate_owner_name_rejects_dangerous(owner, name):
    import pytest

    with pytest.raises(ConfigError):
        validate_owner_name(owner, name)
