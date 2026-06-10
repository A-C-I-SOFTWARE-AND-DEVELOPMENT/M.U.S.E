"""Tests for the non-interactive bulk-install path in hermes_cli.mcp_catalog.

``register_entry_noninteractive`` / ``install_all_entries`` must never prompt,
probe, or launch a server, must never write a literal secret, and must isolate
per-entry failures so one bad entry can't abort a bulk install.
"""

from pathlib import Path

import pytest

from hermes_cli.config import load_config
from hermes_cli.mcp_catalog import (
    AuthSpec,
    CatalogEntry,
    EnvVarSpec,
    InstallSpec,
    TransportSpec,
    install_all_entries,
    register_entry_noninteractive,
)


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Redirect all config / .env I/O to a temp directory."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("hermes_cli.config.get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(
        "hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml"
    )
    monkeypatch.setattr(
        "hermes_cli.config.get_env_path", lambda: tmp_path / ".env"
    )
    return tmp_path


# ─── builders ────────────────────────────────────────────────────────────────

def _stdio_none(name="srv-none"):
    return CatalogEntry(
        name=name, description="d", source="",
        transport=TransportSpec(type="stdio", command="echo", args=["hi"]),
        auth=AuthSpec(type="none"),
    )


def _stdio_apikey(name="srv-key", var="MY_TOKEN"):
    return CatalogEntry(
        name=name, description="d", source="",
        transport=TransportSpec(type="stdio", command="npx", args=["-y", "x"]),
        auth=AuthSpec(type="api_key", env=[EnvVarSpec(name=var, prompt="p")]),
    )


def _http_oauth(name="srv-oauth"):
    return CatalogEntry(
        name=name, description="d", source="",
        transport=TransportSpec(type="http", url="https://example.com/mcp"),
        auth=AuthSpec(type="oauth"),
    )


def _git_entry(name="srv-git"):
    return CatalogEntry(
        name=name, description="d", source="",
        transport=TransportSpec(type="stdio", command="${INSTALL_DIR}/bin"),
        auth=AuthSpec(type="none"),
        install=InstallSpec(
            type="git", url="https://example.com/x.git", ref="main", bootstrap=[]
        ),
    )


@pytest.fixture(autouse=True)
def _never_probe(monkeypatch):
    """Hard guard: registration must never reach the probe/launch path."""
    def boom(*a, **k):
        raise AssertionError("non-interactive register must not probe/launch")
    monkeypatch.setattr(
        "hermes_cli.mcp_config._probe_single_server", boom, raising=False
    )


# ─── register_entry_noninteractive ─────────────────────────────────────────────

def test_none_auth_written_and_enabled():
    res = register_entry_noninteractive(_stdio_none())
    assert res["status"] == "installed"
    assert res["enabled"] is True
    servers = load_config().get("mcp_servers", {})
    assert servers["srv-none"]["command"] == "echo"
    assert servers["srv-none"]["enabled"] is True


def test_oauth_written_and_enabled():
    res = register_entry_noninteractive(_http_oauth())
    assert res["status"] == "installed"
    assert res["enabled"] is True
    assert load_config()["mcp_servers"]["srv-oauth"]["auth"] == "oauth"


def test_apikey_missing_creds_disabled_with_ref(tmp_path):
    res = register_entry_noninteractive(_stdio_apikey(var="MY_TOKEN"))
    assert res["status"] == "needs_creds"
    assert res["enabled"] is False
    # The literal ${VAR} must be persisted, never an expanded (empty) value.
    raw = (tmp_path / "config.yaml").read_text()
    assert "${MY_TOKEN}" in raw
    servers = load_config().get("mcp_servers", {})
    assert servers["srv-key"]["env"]["MY_TOKEN"] == "${MY_TOKEN}"


def test_apikey_present_creds_enabled(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.mcp_catalog.get_env_value",
        lambda n: "xyz" if n == "PRESENT_TOKEN" else "",
    )
    res = register_entry_noninteractive(_stdio_apikey(var="PRESENT_TOKEN"))
    assert res["status"] == "installed"
    assert res["enabled"] is True


def test_apikey_force_enable_without_creds():
    res = register_entry_noninteractive(
        _stdio_apikey(var="ABSENT_TOKEN"), enable_without_creds=True
    )
    assert res["status"] == "needs_creds"  # creds still genuinely absent
    assert res["enabled"] is True          # but force-enabled


def test_git_skipped_without_bootstrap(monkeypatch):
    called = {"clone": False}

    def fake_clone(entry):
        called["clone"] = True
        return Path("/tmp/should-not-run")

    monkeypatch.setattr("hermes_cli.mcp_catalog._do_git_install", fake_clone)
    res = register_entry_noninteractive(_git_entry(), run_bootstrap=False)
    assert res["status"] == "skipped"
    assert called["clone"] is False
    assert "srv-git" not in load_config().get("mcp_servers", {})


# ─── install_all_entries ───────────────────────────────────────────────────────

def test_install_all_isolates_one_failure(monkeypatch):
    good, bad = _stdio_none(name="good"), _stdio_none(name="bad")
    monkeypatch.setattr("hermes_cli.mcp_catalog.list_catalog", lambda: [good, bad])

    real = register_entry_noninteractive

    def maybe_raise(entry, **kw):
        if entry.name == "bad":
            raise RuntimeError("boom")
        return real(entry, **kw)

    monkeypatch.setattr(
        "hermes_cli.mcp_catalog.register_entry_noninteractive", maybe_raise
    )
    summary = install_all_entries()
    assert [r["name"] for r in summary["installed"]] == ["good"]
    assert [r["name"] for r in summary["failed"]] == ["bad"]
    # The good entry still landed in config despite the bad one raising.
    assert "good" in load_config().get("mcp_servers", {})
