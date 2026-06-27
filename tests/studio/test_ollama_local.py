"""Tests for the Ollama local-adapter wiring in Axiom Studio.

These tests do NOT require a live Ollama daemon — they mock the availability
probe and HTTP layer. A separate smoke script (benchmarks/bench_studio_local.py)
exercises a live daemon when present.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.studio.adapters import ollama_local
from agent.studio.adapters.base import default_registry
from agent.studio.types import Provider


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset Ollama availability probe cache between tests."""
    if hasattr(ollama_local._ollama_available, "_cache"):
        delattr(ollama_local._ollama_available, "_cache")
    yield


def test_local_adapters_register_six_capabilities():
    """Importing ollama_local must register all six local stages."""
    expected = {"script", "gdd", "world_bible",
                "dialogue_text", "gameplay_code", "shot_list"}
    have = {cap for cap, bucket in default_registry._by_capability.items()
            if any(a.provider == Provider.OLLAMA_LOCAL for a in bucket)}
    assert expected <= have, f"missing local adapters for {expected - have}"


def test_local_adapter_unavailable_when_daemon_down(tmp_path: Path):
    """If Ollama is unreachable, available() returns False — stub path used."""
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        ad = ollama_local.OllamaScriptAdapter()
        assert ad.available() is False
        result = ad.run("hello", tmp_path)
        assert result.status == "stubbed"
        assert result.est_cost_usd == 0.0


def test_local_adapter_priority_beats_openrouter(tmp_path: Path):
    """When Ollama is up, registry.pick('script') must select the local adapter."""
    with patch.object(ollama_local, "_ollama_available", return_value=True):
        picked = default_registry.pick("script")
        assert picked is not None
        assert picked.provider == Provider.OLLAMA_LOCAL, \
            f"expected local Ollama, got {picked.provider}"


def test_local_adapter_runs_real_path_when_available(tmp_path: Path):
    """Mock the HTTP call; verify a real artifact file is written."""
    fake_response = "FADE IN:\n\nINT. SHIP - NIGHT\n\nA captain stares at the void.\n"
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat", return_value=fake_response):
        ad = ollama_local.OllamaScriptAdapter()
        result = ad.run("Write a short scene.", tmp_path)
        assert result.status == "ok"
        assert result.est_cost_usd == 0.0
        assert len(result.artifacts) == 1
        artifact = Path(result.artifacts[0])
        assert artifact.exists()
        assert "FADE IN" in artifact.read_text(encoding="utf-8")


def test_world_bible_adapter_uses_gpt_oss_by_default(tmp_path: Path):
    captured = {}
    def fake_chat(model, system, user, **kw):
        captured["model"] = model
        captured["system"] = system
        return "# World Bible\n\n## Cosmology\n..."
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat", side_effect=fake_chat):
        ad = ollama_local.OllamaWorldBibleAdapter()
        result = ad.run("Build a world for a space opera.", tmp_path)
        assert result.status == "ok"
        assert captured["model"] == "gpt-oss:20b"
        assert "world-building" in captured["system"].lower()


def test_gameplay_code_adapter_picks_engine_idiom(tmp_path: Path):
    captured = {}
    def fake_chat(model, system, user, **kw):
        captured["system"] = system
        return "// player.h\nclass APlayer { };"
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat", side_effect=fake_chat):
        ad = ollama_local.OllamaGameplayCodeAdapter()
        for engine in ["ue5", "unity", "godot"]:
            ad.run("player controller", tmp_path, engine=engine)
            assert engine in captured["system"]


def test_dialogue_adapter_writes_jsonl(tmp_path: Path):
    fake = ('{"character":"HERO","emotion":"resolute","line":"Hold the line.",'
            '"tags":["cinematic"]}\n')
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat", return_value=fake):
        ad = ollama_local.OllamaDialogueAdapter()
        result = ad.run("HERO at the gate.", tmp_path)
        assert result.status == "ok"
        artifact = Path(result.artifacts[0])
        assert artifact.suffix == ".jsonl"
        # Validate at least one JSON line parses
        first_line = artifact.read_text(encoding="utf-8").strip().splitlines()[0]
        parsed = json.loads(first_line)
        assert parsed["character"] == "HERO"


def test_orchestrator_film_pipeline_uses_local_when_available(tmp_path: Path):
    """End-to-end: film pipeline routes shot_list through local adapter."""
    from agent.studio import StudioOrchestrator, FilmBrief
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat",
                      return_value="stub-text-for-test"):
        orch = StudioOrchestrator(root=tmp_path)
        manifest = orch.produce_film(FilmBrief(
            title="Test Film", logline="A test.", runtime_min=20,
        ))
        # Find the shot_list stage and confirm it ran on local
        shot_stages = [s for s in manifest.stages if s.stage == "shot_list"]
        assert shot_stages, "shot_list stage missing"
        assert shot_stages[0].provider == Provider.OLLAMA_LOCAL


def test_orchestrator_game_pipeline_routes_to_local_capabilities(tmp_path: Path):
    """Game pipeline must invoke gdd, world_bible, dialogue_text, gameplay_code."""
    from agent.studio import StudioOrchestrator, GameBrief
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat", return_value="stub"):
        orch = StudioOrchestrator(root=tmp_path)
        manifest = orch.produce_game(GameBrief(
            title="Test Game", genre="action-rpg", target="PC",
        ))
        stage_names = {s.stage for s in manifest.stages}
        assert "gdd" in stage_names
        assert "world_bible" in stage_names
        assert "dialogue_text" in stage_names
        assert "gameplay_code" in stage_names
