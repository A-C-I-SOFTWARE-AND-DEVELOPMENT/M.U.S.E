"""Blender headless post-processing contracts for AAA asset pipeline."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


BLENDER_CONTRACT_VERSION = "muse_blender_contract_v1"


@dataclass(frozen=True)
class BlenderExportSettings:
    format: str
    apply_transforms: bool
    apply_modifiers: bool
    triangulate: bool
    embed_textures: bool
    scale: float
    forward_axis: str
    up_axis: str


@dataclass(frozen=True)
class BlenderPostStep:
    step_id: str
    operation: str
    parameters: Mapping[str, Any]
    input_path: str
    output_path: str
    required: bool = True


@dataclass(frozen=True)
class BlenderContract:
    contract_version: str
    asset_id: str
    input_format: str
    output_format: str
    export_settings: BlenderExportSettings
    steps: tuple[BlenderPostStep, ...]
    validation_requirements: tuple[str, ...]

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "contract_version": self.contract_version,
            "asset_id": self.asset_id,
            "input_format": self.input_format,
            "output_format": self.output_format,
            "export_settings": asdict(self.export_settings),
            "steps": [asdict(s) for s in self.steps],
            "validation_requirements": list(self.validation_requirements),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> BlenderContract:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            contract_version=data["contract_version"],
            asset_id=data["asset_id"],
            input_format=data["input_format"],
            output_format=data["output_format"],
            export_settings=BlenderExportSettings(**data["export_settings"]),
            steps=tuple(BlenderPostStep(**s) for s in data.get("steps", [])),
            validation_requirements=tuple(data.get("validation_requirements", [])),
        )

    def validate_outputs(self, output_paths: Sequence[Path]) -> tuple[bool, tuple[str, ...]]:
        failures: list[str] = []
        expected = {s.output_path for s in self.steps if s.required}
        present = {str(p) for p in output_paths}
        for req in expected:
            if req not in present:
                failures.append(f"missing_output:{req}")
        return (not failures, tuple(failures))


DEFAULT_EXPORT = BlenderExportSettings(
    format="fbx",
    apply_transforms=True,
    apply_modifiers=True,
    triangulate=False,
    embed_textures=False,
    scale=1.0,
    forward_axis="-Z",
    up_axis="Y",
)


def build_creature_blender_contract(asset_id: str) -> BlenderContract:
    base = f"Content/Creatures/{asset_id}"
    return BlenderContract(
        contract_version=BLENDER_CONTRACT_VERSION,
        asset_id=asset_id,
        input_format="glb",
        output_format="fbx",
        export_settings=DEFAULT_EXPORT,
        steps=(
            BlenderPostStep(
                "retopology_check",
                "validate_topology",
                {"max_triangles": 1_000_000, "manifold": True},
                f"{base}/{asset_id}.glb",
                f"{base}/validation/topology.json",
            ),
            BlenderPostStep(
                "uv_unwrap",
                "uv_unwrap",
                {"method": "smart_project", "margin": 0.002},
                f"{base}/{asset_id}.glb",
                f"{base}/{asset_id}_uv.blend",
            ),
            BlenderPostStep(
                "pbr_bake",
                "bake_pbr",
                {"maps": ("albedo", "normal", "roughness", "metallic", "ao")},
                f"{base}/{asset_id}_uv.blend",
                f"{base}/textures/",
            ),
            BlenderPostStep(
                "rig_apply",
                "apply_skeleton",
                {"retarget": "ue5_mannequin", "bone_count_max": 180},
                f"{base}/{asset_id}_uv.blend",
                f"{base}/{asset_id}_rigged.blend",
            ),
            BlenderPostStep(
                "export_fbx",
                "export",
                {"format": "fbx", "embed_textures": False},
                f"{base}/{asset_id}_rigged.blend",
                f"{base}/{asset_id}.fbx",
            ),
        ),
        validation_requirements=(
            "finite_bounds",
            "uv",
            "collision",
            "skeleton_compatible",
            "animation_compatible",
        ),
    )


def build_environment_blender_contract(asset_id: str) -> BlenderContract:
    base = f"Content/Environment/{asset_id}"
    return BlenderContract(
        contract_version=BLENDER_CONTRACT_VERSION,
        asset_id=asset_id,
        input_format="glb",
        output_format="fbx",
        export_settings=DEFAULT_EXPORT,
        steps=(
            BlenderPostStep(
                "lod_generate",
                "generate_lods",
                {"levels": (0, 1, 2, 3), "reduction": (1.0, 0.5, 0.25, 0.1)},
                f"{base}/{asset_id}.glb",
                f"{base}/lods/",
            ),
            BlenderPostStep(
                "collision_generate",
                "generate_collision",
                {"method": "convex_hull", "max_hulls": 8},
                f"{base}/{asset_id}.glb",
                f"{base}/collision/",
            ),
            BlenderPostStep(
                "export_fbx",
                "export",
                {"format": "fbx"},
                f"{base}/{asset_id}.glb",
                f"{base}/{asset_id}.fbx",
            ),
        ),
        validation_requirements=("finite_bounds", "uv", "lod", "collision"),
    )


def generate_blender_script(contract: BlenderContract) -> str:
    lines = [
        "# Generated Blender headless script — muse blender contract",
        "import bpy",
        "import json",
        "",
        f"CONTRACT = {json.dumps(asdict(contract), indent=2)}",
        "",
        "def run_contract():",
        "    results = []",
        "    for step in CONTRACT['steps']:",
        "        results.append({'step_id': step['step_id'], 'status': 'stubbed'})",
        "    return results",
        "",
        "if __name__ == '__main__':",
        "    print(json.dumps(run_contract()))",
    ]
    return "\n".join(lines)


__all__ = [
    "BLENDER_CONTRACT_VERSION",
    "BlenderContract",
    "BlenderExportSettings",
    "BlenderPostStep",
    "build_creature_blender_contract",
    "build_environment_blender_contract",
    "generate_blender_script",
]
