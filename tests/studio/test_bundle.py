"""Tests for the bundle producer."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.studio.adapters import ollama_local, free_providers
from agent.studio.bundle import build_index, make_bundle, make_bundle_dir
from agent.studio.types import (
    FilmBrief, GameBrief, ProjectManifest, Provider, Quality, StageResult,
)


def _fake_manifest(tmp_path: Path) -> ProjectManifest:
    """Hand-build a tiny film manifest with two real artifacts on disk."""
    wd = tmp_path / "film_workdir"
    wd.mkdir()
    script = wd / "script.md"
    script.write_text("FADE IN:\n\nINT. ROOM - DAY\n\nA character speaks.\n")
    art = wd / "concept.png"
    art.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)
    return ProjectManifest(
        kind="film", title="Test Title", workdir=wd, quality=Quality.DRAFT,
        stages=[
            StageResult(stage="script", provider=Provider.OLLAMA_LOCAL,
                        status="ok", artifacts=[str(script)], duration_s=1.0,
                        notes="42 chars"),
            StageResult(stage="concept_art", provider=Provider.FLUX_PRO,
                        status="ok", artifacts=[str(art)], duration_s=2.5),
        ],
        total_cost_usd=0.0, total_duration_s=3.5,
    )


def test_index_classifies_artifacts(tmp_path: Path):
    m = _fake_manifest(tmp_path)
    idx = build_index(m)
    assert idx["schema"] == "axiom.studio.bundle/1"
    assert idx["totals"]["artifacts"] == 2
    kinds = idx["totals"]["by_kind"]
    assert kinds["text"] == 1
    assert kinds["image"] == 1
    for a in idx["artifacts"]:
        assert len(a["sha256"]) == 64
        assert a["size"] > 0


def test_index_descends_into_engine_dirs(tmp_path: Path):
    """Engine project artifacts are directories — they must be walked."""
    wd = tmp_path / "game"
    wd.mkdir()
    proj = wd / "ue5_project"
    proj.mkdir()
    (proj / "Project.uproject").write_text("{\"FileVersion\":3}")
    (proj / "README.md").write_text("# game")
    m = ProjectManifest(
        kind="game", title="G", workdir=wd, quality=Quality.DRAFT,
        stages=[StageResult(stage="engine_project", provider=Provider.UE5,
                            status="ok", artifacts=[str(proj)])],
    )
    idx = build_index(m)
    assert idx["totals"]["artifacts"] == 2


def test_make_bundle_creates_zip_with_layout(tmp_path: Path):
    m = _fake_manifest(tmp_path)
    bundle = make_bundle(m)
    assert bundle.exists()
    assert bundle.suffix == ".zip"
    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
        assert "manifest.txt" in names
        assert "index.json" in names
        assert "README.md" in names
        assert "artifacts/script/script.md" in names
        assert "artifacts/concept_art/concept.png" in names
        idx = json.loads(zf.read("index.json"))
        assert idx["title"] == "Test Title"
        assert idx["kind"] == "film"


def test_make_bundle_dir_creates_layout(tmp_path: Path):
    m = _fake_manifest(tmp_path)
    out = make_bundle_dir(m, out_dir=tmp_path / "out")
    assert (out / "manifest.txt").exists()
    assert (out / "index.json").exists()
    assert (out / "README.md").exists()
    assert (out / "artifacts" / "script" / "script.md").exists()
    assert (out / "artifacts" / "concept_art" / "concept.png").exists()
    idx = json.loads((out / "index.json").read_text())
    assert idx["totals"]["artifacts"] == 2


def test_bundle_skips_missing_artifacts(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    m = ProjectManifest(
        kind="film", title="X", workdir=wd, quality=Quality.DRAFT,
        stages=[StageResult(stage="script", provider=Provider.OLLAMA_LOCAL,
                            status="failed",
                            artifacts=[str(wd / "nonexistent.md")])],
    )
    bundle = make_bundle(m)
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        assert "manifest.txt" in names
        # No artifacts/script/ entries since file doesn't exist
        assert not any(n.startswith("artifacts/script/") for n in names)


def test_full_orchestrator_to_bundle_e2e(tmp_path: Path):
    """End-to-end: produce_film(...) → make_bundle(...) yields a real zip."""
    from agent.studio import StudioOrchestrator, FilmBrief
    with patch.object(ollama_local, "_ollama_available", return_value=True), \
         patch.object(ollama_local, "_ollama_chat",
                      return_value="FADE IN:\n\nINT. ROOM - DAY\n\nReal scene text.\n"), \
         patch.object(free_providers, "_pollinations_available", return_value=False), \
         patch.object(free_providers, "_edge_tts_available", return_value=False):
        orch = StudioOrchestrator(root=tmp_path)
        manifest = orch.produce_film(FilmBrief(
            title="E2E Film", logline="A test bundle.", runtime_min=10,
        ))
        bundle = make_bundle(manifest)
        assert bundle.exists()
        # Bundle is at least a few KB (manifest + index + at least one real artifact)
        assert bundle.stat().st_size > 500
        with zipfile.ZipFile(bundle) as zf:
            idx = json.loads(zf.read("index.json"))
            assert idx["title"] == "E2E Film"
            assert idx["totals"]["artifacts"] >= 2  # at least script + shot_list
