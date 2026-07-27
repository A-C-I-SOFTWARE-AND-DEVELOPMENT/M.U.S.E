"""Typed world and asset manifests for AAA game production."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AssetManifestEntry:
    asset_id: str
    category: str
    format: str
    path: str
    provenance_ref: str
    validation_ref: str
    provider: str
    license: str
    previs_only: bool = False
    lod_levels: tuple[int, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssetManifest:
    project_id: str
    profile: str
    entries: tuple[AssetManifestEntry, ...]
    version: str = "1.0"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "project_id": self.project_id,
            "profile": self.profile,
            "entries": [asdict(e) for e in self.entries],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> AssetManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = tuple(
            AssetManifestEntry(**item) for item in data.get("entries", [])
        )
        return cls(
            project_id=data["project_id"],
            profile=data["profile"],
            entries=entries,
            version=data.get("version", "1.0"),
        )

    def by_category(self, category: str) -> tuple[AssetManifestEntry, ...]:
        return tuple(e for e in self.entries if e.category == category)


@dataclass(frozen=True)
class BiomeSpec:
    biome_id: str
    name: str
    climate: str
    elevation_range_m: tuple[float, float]
    vegetation_density: str
    water_coverage_pct: float
    creature_spawn_table: tuple[str, ...]
    mission_hooks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ZoneSpec:
    zone_id: str
    name: str
    biome_id: str
    bounds_km2: float
    streaming_cell: str
    hlod_layer: int
    pcg_graphs: tuple[str, ...] = ()
    data_layers: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldManifest:
    project_id: str
    profile: str
    engine: str
    engine_version: str
    world_name: str
    world_size_km2: float
    biomes: tuple[BiomeSpec, ...]
    zones: tuple[ZoneSpec, ...]
    world_partition: Mapping[str, Any]
    navigation_mesh: Mapping[str, Any]
    collision_profile: Mapping[str, Any]
    scalability_profile: str
    version: str = "1.0"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "project_id": self.project_id,
            "profile": self.profile,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "world_name": self.world_name,
            "world_size_km2": self.world_size_km2,
            "biomes": [asdict(b) for b in self.biomes],
            "zones": [asdict(z) for z in self.zones],
            "world_partition": dict(self.world_partition),
            "navigation_mesh": dict(self.navigation_mesh),
            "collision_profile": dict(self.collision_profile),
            "scalability_profile": self.scalability_profile,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> WorldManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            project_id=data["project_id"],
            profile=data["profile"],
            engine=data["engine"],
            engine_version=data["engine_version"],
            world_name=data["world_name"],
            world_size_km2=float(data["world_size_km2"]),
            biomes=tuple(BiomeSpec(**b) for b in data.get("biomes", [])),
            zones=tuple(ZoneSpec(**z) for z in data.get("zones", [])),
            world_partition=data.get("world_partition", {}),
            navigation_mesh=data.get("navigation_mesh", {}),
            collision_profile=data.get("collision_profile", {}),
            scalability_profile=data.get("scalability_profile", "default"),
            version=data.get("version", "1.0"),
        )


@dataclass(frozen=True)
class PipelineManifest:
    project_id: str
    title: str
    profile: str
    world_manifest_ref: str
    asset_manifest_ref: str
    creature_manifest_ref: str
    mission_manifest_ref: str
    audio_manifest_ref: str
    cinematic_manifest_ref: str
    checkpoint_ref: str
    provenance_index_ref: str
    acceptance_report_ref: str
    previs_sources: tuple[str, ...] = ()
    stages_completed: tuple[str, ...] = ()
    version: str = "1.0"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> PipelineManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


def decompose_brief(
    *,
    project_id: str,
    title: str,
    profile: str,
    setting: str,
    genre: str,
    creatures: Sequence[str] | None = None,
    biomes: Sequence[str] | None = None,
    engine: str = "unreal",
    engine_version: str = "5.6",
) -> tuple[WorldManifest, AssetManifest]:
    """Typed decomposition from a production brief into world + asset manifests."""

    from agent.studio.quality_profiles import load_quality_profile

    qp = load_quality_profile(profile)
    creature_names = tuple(creatures or ("apex_predator", "pack_hunter", "ambient_fauna"))
    biome_names = tuple(biomes or ("temperate_forest", "volcanic_highlands", "coastal_wetlands"))

    biome_specs = tuple(
        BiomeSpec(
            biome_id=f"biome_{i:02d}",
            name=name,
            climate="temperate" if "forest" in name else "extreme",
            elevation_range_m=(0.0, 2000.0),
            vegetation_density="dense" if qp.tier.value != "previz" else "sparse",
            water_coverage_pct=15.0,
            creature_spawn_table=creature_names,
            mission_hooks=(f"investigate_{name}", f"hunt_in_{name}"),
        )
        for i, name in enumerate(biome_names)
    )
    zone_specs = tuple(
        ZoneSpec(
            zone_id=f"zone_{i:02d}",
            name=f"{b.name}_hub",
            biome_id=b.biome_id,
            bounds_km2=4.0,
            streaming_cell=f"cell_{i:02d}",
            hlod_layer=0,
            pcg_graphs=("foliage_scatter", "rock_formation", "prop_placement"),
            data_layers=("gameplay", "audio", "vfx"),
        )
        for i, b in enumerate(biome_specs)
    )
    world = WorldManifest(
        project_id=project_id,
        profile=profile,
        engine=engine,
        engine_version=engine_version,
        world_name=title,
        world_size_km2=len(biome_specs) * 4.0,
        biomes=biome_specs,
        zones=zone_specs,
        world_partition={
            "enabled": qp.streaming.world_partition_enabled,
            "cell_size_meters": qp.streaming.cell_size_meters,
            "loading_range_meters": qp.streaming.loading_range_meters,
            "data_layer_count": qp.streaming.data_layer_count,
            "hlod_levels": qp.streaming.hlod_levels,
        },
        navigation_mesh={
            "agent_radius_cm": 42.0,
            "agent_height_cm": 192.0,
            "max_slope_degrees": 45.0,
            "cell_size_cm": 19.0,
        },
        collision_profile={
            "complex_per_poly": True,
            "simple_collision_fallback": True,
            "nav_mesh_generation": True,
        },
        scalability_profile=qp.name,
    )
    asset_entries: list[AssetManifestEntry] = []
    for creature in creature_names:
        asset_entries.append(
            AssetManifestEntry(
                asset_id=f"creature_{creature}",
                category="creature",
                format="fbx",
                path=f"Content/Creatures/{creature}/{creature}.fbx",
                provenance_ref=f"provenance/creature_{creature}.json",
                validation_ref=f"validation/creature_{creature}.json",
                provider="mesh3d",
                license="original",
                previs_only=False,
                lod_levels=(0, 1, 2, 3),
                tags=("skeletal", "nanite_fallback", creature),
            )
        )
    for biome in biome_specs:
        asset_entries.append(
            AssetManifestEntry(
                asset_id=f"terrain_{biome.biome_id}",
                category="terrain",
                format="heightmap",
                path=f"Content/World/{biome.biome_id}/heightmap.r16",
                provenance_ref=f"provenance/terrain_{biome.biome_id}.json",
                validation_ref=f"validation/terrain_{biome.biome_id}.json",
                provider="procedural",
                license="original",
                previs_only=False,
                tags=("terrain", "world_partition", biome.name),
            )
        )
    assets = AssetManifest(
        project_id=project_id,
        profile=profile,
        entries=tuple(asset_entries),
    )
    return world, assets


__all__ = [
    "AssetManifest",
    "AssetManifestEntry",
    "BiomeSpec",
    "PipelineManifest",
    "WorldManifest",
    "ZoneSpec",
    "decompose_brief",
]
