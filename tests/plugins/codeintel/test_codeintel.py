"""codeintel plugin — registration, double-gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.codeintel as plugin_pkg
import plugins.codeintel.tools as tools
from plugins.codeintel import config as codeintel_config
from plugins.codeintel.client import CodeintelClient
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


def _cfg(monkeypatch, *, enabled=True, allow_exec=False):
    monkeypatch.setattr(
        codeintel_config,
        "load_config",
        lambda: codeintel_config.CodeintelConfig(
            enabled=enabled, allow_code_execution=allow_exec
        ),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    m.resolve_osv_ecosystem = CodeintelClient.resolve_osv_ecosystem
    m.resolve_depsdev_system = CodeintelClient.resolve_depsdev_system
    monkeypatch.setattr(tools, "CodeintelClient", m)
    return instance


# ── registration + gating ────────────────────────────────────────────────────


def test_register_emits_three_tools_with_distinct_run_code_gate():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    by_name = {c["name"]: c for c in captured}
    assert set(by_name) == {"dependency_audit", "dependency_info", "run_code"}
    assert all(c["toolset"] == "codeintel" for c in captured)
    # run_code must NOT share the read-only tools' check_fn.
    assert (
        by_name["run_code"]["check_fn"] is not by_name["dependency_audit"]["check_fn"]
    )


def test_run_code_check_fn_requires_both_flags(monkeypatch):
    _cfg(monkeypatch, enabled=True, allow_exec=False)
    assert tools.check_codeintel_enabled() is True
    assert tools.check_run_code_ready() is False
    _cfg(monkeypatch, enabled=True, allow_exec=True)
    assert tools.check_run_code_ready() is True
    _cfg(monkeypatch, enabled=False, allow_exec=True)
    assert tools.check_run_code_ready() is False


# ── dependency_audit (OSV) ───────────────────────────────────────────────────


def test_dependency_audit_reports_vulns(monkeypatch, mock_client):
    _cfg(monkeypatch)
    mock_client.osv_query.return_value = {
        "vulns": [
            {
                "id": "GHSA-xxxx",
                "summary": "RCE",
                "aliases": ["CVE-2025-0001"],
                "severity": [{"type": "CVSS_V3", "score": "9.8"}],
                "modified": "2025-01-01",
                "details": "long noise",
            }
        ]
    }
    out = _parse(
        tools.handle_dependency_audit({
            "ecosystem": "pip",
            "name": "flask",
            "version": "0.1",
        })
    )
    assert out["success"] is True
    assert out["vulnerable"] is True
    assert out["ecosystem"] == "PyPI"  # alias resolved
    assert out["vulnerabilities"][0]["severity"] == "9.8"
    assert "details" not in out["vulnerabilities"][0]


def test_dependency_audit_clean_is_not_vulnerable(monkeypatch, mock_client):
    _cfg(monkeypatch)
    mock_client.osv_query.return_value = {}
    out = _parse(
        tools.handle_dependency_audit({"ecosystem": "npm", "name": "left-pad"})
    )
    assert out["vulnerable"] is False
    assert out["vulnerabilities"] == []


def test_dependency_audit_requires_fields(monkeypatch, mock_client):
    _cfg(monkeypatch)
    assert _parse(tools.handle_dependency_audit({"name": "x"}))["error"] == "bad_args"
    assert (
        _parse(tools.handle_dependency_audit({"ecosystem": "pip"}))["error"]
        == "bad_args"
    )


# ── dependency_info (deps.dev) ───────────────────────────────────────────────


def test_dependency_info_version_returns_licenses(monkeypatch, mock_client):
    _cfg(monkeypatch)
    mock_client.depsdev.return_value = {
        "licenses": ["MIT"],
        "advisoryKeys": [{"id": "GHSA-yyyy"}],
        "publishedAt": "2024-01-01T00:00:00Z",
    }
    out = _parse(
        tools.handle_dependency_info({
            "system": "cargo",
            "name": "serde",
            "version": "1.0.0",
        })
    )
    assert out["licenses"] == ["MIT"]
    assert out["advisory_keys"] == ["GHSA-yyyy"]
    assert mock_client.depsdev.call_args.args[0] == "cargo"


def test_dependency_info_without_version_lists_versions(monkeypatch, mock_client):
    _cfg(monkeypatch)
    mock_client.depsdev.return_value = {
        "versions": [
            {"versionKey": {"version": "1.0.0"}},
            {"versionKey": {"version": "1.1.0"}},
        ]
    }
    out = _parse(tools.handle_dependency_info({"system": "pypi", "name": "flask"}))
    assert out["versions"] == ["1.0.0", "1.1.0"]


# ── run_code (Piston, double-gated) ──────────────────────────────────────────


def test_run_code_refused_when_exec_not_allowed(monkeypatch, mock_client):
    _cfg(monkeypatch, enabled=True, allow_exec=False)
    out = _parse(tools.handle_run_code({"language": "python", "code": "print(1)"}))
    assert out["error"] == "code_execution_disabled"
    mock_client.piston_execute.assert_not_called()


def test_run_code_refused_when_plugin_disabled(monkeypatch, mock_client):
    _cfg(monkeypatch, enabled=False, allow_exec=True)
    out = _parse(tools.handle_run_code({"language": "python", "code": "print(1)"}))
    assert out["error"] == "plugin_disabled"
    mock_client.piston_execute.assert_not_called()


def test_run_code_executes_when_allowed(monkeypatch, mock_client):
    _cfg(monkeypatch, enabled=True, allow_exec=True)
    mock_client.piston_execute.return_value = {
        "language": "python",
        "version": "3.12.0",
        "run": {"stdout": "1\n", "stderr": "", "code": 0, "output": "1\n"},
    }
    out = _parse(tools.handle_run_code({"language": "python", "code": "print(1)"}))
    assert out["success"] is True
    assert out["stdout"] == "1\n"
    assert out["exit_code"] == 0


def test_run_code_rejects_oversized_code(monkeypatch, mock_client):
    _cfg(monkeypatch, enabled=True, allow_exec=True)
    out = _parse(
        tools.handle_run_code({
            "language": "python",
            "code": "x" * (tools.MAX_CODE_CHARS + 1),
        })
    )
    assert out["error"] == "bad_args"
    mock_client.piston_execute.assert_not_called()
