"""Validity invariants for every shipped MCP catalog manifest.

These assert *contracts* — every manifest parses, transport/auth shapes are
coherent, and no secret is embedded — rather than pinning specific entries.
Adding a new manifest doesn't require touching this test, but a malformed one
(or one that bakes in a literal credential) fails CI.
"""

import re

import pytest

from hermes_cli.mcp_catalog import catalog_diagnostics, list_catalog

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Shapes that look like real credentials. Used to assert we never embed one.
_SECRETISH = re.compile(
    r"(xoxp-|xoxb-|ghp_|github_pat_|sk-[A-Za-z0-9]|secret_[A-Za-z0-9]|"
    r"ntn_[A-Za-z0-9]|Bearer\s+[A-Za-z0-9]{12,})"
)


@pytest.fixture(scope="module")
def entries():
    return list_catalog()


def test_catalog_is_nonempty_and_all_parse():
    # Fresh call so catalog_diagnostics() reflects exactly this load.
    loaded = list_catalog()
    assert loaded, "expected at least one catalog manifest in optional-mcps/"
    assert catalog_diagnostics() == [], (
        f"malformed / unsupported manifests: {catalog_diagnostics()}"
    )


def test_entry_names_unique_and_valid(entries):
    names = [e.name for e in entries]
    assert len(names) == len(set(names)), "duplicate catalog entry names"
    for name in names:
        assert _NAME_RE.match(name), f"invalid entry name: {name!r}"


def test_transport_shape(entries):
    for e in entries:
        assert e.transport.type in ("stdio", "http"), e.name
        if e.transport.type == "stdio":
            assert e.transport.command, f"{e.name}: stdio needs a command"
        else:
            assert e.transport.url and e.transport.url.startswith("http"), (
                f"{e.name}: http transport needs an http(s) url"
            )


def test_auth_shape(entries):
    for e in entries:
        assert e.auth.type in ("api_key", "oauth", "none"), e.name
        if e.auth.type == "api_key":
            assert e.auth.env, f"{e.name}: api_key auth must declare env vars"
            for spec in e.auth.env:
                assert _ENV_NAME_RE.match(spec.name), (
                    f"{e.name}: bad env var name {spec.name!r}"
                )


def test_git_install_shape(entries):
    for e in entries:
        if e.install is not None:
            assert e.install.type == "git", e.name
            assert e.install.url and e.install.ref, (
                f"{e.name}: git install needs url + ref"
            )


def test_no_embedded_secrets(entries):
    """Credentials are referenced via ${VAR}, never embedded as literals."""
    for e in entries:
        for spec in e.auth.env:
            assert not _SECRETISH.search(spec.default or ""), (
                f"{e.name}: env default for {spec.name} looks like a secret"
            )
        if e.auth.header:
            assert "${" in e.auth.header, (
                f"{e.name}: auth.header must reference a ${{VAR}}, not a literal"
            )
            # The non-placeholder part of the header must not carry a secret.
            prefix = e.auth.header.split("${", 1)[0]
            assert not _SECRETISH.search(prefix), (
                f"{e.name}: auth.header carries a literal secret"
            )
