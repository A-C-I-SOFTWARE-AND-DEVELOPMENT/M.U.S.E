"""Tests for the unified headless login orchestrator."""

from __future__ import annotations

import argparse

import muse_cli.auth_commands as ac


def test_unified_flow_walks_providers_and_configures(monkeypatch):
    calls = []
    monkeypatch.setattr(ac, "auth_add_command", lambda args: calls.append(args.provider))
    configured = {"n": 0}
    monkeypatch.setattr(ac, "_configure_openai_dual_entity_defaults", lambda: configured.__setitem__("n", configured["n"] + 1))
    monkeypatch.setattr(ac, "_capture_claude_code_token", lambda: None)

    ac.headless_login_command(argparse.Namespace(provider=None))

    assert calls == ["openai-codex", "anthropic"]
    # Codex login configures the GPT/Codex dual entity exactly once.
    assert configured["n"] == 1


def test_unified_flow_continues_when_one_provider_fails(monkeypatch):
    def _add(args):
        if args.provider == "openai-codex":
            raise SystemExit("device code timeout")

    monkeypatch.setattr(ac, "auth_add_command", _add)
    monkeypatch.setattr(ac, "_configure_openai_dual_entity_defaults", lambda: None)
    monkeypatch.setattr(ac, "_capture_claude_code_token", lambda: None)

    # Should not raise — a failed provider is recorded and the rest proceed.
    ac.headless_login_command(argparse.Namespace(provider=None))


def test_single_provider_delegates(monkeypatch):
    seen = {}
    monkeypatch.setattr(ac, "auth_add_command", lambda args: seen.update(provider=args.provider, type=args.auth_type, manual=args.manual_paste))
    monkeypatch.setattr(ac, "_configure_openai_dual_entity_defaults", lambda: seen.update(configured=True))

    ac.headless_login_command(argparse.Namespace(provider="anthropic", manual_paste=True))

    assert seen["provider"] == "anthropic"
    assert seen["type"] == "oauth"
    assert seen["manual"] is True
    # Non-codex single login does not touch the dual-entity config.
    assert "configured" not in seen


def test_configure_dual_entity_writes_config(monkeypatch):
    cfg = {}
    monkeypatch.setattr(ac, "auth_add_command", lambda args: None)
    import muse_cli.config as config_mod

    monkeypatch.setattr(config_mod, "load_config", lambda: cfg)
    saved = {}
    monkeypatch.setattr(config_mod, "save_config", lambda c: saved.update(c))
    # Avoid network in get_codex_model_ids.
    monkeypatch.setattr("muse_cli.codex_models.get_codex_model_ids", lambda *a, **k: ["gpt-5.5", "gpt-5.3-codex"])

    ac._configure_openai_dual_entity_defaults()

    model = saved["model"]
    assert model["provider"] == "openai-codex"
    assert model["default"] == "gpt-5.5"
    assert model["chat_model"] == "gpt-5.5"
    assert model["codex_model"] == "gpt-5.3-codex"
    assert model["openai_dual_entity"] is True
