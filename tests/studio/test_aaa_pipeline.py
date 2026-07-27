"""Tests for the AAA high-fidelity game production pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.studio.aaa_pipeline import (
    AAAPipeline,
    AAAPipelineBrief,
    run_creature_hunting_pipeline,
)
from agent.studio.acceptance import evaluate_acceptance
from agent.studio.checkpoints import PipelineCheckpoint, PipelineStage
from agent.studio.creature_specs import REQUIRED_CREATURE_ANIMATIONS, build_creature_manifest
from agent.studio.gates import CostGate, LicenseGate, evaluate_all_gates, gates_passed
from agent.studio.manifests import decompose_brief
from agent.studio.quality_profiles import (
    AAA_BENCHMARK_PROFILE,
    HIGH_FIDELITY_PROFILE,
    load_quality_profile,
)
from agent.studio.ue5_generator import generate_ue5_project


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("AXIOM_STUDIO_OFFLINE", "1")


@pytest.fixture
def pipeline_root(tmp_path):
    return tmp_path / "aaa"


def test_quality_profile_has_explicit_budgets():
    profile = load_quality_profile("aaa_benchmark")
    assert profile.polygon.hero_creature_triangles >= 500_000
    assert profile.texture.hero_albedo_max >= 4096
    assert profile.performance.target_frame_ms <= 16.67
    assert profile.lighting.lumen_enabled is True
    assert profile.streaming.world_partition_enabled is True
    assert profile.requires_ue_render_evidence is True


def test_decompose_brief_produces_world_and_asset_manifests():
    world, assets = decompose_brief(
        project_id="test-project",
        title="Test Hunt",
        profile="high_fidelity",
        setting="frontier",
        genre="action-RPG",
        creatures=("apex_beast",),
        biomes=("forest",),
    )
    assert world.project_id == "test-project"
    assert len(world.biomes) == 1
    assert len(world.zones) == 1
    assert world.world_partition["enabled"] is True
    assert any(e.category == "creature" for e in assets.entries)


def test_creature_manifest_includes_required_animations():
    creature = build_creature_manifest("apex_beast", profile="high_fidelity")
    missing = creature.missing_required_animations()
    assert not missing, f"missing animations: {missing}"
    assert len(creature.required_animation_names()) >= len(REQUIRED_CREATURE_ANIMATIONS)


def test_ue5_generator_writes_substantive_project(tmp_path):
    world, _ = decompose_brief(
        project_id="ue5-test",
        title="Frontier Hunt",
        profile="high_fidelity",
        setting="frontier",
        genre="action-RPG",
    )
    profile = load_quality_profile("high_fidelity")
    written = generate_ue5_project(
        tmp_path / "ue5",
        title="Frontier Hunt",
        engine_version="5.6",
        profile=profile,
        world_manifest=world,
    )
    assert any(p.endswith(".uproject") for p in written)
    engine_ini = tmp_path / "ue5" / "Config" / "DefaultEngine.ini"
    assert engine_ini.is_file()
    content = engine_ini.read_text(encoding="utf-8")
    assert "r.Lumen.Enabled=True" in content
    assert "r.Nanite.ProjectEnabled=True" in content
    assert "GlobalDefaultGameMode=/Script/FrontierHunt.FrontierHuntGameMode" in content
    assert (tmp_path / "ue5" / "Config" / "WorldPartition.ini").is_file()
    assert (tmp_path / "ue5" / "Config" / "PCGGraphs.json").is_file()
    assert (tmp_path / "ue5" / "Source" / "FrontierHunt" / "FrontierHuntCreatureBase.h").is_file()


def test_cost_gate_fails_closed():
    gate = CostGate(max_estimated_cost_usd=0.0, current_cost_usd=1.0)
    ok, reason = gate.check()
    assert ok is False
    assert "cost gate blocked" in reason


def test_license_gate_fails_on_missing_license():
    gate = LicenseGate(
        required_licenses=("original",),
        asset_licenses={"asset_a": ""},
        commercial_use_required=True,
    )
    ok, failures = gate.check()
    assert ok is False
    assert any("missing_license" in f or "asset_a" in f for f in failures)


def test_acceptance_offline_does_not_claim_evidence():
    report = evaluate_acceptance(
        "proj",
        "aaa_benchmark",
        offline=True,
    )
    assert report.evidence_complete is False
    assert "benchmark" in report.benchmark_claim.lower() or report.benchmark_claim == ""


def test_aaa_pipeline_offline_creature_hunting(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    assert result.project_id
    assert (result.root / "pipeline_manifest.json").is_file()
    assert (result.root / "manifests" / "world_manifest.json").is_file()
    assert (result.root / "manifests" / "asset_manifest.json").is_file()
    assert (result.root / "checkpoints" / "pipeline_checkpoint.json").is_file()
    assert (result.root / "provenance" / "provenance_index.json").is_file()
    assert (result.root / "reports" / "acceptance_report.json").is_file()
    assert (result.root / "ue5_project").is_dir()
    assert not result.acceptance_report.evidence_complete
    assert "complete" in result.checkpoint.completed_stages()


def test_pipeline_checkpoint_resume(pipeline_root):
    brief = AAAPipelineBrief(
        title="Resume Test",
        genre="action-RPG",
        setting="test",
        core_loop="test",
        profile="high_fidelity",
        offline=True,
    )
    pipeline = AAAPipeline(pipeline_root)
    first = pipeline.run(brief)
    second = AAAPipeline(pipeline_root, resume=True).run(brief)
    assert first.project_id == second.project_id
    checkpoint = PipelineCheckpoint.load(first.root)
    assert checkpoint is not None
    assert checkpoint.is_stage_complete(PipelineStage.COMPLETE)


def test_previs_is_non_authoritative(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    previs = json.loads(
        (result.root / "previs" / "previs_manifest.json").read_text(encoding="utf-8")
    )
    assert previs["authoritative"] is False


def test_gates_evaluate_all(pipeline_root):
    from agent.studio.gates import HardwareGate, OwnerAuthorizationGate, build_gates_for_profile

    cost, hw, lic, owner = build_gates_for_profile(
        "high_fidelity",
        asset_licenses={"asset_a": "original"},
        ue5_available=False,
    )
    results = evaluate_all_gates(cost=cost, hardware=hw, license_gate=lic, owner=owner)
    assert len(results) >= 3


def test_game_foundry_ue5_has_scalability_config(tmp_path):
    from agent.studio.game_foundry import GameFoundry
    from agent.studio.types import GameProductionSpec

    spec = GameProductionSpec(
        title="Foundry Test",
        project_id="foundry-test",
        metadata={"quality_profile": "high_fidelity"},
    )
    manifest = GameFoundry(tmp_path).create(spec)
    uprojects = list(manifest.root.glob("*.uproject"))
    assert uprojects, "expected a .uproject file"
    assert (manifest.root / "Config" / "DefaultScalability.ini").is_file()


def test_offline_asset_manifest_references_existing_stub_files(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    manifest = json.loads(
        (result.root / "manifests" / "asset_manifest.json").read_text(encoding="utf-8")
    )
    for entry in manifest["entries"]:
        rel = entry["path"].lstrip("/")
        assert (result.root / rel).is_file(), f"missing artifact for {entry['asset_id']}"
        assert entry["format"] == "stub-json"
        assert entry["authoritative"] is False
        assert entry["previs_only"] is True
        assert entry["license"] == "stub-non-commercial"


def test_offline_quality_gate_not_overridden(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    report = result.acceptance_report
    assert report.quality_gate_passed is False
    assert any("missing_metric:" in failure for failure in report.failures)


def test_offline_stub_provenance_is_non_commercial(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    prov = json.loads(
        (result.root / "provenance" / "creature_apex_serpent.json").read_text(encoding="utf-8")
    )
    assert prov["source"] == "generated"
    assert prov["license"] == "stub-non-commercial"
    assert prov["safety_status"] == "unverified"
    assert prov["allowed_uses"] == ["private"]
    assert "commercial" not in prov["allowed_uses"]


def test_offline_gates_passed_reflects_gate_failures(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    gate_report = json.loads(
        (result.root / "validation" / "gate_report.json").read_text(encoding="utf-8")
    )
    assert gate_report["gates_passed"] is False
    assert result.gates_passed is False
    hardware = next(g for g in gate_report["gates"] if g["gate"] == "hardware")
    assert hardware["passed"] is False


def test_validation_refs_resolve_to_blocked_records(pipeline_root):
    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    manifest = json.loads(
        (result.root / "manifests" / "asset_manifest.json").read_text(encoding="utf-8")
    )
    for entry in manifest["entries"]:
        validation_path = result.root / entry["validation_ref"]
        assert validation_path.is_file(), entry["validation_ref"]
        record = json.loads(validation_path.read_text(encoding="utf-8"))
        assert record["passed"] is False
        assert record["blocked_reason"]
        assert record["authoritative"] is False


def test_verify_slice_catches_honesty_regressions(pipeline_root, tmp_path):
    from scripts.verify_slice import verify

    result = run_creature_hunting_pipeline(pipeline_root, offline=True)
    check = verify(result.root)
    assert check["ok"] is True
    assert not check["failures"]

    bad_root = tmp_path / "bad-project"
    bad_root.mkdir()
    for rel in (
        "manifests/asset_manifest.json",
        "validation/gate_report.json",
        "reports/acceptance_report.json",
    ):
        src = result.root / rel
        if src.is_file():
            dest = bad_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    asset_manifest = json.loads((bad_root / "manifests" / "asset_manifest.json").read_text())
    asset_manifest["entries"][0]["path"] = "Content/Creatures/missing.fbx"
    (bad_root / "manifests" / "asset_manifest.json").write_text(
        json.dumps(asset_manifest, indent=2), encoding="utf-8"
    )
    check = verify(bad_root)
    assert check["ok"] is False
    assert any("asset_path_missing" in failure for failure in check["failures"])
