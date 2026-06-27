"""Tests for Axiom Studio orchestrator (stub-mode, no API keys required)."""
import os
import json
import pytest
from pathlib import Path

# Force stub mode for the whole test module
for k in [
    "OPENROUTER_API_KEY", "BFL_API_KEY", "GOOGLE_VEO_API_KEY",
    "OPENAI_API_KEY", "REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY",
    "SUNO_API_KEY", "GOOGLE_GENIE_API_KEY",
]:
    os.environ.pop(k, None)

from agent.studio import StudioOrchestrator, FilmBrief, GameBrief, Quality, Provider
from agent.studio.adapters.base import default_registry


@pytest.fixture
def studio(tmp_path):
    return StudioOrchestrator(root=tmp_path / "studio_out")


def test_registry_has_all_capabilities():
    expected = {"script", "concept_art", "video", "mesh3d", "voice",
                "music", "sfx", "world", "engine_project"}
    found = set(default_registry._by_capability.keys())
    missing = expected - found
    assert not missing, f"missing adapters: {missing}"


def test_film_pipeline_runs_end_to_end(studio):
    brief = FilmBrief(
        title="The Last Signal",
        logline="A radio engineer in 1962 hears a message from herself, 60 years later.",
        runtime_min=110,
        genre="sci-fi thriller",
        quality=Quality.PREVIZ,
        extra={"characters": ["Helena", "Older Helena", "Director Voss"],
               "sfx_cues": ["tape hiss", "morse code", "thunder roll"]},
    )
    m = studio.produce_film(brief)

    assert m.kind == "film"
    assert m.title == "The Last Signal"
    assert len(m.stages) >= 15  # script + shotlist + 20 art + 27+ scenes + voices + music + sfx + edl
    # Every stage either ran or stubbed
    bad = [s for s in m.stages if s.status not in ("ok", "stubbed")]
    assert not bad, f"failed stages: {[(s.stage, s.notes) for s in bad]}"
    # Manifest written
    assert (m.workdir / "manifest.txt").exists()


def test_game_pipeline_runs_end_to_end(studio):
    brief = GameBrief(
        title="Aetherbound",
        genre="action-RPG",
        target="PC/PS5",
        setting="post-magical-collapse Victorian London",
        core_loop="explore → contract → fight → bind aether → upgrade",
        art_style="painterly realism, Frostbite-tier",
        runtime_hours=40,
        quality=Quality.PREVIZ,
        engine=Provider.UE5,
        extra={
            "characters": ["Aria", "Cipher", "The Curator", "Father Holm"],
            "levels": ["Whitechapel Foundry", "The Aether Spire", "Drowned Court"],
        },
    )
    m = studio.produce_game(brief)

    assert m.kind == "game"
    assert len(m.stages) >= 20
    bad = [s for s in m.stages if s.status not in ("ok", "stubbed")]
    assert not bad, f"failed stages: {[(s.stage, s.notes) for s in bad]}"

    # Engine project scaffold actually wrote a uproject file
    engine_stage = next(s for s in m.stages if s.stage == "engine_project")
    assert engine_stage.status == "ok"
    uproject = Path(engine_stage.artifacts[0]) / "Project.uproject"
    assert uproject.exists()
    data = json.loads(uproject.read_text())
    assert data["EngineAssociation"] == "5.5"


def test_quality_levels_change_video_resolution(studio, tmp_path):
    brief = FilmBrief(title="Test", logline="x", runtime_min=4, quality=Quality.THEATRICAL)
    m = studio.produce_film(brief)
    # In stub mode, the resolution is recorded in the stage's stub manifest
    video_stages = [s for s in m.stages if s.stage == "video"]
    assert video_stages
    # Read first stub manifest and verify kwargs captured resolution
    art = Path(video_stages[0].artifacts[0])
    stub = json.loads(art.read_text())
    assert stub["kwargs"]["resolution"] == "4k"


def test_cost_estimate_aggregates(studio):
    brief = GameBrief(title="X", genre="action", quality=Quality.PREVIZ)
    m = studio.produce_game(brief)
    # In stub mode total cost is 0 (cost only accrues on real calls)
    assert m.total_cost_usd == 0.0
    # But each stage has a notes string
    assert all(s.notes for s in m.stages if s.status == "stubbed")


def test_manifest_summary_is_human_readable(studio):
    brief = FilmBrief(title="Demo", logline="x", runtime_min=4)
    m = studio.produce_film(brief)
    out = m.summary()
    assert "FILM: Demo" in out
    assert "stages:" in out
    assert "cost:" in out
