"""High-fidelity AAA game production pipeline orchestrator."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.studio.acceptance import AcceptanceReport, evaluate_acceptance
from agent.studio.blender_contract import (
    build_creature_blender_contract,
    build_environment_blender_contract,
    generate_blender_script,
)
from agent.studio.checkpoints import (
    PipelineCheckpoint,
    PipelineStage,
    begin_stage,
    complete_stage,
    create_checkpoint,
    fail_stage,
)
from agent.studio.creature_specs import build_creature_manifests
from agent.studio.gates import GateResult, build_gates_for_profile, evaluate_all_gates, gates_passed
from agent.studio.manifests import (
    AssetManifest,
    PipelineManifest,
    WorldManifest,
    decompose_brief,
    materialize_stub_asset_entry,
    resolve_manifest_entry_path,
)
from agent.studio.provenance import AssetProvenance, sha256_file
from agent.studio.provider_config import build_provider_config, slot_manifest_entry
from agent.studio.quality_profiles import QualityProfile, load_quality_profile
from agent.studio.ue5_generator import generate_ue5_project
from agent.studio.world_specs import WorldSystemsManifest, build_world_systems


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "game"


@dataclass(frozen=True)
class AAAPipelineBrief:
    title: str
    genre: str
    setting: str
    core_loop: str
    profile: str = "high_fidelity"
    project_id: str = ""
    engine: str = "unreal"
    engine_version: str = "5.6"
    creatures: tuple[str, ...] = ("apex_predator", "pack_hunter", "ambient_fauna")
    biomes: tuple[str, ...] = ("temperate_forest", "volcanic_highlands", "coastal_wetlands")
    art_style: str = "stylized realism"
    offline: bool = False


@dataclass
class AAAPipelineResult:
    project_id: str
    root: Path
    profile: str
    checkpoint: PipelineCheckpoint
    pipeline_manifest: PipelineManifest
    world_manifest: WorldManifest
    asset_manifest: AssetManifest
    world_systems: WorldSystemsManifest
    acceptance_report: AcceptanceReport
    gates_passed: bool
    stages_failed: tuple[str, ...]
    total_cost_usd: float
    duration_s: float


def _load_gate_results(project_root: Path) -> tuple[GateResult, ...]:
    gate_report = project_root / "validation" / "gate_report.json"
    if not gate_report.is_file():
        return ()
    data = json.loads(gate_report.read_text(encoding="utf-8"))
    return tuple(
        GateResult(
            passed=item.get("passed", False),
            gate=item.get("gate", ""),
            reason=item.get("reason", ""),
            failures=tuple(item.get("failures", [])),
        )
        for item in data.get("gates", [])
    )


class AAAPipeline:
    """Evidence-driven high-fidelity game production pipeline."""

    PREVIS_SOURCES = ("lingbot/reactor", "google/veo-3")

    def __init__(self, root: Path, *, resume: bool = True) -> None:
        self.root = Path(root)
        self.resume = resume

    def run(self, brief: AAAPipelineBrief) -> AAAPipelineResult:
        t0 = time.perf_counter()
        project_id = brief.project_id or _slug(brief.title)
        project_root = self.root / project_id
        project_root.mkdir(parents=True, exist_ok=True)

        profile = load_quality_profile(brief.profile)
        checkpoint = PipelineCheckpoint.load(project_root) if self.resume else None
        if checkpoint is None:
            checkpoint = create_checkpoint(project_id, brief.profile)

        stages_failed: list[str] = []
        total_cost = 0.0
        provider_config = build_provider_config(brief.profile, offline=brief.offline)
        gate_results: tuple[Any, ...] = ()

        if not checkpoint.is_stage_complete(PipelineStage.DECOMPOSE):
            begin_stage(checkpoint, PipelineStage.DECOMPOSE)
            world, assets = decompose_brief(
                project_id=project_id,
                title=brief.title,
                profile=brief.profile,
                setting=brief.setting,
                genre=brief.genre,
                creatures=brief.creatures,
                biomes=brief.biomes,
                engine=brief.engine,
                engine_version=brief.engine_version,
            )
            world.write(project_root / "manifests" / "world_manifest.json")
            assets.write(project_root / "manifests" / "asset_manifest.json")
            complete_stage(
                checkpoint,
                PipelineStage.DECOMPOSE,
                [
                    str(project_root / "manifests" / "world_manifest.json"),
                    str(project_root / "manifests" / "asset_manifest.json"),
                ],
            )
        else:
            world = WorldManifest.load(project_root / "manifests" / "world_manifest.json")
            assets = AssetManifest.load(project_root / "manifests" / "asset_manifest.json")

        if not checkpoint.is_stage_complete(PipelineStage.PREVIS):
            begin_stage(checkpoint, PipelineStage.PREVIS)
            previs_dir = project_root / "previs"
            previs_dir.mkdir(parents=True, exist_ok=True)
            previs_manifest = {
                "authoritative": False,
                "sources": list(self.PREVIS_SOURCES),
                "note": "LingBot/Reactor previs is non-authoritative visual reference only.",
                "slots": [
                    slot_manifest_entry(s)
                    for s in provider_config.slots
                    if s.capability == "previs" or s.previs_only
                ],
            }
            previs_path = previs_dir / "previs_manifest.json"
            previs_path.write_text(json.dumps(previs_manifest, indent=2), encoding="utf-8")
            complete_stage(checkpoint, PipelineStage.PREVIS, [str(previs_path)])

        if not checkpoint.is_stage_complete(PipelineStage.WORLD_SYSTEMS):
            begin_stage(checkpoint, PipelineStage.WORLD_SYSTEMS)
            zone_ids = tuple(z.zone_id for z in world.zones)
            systems = build_world_systems(
                project_id, zone_ids, brief.creatures, profile=brief.profile
            )
            systems_path = project_root / "manifests" / "world_systems.json"
            systems.write(systems_path)
            mission_path = project_root / "manifests" / "mission_manifest.json"
            mission_path.write_text(
                json.dumps([asdict(m) for m in systems.missions], indent=2),
                encoding="utf-8",
            )
            audio_path = project_root / "manifests" / "audio_manifest.json"
            audio_path.write_text(
                json.dumps([asdict(a) for a in systems.audio], indent=2),
                encoding="utf-8",
            )
            cinematic_path = project_root / "manifests" / "cinematic_manifest.json"
            cinematic_path.write_text(
                json.dumps([asdict(c) for c in systems.cinematics], indent=2),
                encoding="utf-8",
            )
            complete_stage(
                checkpoint,
                PipelineStage.WORLD_SYSTEMS,
                [str(systems_path), str(mission_path), str(audio_path), str(cinematic_path)],
            )
        else:
            systems = WorldSystemsManifest.load(
                project_root / "manifests" / "world_systems.json"
            )

        if not checkpoint.is_stage_complete(PipelineStage.CREATURE_RIG):
            begin_stage(checkpoint, PipelineStage.CREATURE_RIG)
            creatures = build_creature_manifests(brief.creatures, profile=brief.profile)
            creature_dir = project_root / "manifests" / "creatures"
            creature_dir.mkdir(parents=True, exist_ok=True)
            creature_paths: list[str] = []
            for creature in creatures:
                path = creature_dir / f"{creature.creature_id}.json"
                creature.write(path)
                creature_paths.append(str(path))
            creature_index = creature_dir / "creature_manifest.json"
            creature_index.write_text(
                json.dumps([c.creature_id for c in creatures], indent=2),
                encoding="utf-8",
            )
            creature_paths.append(str(creature_index))
            complete_stage(checkpoint, PipelineStage.CREATURE_RIG, creature_paths)

        if not checkpoint.is_stage_complete(PipelineStage.BLENDER_POST):
            begin_stage(checkpoint, PipelineStage.BLENDER_POST)
            blender_dir = project_root / "blender"
            blender_dir.mkdir(parents=True, exist_ok=True)
            blender_paths: list[str] = []
            for creature_id in brief.creatures:
                contract = build_creature_blender_contract(creature_id)
                contract_path = blender_dir / f"{creature_id}_contract.json"
                contract.write(contract_path)
                script_path = blender_dir / f"{creature_id}_headless.py"
                script_path.write_text(generate_blender_script(contract), encoding="utf-8")
                blender_paths.extend([str(contract_path), str(script_path)])
            for biome in world.biomes:
                contract = build_environment_blender_contract(biome.biome_id)
                contract_path = blender_dir / f"{biome.biome_id}_contract.json"
                contract.write(contract_path)
                blender_paths.append(str(contract_path))
            complete_stage(checkpoint, PipelineStage.BLENDER_POST, blender_paths)

        if not checkpoint.is_stage_complete(PipelineStage.ASSET_GENERATION):
            begin_stage(checkpoint, PipelineStage.ASSET_GENERATION)
            assets_dir = project_root / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            provider_config.write(project_root / "manifests" / "provider_config.json")
            asset_gen_paths: list[str] = []
            materialized_entries: list[Any] = []
            for entry in assets.entries:
                slot = provider_config.pick(
                    "mesh3d" if entry.category == "creature" else "concept_art"
                )
                stub_relpath = f"assets/{entry.asset_id}.stub.json"
                if brief.offline:
                    manifest_entry = materialize_stub_asset_entry(
                        entry, stub_relpath=stub_relpath
                    )
                else:
                    manifest_entry = entry
                stub = {
                    "asset_id": entry.asset_id,
                    "provider": slot.provider_id if slot else "axiom/stub",
                    "previs_only": manifest_entry.previs_only,
                    "authoritative": manifest_entry.authoritative,
                    "offline": brief.offline,
                    "path": manifest_entry.path,
                    "license": manifest_entry.license,
                    "note": "Non-authoritative offline stub; not validated for commercial use.",
                }
                stub_path = assets_dir / f"{entry.asset_id}.stub.json"
                stub_path.write_text(json.dumps(stub, indent=2), encoding="utf-8")
                asset_gen_paths.append(str(stub_path))
                materialized_entries.append(manifest_entry)
                if slot:
                    total_cost += slot.est_cost_usd
            assets = assets.with_entries(tuple(materialized_entries))
            assets.write(project_root / "manifests" / "asset_manifest.json")
            complete_stage(checkpoint, PipelineStage.ASSET_GENERATION, asset_gen_paths)

        if not checkpoint.is_stage_complete(PipelineStage.UE5_SOURCE):
            begin_stage(checkpoint, PipelineStage.UE5_SOURCE)
            if brief.engine != "unreal":
                fail_stage(checkpoint, PipelineStage.UE5_SOURCE, f"engine {brief.engine} not supported for AAA UE5 source")
                stages_failed.append("ue5_source")
            else:
                ue_root = project_root / "ue5_project"
                written = generate_ue5_project(
                    ue_root,
                    title=brief.title,
                    engine_version=brief.engine_version,
                    profile=profile,
                    world_manifest=world,
                )
                complete_stage(checkpoint, PipelineStage.UE5_SOURCE, written)

        if not checkpoint.is_stage_complete(PipelineStage.PROVENANCE):
            begin_stage(checkpoint, PipelineStage.PROVENANCE)
            prov_dir = project_root / "provenance"
            prov_dir.mkdir(parents=True, exist_ok=True)
            prov_paths: list[str] = []
            index: dict[str, str] = {}
            for entry in assets.entries:
                stub_file = project_root / "assets" / f"{entry.asset_id}.stub.json"
                content_hash = sha256_file(stub_file) if stub_file.is_file() else "sha256:" + "0" * 64
                if brief.offline or not entry.authoritative:
                    prov = AssetProvenance(
                        asset_id=entry.asset_id,
                        content_hash=content_hash,
                        formats=("stub-json",),
                        creator="muse-aaa-pipeline",
                        generator=entry.provider,
                        source="generated",
                        license=entry.license,
                        allowed_uses=("private",),
                        safety_status="unverified",
                        prompt_ref=f"prompts/{entry.asset_id}.ref",
                    )
                else:
                    prov = AssetProvenance(
                        asset_id=entry.asset_id,
                        content_hash=content_hash,
                        formats=(entry.format,),
                        creator="muse-aaa-pipeline",
                        generator=entry.provider,
                        source="generated",
                        license=entry.license,
                        allowed_uses=("private",),
                        safety_status="unverified",
                        prompt_ref=f"prompts/{entry.asset_id}.ref",
                    )
                path = prov_dir / f"{entry.asset_id}.json"
                prov.write(path)
                prov_paths.append(str(path))
                index[entry.asset_id] = str(path)
            index_path = prov_dir / "provenance_index.json"
            index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
            prov_paths.append(str(index_path))
            complete_stage(checkpoint, PipelineStage.PROVENANCE, prov_paths)

        if not checkpoint.is_stage_complete(PipelineStage.VALIDATION):
            begin_stage(checkpoint, PipelineStage.VALIDATION)
            validation_dir = project_root / "validation"
            validation_dir.mkdir(parents=True, exist_ok=True)
            from agent.studio.asset_validation import write_asset_validation_record
            from agent.studio.game_verification import discover_engine

            asset_licenses = {e.asset_id: e.license for e in assets.entries}
            engine_status = discover_engine(brief.engine, brief.engine_version)
            cost_gate, hw_gate, lic_gate, owner_gate = build_gates_for_profile(
                brief.profile,
                current_cost_usd=total_cost,
                asset_licenses=asset_licenses,
                ue5_available=engine_status.available,
            )
            gate_results = evaluate_all_gates(
                cost=cost_gate,
                hardware=hw_gate,
                license_gate=lic_gate,
                owner=owner_gate,
                pending_action="paid_api_spend" if total_cost > 0 else "",
                additional_cost=0.0,
            )
            validation_paths: list[str] = []
            for entry in assets.entries:
                artifact_ok, artifact_reason = resolve_manifest_entry_path(entry, project_root)
                blocked_reason = ""
                failures: list[str] = []
                if brief.offline or not entry.authoritative:
                    blocked_reason = "offline_stub: non-authoritative placeholder; mesh not generated"
                    failures.append(blocked_reason)
                elif not artifact_ok:
                    blocked_reason = artifact_reason
                    failures.append(artifact_reason)
                record_path = validation_dir / f"{entry.asset_id}.json"
                write_asset_validation_record(
                    record_path,
                    asset_id=entry.asset_id,
                    passed=False,
                    blocked_reason=blocked_reason,
                    failures=tuple(failures),
                    offline=brief.offline,
                )
                validation_paths.append(str(record_path))
            validation_report = {
                "gates": [
                    asdict(g)
                    if hasattr(g, "__dataclass_fields__")
                    else {
                        "passed": g.passed,
                        "gate": g.gate,
                        "reason": g.reason,
                        "failures": list(g.failures),
                    }
                    for g in gate_results
                ],
                "profile": brief.profile,
                "offline": brief.offline,
                "gates_passed": gates_passed(gate_results),
            }
            val_path = validation_dir / "gate_report.json"
            val_path.write_text(json.dumps(validation_report, indent=2), encoding="utf-8")
            validation_paths.append(str(val_path))
            complete_stage(
                checkpoint,
                PipelineStage.VALIDATION,
                validation_paths,
                metadata={"gates_passed": gates_passed(gate_results)},
            )
        else:
            gate_results = _load_gate_results(project_root)

        if not checkpoint.is_stage_complete(PipelineStage.ACCEPTANCE):
            begin_stage(checkpoint, PipelineStage.ACCEPTANCE)
            license_failures: list[str] = []
            if brief.offline:
                license_failures.extend(
                    f"{entry.asset_id}:stub_non_commercial"
                    for entry in assets.entries
                    if not entry.authoritative
                )
            acceptance = evaluate_acceptance(
                project_id,
                brief.profile,
                performance_metrics={"frame_ms": 0, "draw_calls": 0, "gpu_memory_mb": 0},
                render_evidence_paths=() if brief.offline else None,
                license_failures=license_failures,
                offline=brief.offline,
            )
            acc_path = project_root / "reports" / "acceptance_report.json"
            acceptance.write(acc_path)
            complete_stage(checkpoint, PipelineStage.ACCEPTANCE, [str(acc_path)])

        acceptance = AcceptanceReport.load(project_root / "reports" / "acceptance_report.json")

        pipeline_manifest = PipelineManifest(
            project_id=project_id,
            title=brief.title,
            profile=brief.profile,
            world_manifest_ref="manifests/world_manifest.json",
            asset_manifest_ref="manifests/asset_manifest.json",
            creature_manifest_ref="manifests/creatures/creature_manifest.json",
            mission_manifest_ref="manifests/mission_manifest.json",
            audio_manifest_ref="manifests/audio_manifest.json",
            cinematic_manifest_ref="manifests/cinematic_manifest.json",
            checkpoint_ref="checkpoints/pipeline_checkpoint.json",
            provenance_index_ref="provenance/provenance_index.json",
            acceptance_report_ref="reports/acceptance_report.json",
            previs_sources=self.PREVIS_SOURCES,
            stages_completed=checkpoint.completed_stages(),
        )
        pipeline_manifest.write(project_root / "pipeline_manifest.json")
        checkpoint.write(project_root)
        complete_stage(checkpoint, PipelineStage.COMPLETE, [str(project_root / "pipeline_manifest.json")])
        checkpoint.write(project_root)

        duration = time.perf_counter() - t0
        evaluated_gates_passed = (
            gates_passed(gate_results) if gate_results else False
        )
        return AAAPipelineResult(
            project_id=project_id,
            root=project_root,
            profile=brief.profile,
            checkpoint=checkpoint,
            pipeline_manifest=pipeline_manifest,
            world_manifest=world,
            asset_manifest=assets,
            world_systems=systems,
            acceptance_report=acceptance,
            gates_passed=evaluated_gates_passed,
            stages_failed=tuple(stages_failed),
            total_cost_usd=total_cost,
            duration_s=duration,
        )


def run_creature_hunting_pipeline(
    root: Path,
    *,
    title: str = "Frontier Hunt",
    offline: bool = True,
) -> AAAPipelineResult:
    """Representative creature-hunting open-world brief for verification."""

    brief = AAAPipelineBrief(
        title=title,
        genre="creature-hunting action-RPG",
        setting="vast frontier with diverse biomes and apex predators",
        core_loop="track, hunt, craft, explore",
        profile="aaa_benchmark" if not offline else "high_fidelity",
        creatures=("apex_serpent", "pack_wolf", "sky_raptor"),
        biomes=("ancient_forest", "volcanic_caldera", "misty_coast"),
        offline=offline,
    )
    return AAAPipeline(root).run(brief)


__all__ = [
    "AAAPipeline",
    "AAAPipelineBrief",
    "AAAPipelineResult",
    "run_creature_hunting_pipeline",
]
