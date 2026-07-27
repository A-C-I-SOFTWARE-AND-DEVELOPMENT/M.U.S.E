"""Skeletal creature and animation requirements for AAA production."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUIRED_CREATURE_ANIMATIONS = (
    "idle",
    "locomotion_walk",
    "locomotion_run",
    "locomotion_sprint",
    "turn_in_place",
    "attack_primary",
    "attack_secondary",
    "hit_react_front",
    "hit_react_back",
    "death",
    "spawn",
    "roar",
    "investigate",
    "flee",
    "sleep",
)


@dataclass(frozen=True)
class SkeletonSpec:
    creature_id: str
    bone_count: int
    root_bone: str
    ik_chains: tuple[str, ...]
    facial_rig: bool
    retarget_source: str
    compatible_engine: str = "unreal"

    def validate(self, evidence: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
        failures: list[str] = []
        if evidence.get("bone_count", 0) > self.bone_count:
            failures.append("bone_count_over_budget")
        if evidence.get("root_bone") != self.root_bone:
            failures.append("root_bone_mismatch")
        if self.facial_rig and not evidence.get("facial_rig_present"):
            failures.append("facial_rig_missing")
        for chain in self.ik_chains:
            if chain not in evidence.get("ik_chains_present", []):
                failures.append(f"ik_chain_missing:{chain}")
        return (not failures, tuple(failures))


@dataclass(frozen=True)
class AnimationClipSpec:
    clip_id: str
    name: str
    duration_s: float
    loop: bool
    root_motion: bool
    blend_space_axis: str = ""
    priority: int = 0


@dataclass(frozen=True)
class CreatureManifest:
    creature_id: str
    display_name: str
    category: str
    skeleton: SkeletonSpec
    animations: tuple[AnimationClipSpec, ...]
    mesh_path: str
    texture_set: tuple[str, ...]
    nanite_enabled: bool
    collision_profile: str
    ai_behavior_tree: str
    version: str = "1.0"

    def required_animation_names(self) -> frozenset[str]:
        return frozenset(a.name for a in self.animations)

    def missing_required_animations(self) -> tuple[str, ...]:
        present = self.required_animation_names()
        return tuple(a for a in REQUIRED_CREATURE_ANIMATIONS if a not in present)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "creature_id": self.creature_id,
            "display_name": self.display_name,
            "category": self.category,
            "skeleton": asdict(self.skeleton),
            "animations": [asdict(a) for a in self.animations],
            "mesh_path": self.mesh_path,
            "texture_set": list(self.texture_set),
            "nanite_enabled": self.nanite_enabled,
            "collision_profile": self.collision_profile,
            "ai_behavior_tree": self.ai_behavior_tree,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> CreatureManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        skeleton = SkeletonSpec(**data["skeleton"])
        animations = tuple(AnimationClipSpec(**a) for a in data.get("animations", []))
        return cls(
            creature_id=data["creature_id"],
            display_name=data["display_name"],
            category=data["category"],
            skeleton=skeleton,
            animations=animations,
            mesh_path=data["mesh_path"],
            texture_set=tuple(data.get("texture_set", [])),
            nanite_enabled=data.get("nanite_enabled", False),
            collision_profile=data.get("collision_profile", "complex"),
            ai_behavior_tree=data.get("ai_behavior_tree", ""),
        )


def build_creature_manifest(
    creature_id: str,
    *,
    display_name: str = "",
    bone_count: int = 120,
    profile: str = "high_fidelity",
) -> CreatureManifest:
    from agent.studio.quality_profiles import load_quality_profile

    qp = load_quality_profile(profile)
    animations = tuple(
        AnimationClipSpec(
            clip_id=f"{creature_id}_{name}",
            name=name,
            duration_s=2.0 if "locomotion" in name else 1.5,
            loop="locomotion" in name or name == "idle",
            root_motion="locomotion" in name,
            blend_space_axis="speed" if "locomotion" in name else "",
        )
        for name in REQUIRED_CREATURE_ANIMATIONS
    )
    return CreatureManifest(
        creature_id=creature_id,
        display_name=display_name or creature_id.replace("_", " ").title(),
        category="apex_predator" if "apex" in creature_id else "fauna",
        skeleton=SkeletonSpec(
            creature_id=creature_id,
            bone_count=qp.animation.skeleton_bone_count,
            root_bone="root",
            ik_chains=("spine", "head", "front_left_leg", "front_right_leg"),
            facial_rig=qp.animation.facial_blend_shape_count > 0,
            retarget_source="ue5_mannequin",
        ),
        animations=animations,
        mesh_path=f"Content/Creatures/{creature_id}/{creature_id}.fbx",
        texture_set=("albedo", "normal", "orm", "emissive"),
        nanite_enabled=qp.material.require_nanite_fallback,
        collision_profile="complex_per_poly",
        ai_behavior_tree=f"BT_{creature_id}",
    )


def build_creature_manifests(
    creature_ids: Sequence[str],
    *,
    profile: str = "high_fidelity",
) -> tuple[CreatureManifest, ...]:
    return tuple(
        build_creature_manifest(cid, profile=profile) for cid in creature_ids
    )


__all__ = [
    "AnimationClipSpec",
    "CreatureManifest",
    "REQUIRED_CREATURE_ANIMATIONS",
    "SkeletonSpec",
    "build_creature_manifest",
    "build_creature_manifests",
]
