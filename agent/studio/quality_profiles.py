"""Explicit quality profiles for high-fidelity game production."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


class FidelityTier(str, Enum):
    PREVIZ = "previz"
    VERTICAL_SLICE = "vertical_slice"
    HIGH_FIDELITY = "high_fidelity"
    AAA_BENCHMARK = "aaa_benchmark"


@dataclass(frozen=True)
class PolygonBudget:
    hero_creature_triangles: int
    hero_creature_lod0: int
    hero_creature_lod3: int
    environment_prop_triangles: int
    terrain_chunk_triangles: int
    foliage_instance_budget: int
    max_draw_calls_per_frame: int
    max_skinned_meshes: int


@dataclass(frozen=True)
class TextureBudget:
    hero_albedo_max: int
    hero_normal_max: int
    hero_orm_max: int
    environment_albedo_max: int
    terrain_albedo_max: int
    max_texture_memory_mb: float
    virtual_texture_pages: int
    streaming_pool_mb: float


@dataclass(frozen=True)
class MaterialBudget:
    max_material_slots_per_mesh: int
    max_shader_instructions: int
    require_pbr_workflow: bool
    require_nanite_fallback: bool
    max_blend_layers: int
    decal_budget_per_zone: int


@dataclass(frozen=True)
class AnimationBudget:
    skeleton_bone_count: int
    max_blend_shapes: int
    animation_clip_count_creature: int
    max_simultaneous_anim_layers: int
    motion_matching_database_mb: float
    ik_chain_depth: int
    facial_blend_shape_count: int


@dataclass(frozen=True)
class PerformanceBudget:
    target_frame_ms: float
    target_frame_ms_worst_case: float
    gpu_memory_mb: float
    cpu_budget_ms: float
    gpu_budget_ms: float
    streaming_cell_load_ms: float
    max_active_actors: int
    max_physics_bodies: int
    max_particle_systems: int


@dataclass(frozen=True)
class LightingBudget:
    lumen_enabled: bool
    virtual_shadow_maps: bool
    max_local_lights: int
    max_shadow_casting_lights: int
    gi_quality: str
    reflection_quality: str
    volumetric_fog: bool
    sky_atmosphere: bool
    exposure_mode: str


@dataclass(frozen=True)
class StreamingBudget:
    world_partition_enabled: bool
    cell_size_meters: float
    loading_range_meters: float
    streaming_source_count: int
    hlod_levels: int
    data_layer_count: int
    max_concurrent_loads: int
    memory_budget_mb: float


@dataclass(frozen=True)
class AssetDensityBudget:
    creatures_per_km2: int
    props_per_km2: int
    foliage_instances_per_km2: int
    destructibles_per_km2: int
    audio_sources_per_km2: int
    npc_spawn_points_per_km2: int
    mission_markers_per_km2: int


@dataclass(frozen=True)
class QualityProfile:
    tier: FidelityTier
    name: str
    description: str
    polygon: PolygonBudget
    texture: TextureBudget
    material: MaterialBudget
    animation: AnimationBudget
    performance: PerformanceBudget
    lighting: LightingBudget
    streaming: StreamingBudget
    density: AssetDensityBudget
    benchmark_reference: str = ""
    requires_ue_render_evidence: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate_metrics(self, metrics: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
        failures: list[str] = []
        checks = (
            ("frame_ms", self.performance.target_frame_ms_worst_case, "<="),
            ("draw_calls", self.polygon.max_draw_calls_per_frame, "<="),
            ("gpu_memory_mb", self.performance.gpu_memory_mb, "<="),
            ("hero_triangles", self.polygon.hero_creature_triangles, "<="),
            ("texture_memory_mb", self.texture.max_texture_memory_mb, "<="),
        )
        for key, limit, op in checks:
            value = metrics.get(key)
            if value is None:
                failures.append(f"missing_metric:{key}")
                continue
            if op == "<=" and float(value) > float(limit):
                failures.append(f"{key}_over_budget")
        return (not failures, tuple(failures))


PREVIZ_PROFILE = QualityProfile(
    tier=FidelityTier.PREVIZ,
    name="previz",
    description="Fast iteration; stub-safe; no render evidence required.",
    polygon=PolygonBudget(
        hero_creature_triangles=50_000,
        hero_creature_lod0=50_000,
        hero_creature_lod3=5_000,
        environment_prop_triangles=5_000,
        terrain_chunk_triangles=100_000,
        foliage_instance_budget=10_000,
        max_draw_calls_per_frame=500,
        max_skinned_meshes=10,
    ),
    texture=TextureBudget(
        hero_albedo_max=1024,
        hero_normal_max=1024,
        hero_orm_max=1024,
        environment_albedo_max=512,
        terrain_albedo_max=2048,
        max_texture_memory_mb=512.0,
        virtual_texture_pages=0,
        streaming_pool_mb=256.0,
    ),
    material=MaterialBudget(
        max_material_slots_per_mesh=4,
        max_shader_instructions=64,
        require_pbr_workflow=True,
        require_nanite_fallback=False,
        max_blend_layers=2,
        decal_budget_per_zone=10,
    ),
    animation=AnimationBudget(
        skeleton_bone_count=64,
        max_blend_shapes=8,
        animation_clip_count_creature=8,
        max_simultaneous_anim_layers=2,
        motion_matching_database_mb=16.0,
        ik_chain_depth=2,
        facial_blend_shape_count=0,
    ),
    performance=PerformanceBudget(
        target_frame_ms=33.33,
        target_frame_ms_worst_case=50.0,
        gpu_memory_mb=2048.0,
        cpu_budget_ms=20.0,
        gpu_budget_ms=28.0,
        streaming_cell_load_ms=500.0,
        max_active_actors=500,
        max_physics_bodies=100,
        max_particle_systems=20,
    ),
    lighting=LightingBudget(
        lumen_enabled=False,
        virtual_shadow_maps=False,
        max_local_lights=8,
        max_shadow_casting_lights=4,
        gi_quality="low",
        reflection_quality="screen_space",
        volumetric_fog=False,
        sky_atmosphere=True,
        exposure_mode="auto",
    ),
    streaming=StreamingBudget(
        world_partition_enabled=False,
        cell_size_meters=5120.0,
        loading_range_meters=5120.0,
        streaming_source_count=1,
        hlod_levels=2,
        data_layer_count=4,
        max_concurrent_loads=2,
        memory_budget_mb=512.0,
    ),
    density=AssetDensityBudget(
        creatures_per_km2=2,
        props_per_km2=50,
        foliage_instances_per_km2=500,
        destructibles_per_km2=5,
        audio_sources_per_km2=10,
        npc_spawn_points_per_km2=5,
        mission_markers_per_km2=2,
    ),
)

HIGH_FIDELITY_PROFILE = QualityProfile(
    tier=FidelityTier.HIGH_FIDELITY,
    name="high_fidelity",
    description="Production-target UE5 open-world with Nanite, Lumen, World Partition.",
    polygon=PolygonBudget(
        hero_creature_triangles=500_000,
        hero_creature_lod0=500_000,
        hero_creature_lod3=25_000,
        environment_prop_triangles=50_000,
        terrain_chunk_triangles=2_000_000,
        foliage_instance_budget=500_000,
        max_draw_calls_per_frame=3000,
        max_skinned_meshes=40,
    ),
    texture=TextureBudget(
        hero_albedo_max=4096,
        hero_normal_max=4096,
        hero_orm_max=4096,
        environment_albedo_max=2048,
        terrain_albedo_max=8192,
        max_texture_memory_mb=4096.0,
        virtual_texture_pages=512,
        streaming_pool_mb=2048.0,
    ),
    material=MaterialBudget(
        max_material_slots_per_mesh=8,
        max_shader_instructions=256,
        require_pbr_workflow=True,
        require_nanite_fallback=True,
        max_blend_layers=4,
        decal_budget_per_zone=50,
    ),
    animation=AnimationBudget(
        skeleton_bone_count=120,
        max_blend_shapes=32,
        animation_clip_count_creature=48,
        max_simultaneous_anim_layers=4,
        motion_matching_database_mb=128.0,
        ik_chain_depth=4,
        facial_blend_shape_count=52,
    ),
    performance=PerformanceBudget(
        target_frame_ms=16.67,
        target_frame_ms_worst_case=20.0,
        gpu_memory_mb=8192.0,
        cpu_budget_ms=8.0,
        gpu_budget_ms=14.0,
        streaming_cell_load_ms=100.0,
        max_active_actors=5000,
        max_physics_bodies=500,
        max_particle_systems=100,
    ),
    lighting=LightingBudget(
        lumen_enabled=True,
        virtual_shadow_maps=True,
        max_local_lights=32,
        max_shadow_casting_lights=16,
        gi_quality="high",
        reflection_quality="lumen",
        volumetric_fog=True,
        sky_atmosphere=True,
        exposure_mode="manual",
    ),
    streaming=StreamingBudget(
        world_partition_enabled=True,
        cell_size_meters=256.0,
        loading_range_meters=2048.0,
        streaming_source_count=4,
        hlod_levels=4,
        data_layer_count=16,
        max_concurrent_loads=8,
        memory_budget_mb=4096.0,
    ),
    density=AssetDensityBudget(
        creatures_per_km2=8,
        props_per_km2=500,
        foliage_instances_per_km2=50_000,
        destructibles_per_km2=50,
        audio_sources_per_km2=100,
        npc_spawn_points_per_km2=20,
        mission_markers_per_km2=10,
    ),
    benchmark_reference="open-world action-RPG biome density (quality benchmark only)",
    requires_ue_render_evidence=True,
)

AAA_BENCHMARK_PROFILE = QualityProfile(
    tier=FidelityTier.AAA_BENCHMARK,
    name="aaa_benchmark",
    description="Maximum fidelity tier; all gates require measured UE render evidence.",
    polygon=PolygonBudget(
        hero_creature_triangles=1_000_000,
        hero_creature_lod0=1_000_000,
        hero_creature_lod3=50_000,
        environment_prop_triangles=100_000,
        terrain_chunk_triangles=5_000_000,
        foliage_instance_budget=1_000_000,
        max_draw_calls_per_frame=5000,
        max_skinned_meshes=60,
    ),
    texture=TextureBudget(
        hero_albedo_max=8192,
        hero_normal_max=8192,
        hero_orm_max=8192,
        environment_albedo_max=4096,
        terrain_albedo_max=8192,
        max_texture_memory_mb=8192.0,
        virtual_texture_pages=1024,
        streaming_pool_mb=4096.0,
    ),
    material=MaterialBudget(
        max_material_slots_per_mesh=12,
        max_shader_instructions=512,
        require_pbr_workflow=True,
        require_nanite_fallback=True,
        max_blend_layers=6,
        decal_budget_per_zone=100,
    ),
    animation=AnimationBudget(
        skeleton_bone_count=180,
        max_blend_shapes=64,
        animation_clip_count_creature=96,
        max_simultaneous_anim_layers=6,
        motion_matching_database_mb=256.0,
        ik_chain_depth=6,
        facial_blend_shape_count=80,
    ),
    performance=PerformanceBudget(
        target_frame_ms=16.67,
        target_frame_ms_worst_case=16.67,
        gpu_memory_mb=12288.0,
        cpu_budget_ms=6.0,
        gpu_budget_ms=12.0,
        streaming_cell_load_ms=50.0,
        max_active_actors=10000,
        max_physics_bodies=1000,
        max_particle_systems=200,
    ),
    lighting=LightingBudget(
        lumen_enabled=True,
        virtual_shadow_maps=True,
        max_local_lights=64,
        max_shadow_casting_lights=32,
        gi_quality="epic",
        reflection_quality="lumen",
        volumetric_fog=True,
        sky_atmosphere=True,
        exposure_mode="manual",
    ),
    streaming=StreamingBudget(
        world_partition_enabled=True,
        cell_size_meters=128.0,
        loading_range_meters=4096.0,
        streaming_source_count=8,
        hlod_levels=5,
        data_layer_count=32,
        max_concurrent_loads=16,
        memory_budget_mb=8192.0,
    ),
    density=AssetDensityBudget(
        creatures_per_km2=16,
        props_per_km2=1000,
        foliage_instances_per_km2=100_000,
        destructibles_per_km2=100,
        audio_sources_per_km2=200,
        npc_spawn_points_per_km2=40,
        mission_markers_per_km2=20,
    ),
    benchmark_reference="creature-hunting open-world biome density (quality benchmark only)",
    requires_ue_render_evidence=True,
)

QUALITY_PROFILES: dict[str, QualityProfile] = {
    "previz": PREVIZ_PROFILE,
    "vertical_slice": HIGH_FIDELITY_PROFILE,
    "high_fidelity": HIGH_FIDELITY_PROFILE,
    "aaa_benchmark": AAA_BENCHMARK_PROFILE,
}


def load_quality_profile(name: str) -> QualityProfile:
    key = name.lower().strip()
    if key not in QUALITY_PROFILES:
        raise ValueError(
            f"unknown quality profile {name!r}; choose from {sorted(QUALITY_PROFILES)}"
        )
    return QUALITY_PROFILES[key]


__all__ = [
    "AAA_BENCHMARK_PROFILE",
    "AssetDensityBudget",
    "AnimationBudget",
    "FidelityTier",
    "HIGH_FIDELITY_PROFILE",
    "LightingBudget",
    "MaterialBudget",
    "PerformanceBudget",
    "PolygonBudget",
    "PREVIZ_PROFILE",
    "QUALITY_PROFILES",
    "QualityProfile",
    "StreamingBudget",
    "TextureBudget",
    "load_quality_profile",
]
