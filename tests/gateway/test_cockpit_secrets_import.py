"""Owner-gated, opt-in import of the user's existing ~/.hermes/.env credential
keys via the cockpit. Confirms: disabled by default (403), requires the bearer
token (401), and — once HERMES_COCKPIT_SECRET_IMPORT=1 — returns only
credential-shaped names with their values, never non-credential lines.
"""

from __future__ import annotations

import http.client
import json

import pytest

from gateway.cockpit import server as srv


def _get(port: int, path: str, token: str | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        conn.request("GET", path, headers=headers)
        r = conn.getresponse()
        body = r.read()
        try:
            return r.status, json.loads(body)
        except json.JSONDecodeError:
            return r.status, {}
    finally:
        conn.close()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / ".env").write_text(
        "# my keys\n"
        "OPENROUTER_API_KEY=sk-or-abc123\n"
        "ANTHROPIC_API_KEY=sk-ant-xyz\n"
        'GITHUB_PERSONAL_ACCESS_TOKEN="ghp_quoted"\n'
        "SUPABASE_URL=https://x.supabase.co\n"
        "export GROQ_API_KEY=gsk_exported\n"
        "SOME_NOTE=not a credential\n"
        "PORT=8765\n"
    )
    return tmp_path


@pytest.fixture()
def cockpit(home, monkeypatch):
    monkeypatch.delenv("HERMES_COCKPIT_SECRET_IMPORT", raising=False)
    httpd = srv.serve("127.0.0.1", 0, token="testtoken", responder=lambda prompt, history: iter(()))
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()


def test_disabled_by_default(cockpit):
    status, body = _get(cockpit, "/v1/cockpit/secrets/import", token="testtoken")
    assert status == 403
    assert "disabled" in body.get("error", "")


def test_requires_bearer(cockpit, monkeypatch):
    monkeypatch.setenv("HERMES_COCKPIT_SECRET_IMPORT", "1")
    status, _ = _get(cockpit, "/v1/cockpit/secrets/import")  # no token
    assert status == 401


def test_enabled_returns_only_credential_keys(cockpit, monkeypatch):
    monkeypatch.setenv("HERMES_COCKPIT_SECRET_IMPORT", "1")
    status, body = _get(cockpit, "/v1/cockpit/secrets/import", token="testtoken")
    assert status == 200
    keys = body["keys"]
    # Credential-shaped keys are returned with values (quotes/`export ` stripped).
    assert keys["OPENROUTER_API_KEY"] == "sk-or-abc123"
    assert keys["ANTHROPIC_API_KEY"] == "sk-ant-xyz"
    assert keys["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_quoted"
    assert keys["SUPABASE_URL"] == "https://x.supabase.co"
    assert keys["GROQ_API_KEY"] == "gsk_exported"
    # Non-credential lines are excluded.
    assert "SOME_NOTE" not in keys
    assert "PORT" not in keys
    assert body["count"] == 5
