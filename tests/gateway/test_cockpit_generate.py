"""Tests for the cockpit prose generator (the local + all-brains chat wiring).

The bug being fixed: the cockpit responder never wired a generator, so every
reply was the mode envelope regardless of input or configured model. These
prove the chat path now actually calls a model — local first (free-first),
then the configured cloud/subscription brains.
"""

from __future__ import annotations

import json

import pytest

from gateway.cockpit import generate as gen


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _wire_ollama(monkeypatch, *, tags_payload, chat_payload, capture=None):
    def fake_urlopen(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/api/tags"):
            return _FakeResp(tags_payload)
        if url.endswith("/api/chat"):
            if capture is not None and req.data:
                capture.append(json.loads(req.data.decode()))
            return _FakeResp(chat_payload)
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(gen.urllib.request, "urlopen", fake_urlopen)


# ── Tier 1: local Ollama ───────────────────────────────────────────────────


def test_installed_chat_models_filters_embeddings(monkeypatch) -> None:
    _wire_ollama(
        monkeypatch,
        tags_payload={"models": [
            {"name": "qwen2.5:3b"},
            {"name": "nomic-embed-text:latest"},
            {"name": "bge-m3:latest"},
            {"name": "deepseek-r1:8b"},
        ]},
        chat_payload={},
    )
    assert gen.installed_chat_models("http://x") == ["qwen2.5:3b", "deepseek-r1:8b"]


def test_pick_model_prefers_installed_over_uninstalled_policy_tag(monkeypatch) -> None:
    # Policy prefers deepseek-r1:8b but only qwen2.5:3b is installed — the real
    # S23 case (RAM misdetect set an 8B default that was never pulled).
    monkeypatch.setattr(gen, "_policy_preferred_tags", lambda: ["deepseek-r1:8b"])
    _wire_ollama(monkeypatch, tags_payload={"models": [{"name": "qwen2.5:3b"}]}, chat_payload={})
    assert gen.pick_model("http://x") == "qwen2.5:3b"


def test_pick_model_uses_policy_tag_when_installed(monkeypatch) -> None:
    # DeepSeek-R1 pulled locally → policy preference is honored.
    monkeypatch.setattr(gen, "_policy_preferred_tags", lambda: ["deepseek-r1:8b"])
    _wire_ollama(
        monkeypatch,
        tags_payload={"models": [{"name": "qwen2.5:3b"}, {"name": "deepseek-r1:8b"}]},
        chat_payload={},
    )
    assert gen.pick_model("http://x") == "deepseek-r1:8b"


def test_local_generate_calls_model_with_persona_and_prompt(monkeypatch) -> None:
    monkeypatch.setattr(gen, "_policy_preferred_tags", lambda: [])
    captured: list[dict] = []
    _wire_ollama(
        monkeypatch,
        tags_payload={"models": [{"name": "qwen2.5:3b"}]},
        chat_payload={"message": {"content": "  Hello, I am JARVIS.  "}},
        capture=captured,
    )
    out = gen.local_generate("describe yourself", "PERSONA")
    assert out == "Hello, I am JARVIS."  # stripped real model text, not an envelope
    assert captured[0]["model"] == "qwen2.5:3b"
    roles = {m["role"]: m["content"] for m in captured[0]["messages"]}
    assert roles["system"] == "PERSONA"
    assert roles["user"] == "describe yourself"


# ── Free-first orchestration: local → cloud → raise ─────────────────────────


def test_default_prefers_local(monkeypatch) -> None:
    monkeypatch.setattr(gen, "local_generate", lambda p, s: "LOCAL")
    monkeypatch.setattr(gen, "policy_generate", lambda p, s: "CLOUD")
    assert gen.default_prose_generator("hi", "persona") == "LOCAL"


def test_default_falls_back_to_cloud_when_no_local(monkeypatch) -> None:
    def no_local(p, s):
        raise RuntimeError("no local Ollama chat model installed")

    monkeypatch.setattr(gen, "local_generate", no_local)
    monkeypatch.setattr(gen, "policy_generate", lambda p, s: "CLOUD-DEEPSEEK")
    assert gen.default_prose_generator("hi", "persona") == "CLOUD-DEEPSEEK"


def test_default_raises_when_all_tiers_fail(monkeypatch) -> None:
    def boom_local(p, s):
        raise RuntimeError("no local model")

    def boom_cloud(p, s):
        raise RuntimeError("no provider configured")

    monkeypatch.setattr(gen, "local_generate", boom_local)
    monkeypatch.setattr(gen, "policy_generate", boom_cloud)
    with pytest.raises(RuntimeError):
        gen.default_prose_generator("hi", "persona")


# ── End-to-end: a wired generator's text becomes the chat body ──────────────


def test_responder_uses_generator_output() -> None:
    from gateway.cockpit.agent import jarvis_responder

    chunks = list(
        jarvis_responder("anything", [], generate=lambda p, persona: f"REPLY<{p}>")
    )
    bodies = [c for c in chunks if c.get("type") == "body"]
    assert bodies and bodies[0]["text"] == "REPLY<anything>"
