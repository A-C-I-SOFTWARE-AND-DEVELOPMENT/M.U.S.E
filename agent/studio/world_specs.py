"""Terrain, foliage, water, atmosphere, VFX, mission, AI, audio, cinematic specs."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class TerrainSpec:
    zone_id: str
    heightmap_resolution: int
    material_layers: tuple[str, ...]
    nanite_enabled: bool
    virtual_texture: bool
    collision: str
    pcg_scatter_density: float


@dataclass(frozen=True)
class FoliageSpec:
    zone_id: str
    species: tuple[str, ...]
    instances_per_km2: int
    wind_response: bool
    pcg_graph: str
    cull_distance_m: float


@dataclass(frozen=True)
class WaterSpec:
    zone_id: str
    body_type: str
    simulation: str
    caustics: bool
    underwater_fog: bool
    swim_volume: bool


@dataclass(frozen=True)
class AtmosphereSpec:
    zone_id: str
    sky_model: str
    volumetric_clouds: bool
    fog_density: float
    time_of_day_curve: str
    weather_states: tuple[str, ...]


@dataclass(frozen=True)
class VfxSpec:
    vfx_id: str
    category: str
    gpu_particle_budget: int
    niagara_system: str
    collision_interaction: bool


@dataclass(frozen=True)
class MissionSpec:
    mission_id: str
    title: str
    type: str
    zone_id: str
    objectives: tuple[str, ...]
    rewards: tuple[str, ...]
    prerequisite_missions: tuple[str, ...] = ()
    creature_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class AiSpec:
    behavior_id: str
    creature_id: str
    states: tuple[str, ...]
    perception_range_m: float
    aggro_range_m: float
    pack_behavior: bool
    behavior_tree_path: str


@dataclass(frozen=True)
class AudioSpec:
    audio_id: str
    category: str
    format: str
    loop: bool
    attenuation_m: float
    meta_sound: bool
    spatialization: str


@dataclass(frozen=True)
class CinematicSpec:
    cinematic_id: str
    title: str
    duration_s: float
    sequencer_path: str
    camera_rigs: tuple[str, ...]
    required_creatures: tuple[str, ...]
    previs_source: str = ""


@dataclass(frozen=True)
class WorldSystemsManifest:
    project_id: str
    profile: str
    terrain: tuple[TerrainSpec, ...]
    foliage: tuple[FoliageSpec, ...]
    water: tuple[WaterSpec, ...]
    atmosphere: tuple[AtmosphereSpec, ...]
    vfx: tuple[VfxSpec, ...]
    missions: tuple[MissionSpec, ...]
    ai: tuple[AiSpec, ...]
    audio: tuple[AudioSpec, ...]
    cinematics: tuple[CinematicSpec, ...]
    version: str = "1.0"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "project_id": self.project_id,
            "profile": self.profile,
            "terrain": [asdict(t) for t in self.terrain],
            "foliage": [asdict(f) for f in self.foliage],
            "water": [asdict(w) for w in self.water],
            "atmosphere": [asdict(a) for a in self.atmosphere],
            "vfx": [asdict(v) for v in self.vfx],
            "missions": [asdict(m) for m in self.missions],
            "ai": [asdict(a) for a in self.ai],
            "audio": [asdict(a) for a in self.audio],
            "cinematics": [asdict(c) for c in self.cinematics],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> WorldSystemsManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            project_id=data["project_id"],
            profile=data["profile"],
            terrain=tuple(TerrainSpec(**t) for t in data.get("terrain", [])),
            foliage=tuple(FoliageSpec(**f) for f in data.get("foliage", [])),
            water=tuple(WaterSpec(**w) for w in data.get("water", [])),
            atmosphere=tuple(AtmosphereSpec(**a) for a in data.get("atmosphere", [])),
            vfx=tuple(VfxSpec(**v) for v in data.get("vfx", [])),
            missions=tuple(MissionSpec(**m) for m in data.get("missions", [])),
            ai=tuple(AiSpec(**a) for a in data.get("ai", [])),
            audio=tuple(AudioSpec(**a) for a in data.get("audio", [])),
            cinematics=tuple(CinematicSpec(**c) for c in data.get("cinematics", [])),
        )


def build_world_systems(
    project_id: str,
    zone_ids: Sequence[str],
    creature_ids: Sequence[str],
    *,
    profile: str = "high_fidelity",
) -> WorldSystemsManifest:
    from agent.studio.quality_profiles import load_quality_profile

    qp = load_quality_profile(profile)
    terrain = tuple(
        TerrainSpec(
            zone_id=z,
            heightmap_resolution=2048 if qp.tier.value == "previz" else 8192,
            material_layers=("grass", "rock", "dirt", "snow"),
            nanite_enabled=qp.material.require_nanite_fallback,
            virtual_texture=qp.texture.virtual_texture_pages > 0,
            collision="complex",
            pcg_scatter_density=qp.density.props_per_km2 / 1000.0,
        )
        for z in zone_ids
    )
    foliage = tuple(
        FoliageSpec(
            zone_id=z,
            species=("fern", "canopy_tree", "underbrush", "moss_patch"),
            instances_per_km2=qp.density.foliage_instances_per_km2,
            wind_response=True,
            pcg_graph="PCG_FoliageScatter",
            cull_distance_m=4096.0,
        )
        for z in zone_ids
    )
    water = tuple(
        WaterSpec(
            zone_id=z,
            body_type="river_and_lakes",
            simulation="single_layer",
            caustics=qp.lighting.lumen_enabled,
            underwater_fog=True,
            swim_volume=True,
        )
        for z in zone_ids
    )
    atmosphere = tuple(
        AtmosphereSpec(
            zone_id=z,
            sky_model="sky_atmosphere",
            volumetric_clouds=qp.lighting.volumetric_fog,
            fog_density=0.02,
            time_of_day_curve="TOD_Curve_Default",
            weather_states=("clear", "overcast", "rain", "storm"),
        )
        for z in zone_ids
    )
    vfx = (
        VfxSpec("vfx_hit_impact", "combat", 500, "NS_HitImpact", True),
        VfxSpec("vfx_environment_dust", "ambient", 200, "NS_DustMotes", False),
        VfxSpec("vfx_weather_rain", "weather", 2000, "NS_Rain", False),
        VfxSpec("vfx_creature_spawn", "creature", 300, "NS_CreatureSpawn", True),
    )
    missions = tuple(
        MissionSpec(
            mission_id=f"mission_hunt_{cid}",
            title=f"Hunt the {cid.replace('_', ' ').title()}",
            type="hunt",
            zone_id=zone_ids[i % len(zone_ids)] if zone_ids else "zone_00",
            objectives=("track_creature", "engage_combat", "carve_resources"),
            rewards=("crafting_material", "experience"),
            creature_targets=(cid,),
        )
        for i, cid in enumerate(creature_ids)
    )
    ai = tuple(
        AiSpec(
            behavior_id=f"ai_{cid}",
            creature_id=cid,
            states=("idle", "patrol", "alert", "combat", "flee", "dead"),
            perception_range_m=50.0,
            aggro_range_m=30.0,
            pack_behavior="pack" in cid,
            behavior_tree_path=f"Content/AI/BT_{cid}",
        )
        for cid in creature_ids
    )
    audio = (
        AudioSpec("audio_ambient_forest", "ambient", "wav", True, 5000.0, True, "binaural"),
        AudioSpec("audio_combat_impact", "sfx", "wav", False, 100.0, True, "object"),
        AudioSpec("audio_score_exploration", "music", "wav", True, 0.0, True, "non_spatial"),
        AudioSpec("audio_creature_roar", "sfx", "wav", False, 200.0, True, "object"),
    )
    cinematics = (
        CinematicSpec(
            cinematic_id="cin_intro",
            title="Arrival at the Frontier",
            duration_s=45.0,
            sequencer_path="Content/Cinematics/SEQ_Intro",
            camera_rigs=("crane", "dolly", "handheld"),
            required_creatures=creature_ids[:1] if creature_ids else (),
            previs_source="lingbot_previs/non_authoritative",
        ),
    )
    return WorldSystemsManifest(
        project_id=project_id,
        profile=profile,
        terrain=terrain,
        foliage=foliage,
        water=water,
        atmosphere=atmosphere,
        vfx=vfx,
        missions=missions,
        ai=ai,
        audio=audio,
        cinematics=cinematics,
    )


__all__ = [
    "AiSpec",
    "AtmosphereSpec",
    "AudioSpec",
    "CinematicSpec",
    "FoliageSpec",
    "MissionSpec",
    "TerrainSpec",
    "VfxSpec",
    "WaterSpec",
    "WorldSystemsManifest",
    "build_world_systems",
]
