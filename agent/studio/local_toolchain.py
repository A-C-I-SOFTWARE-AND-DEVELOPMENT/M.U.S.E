"""Local Blender and Unreal execution with durable evidence."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from agent.studio.engine_discovery import UnrealInstallation, discover_unreal
from agent.studio.game_verification import CommandEvidence, run_declared_commands


@dataclass(frozen=True)
class LocalToolchain:
    blender: str
    unreal: UnrealInstallation | None
    gpu_name: str
    vram_gb: float

    @property
    def ready(self) -> bool:
        return bool(self.blender and self.unreal)


def discover_blender() -> Path | None:
    configured = os.environ.get("BLENDER_EXECUTABLE")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path(shutil.which("blender") or ""),
        Path("C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"),
        Path("C:/Blender/blender.exe"),
    ]
    return next((path.resolve() for path in candidates if path and path.is_file()), None)


def _gpu_info() -> tuple[str, float]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=15,
        ).splitlines()[0]
        name, memory_mib = (part.strip() for part in output.split(",", 1))
        return name, round(float(memory_mib) / 1024.0, 2)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return "", 0.0


def discover_local_toolchain(engine_version: str = "5.8") -> LocalToolchain:
    blender = discover_blender()
    gpu_name, vram_gb = _gpu_info()
    return LocalToolchain(
        blender=str(blender or ""),
        unreal=discover_unreal(preferred=engine_version),
        gpu_name=gpu_name,
        vram_gb=vram_gb,
    )


def generate_proof_asset(
    project_root: Path,
    *,
    asset_id: str = "proof_creature",
    runner=subprocess.run,
) -> tuple[Path | None, dict[str, object]]:
    """Create a deterministic, original procedural FBX for pipeline verification."""

    project_root = Path(project_root).resolve()
    blender = discover_blender()
    evidence_dir = project_root / "evidence" / "blender"
    output_dir = project_root / "assets" / "procedural"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{asset_id}.fbx"
    script = evidence_dir / f"{asset_id}_build.py"
    script.write_text(
        "\n".join(
            [
                "import bpy, json, pathlib",
                "bpy.ops.wm.read_factory_settings(use_empty=True)",
                "bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.5)",
                f"obj = bpy.context.active_object; obj.name = {asset_id!r}",
                "obj.scale = (1.0, 1.8, 0.85)",
                "bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)",
                "bpy.ops.object.modifier_add(type='DECIMATE')",
                "obj.modifiers[-1].ratio = 0.55",
                "bpy.ops.object.modifier_apply(modifier=obj.modifiers[-1].name)",
                "bpy.ops.object.shade_smooth_by_angle()",
                f"target = pathlib.Path({str(output)!r})",
                "target.parent.mkdir(parents=True, exist_ok=True)",
                "bpy.ops.export_scene.fbx(filepath=str(target), use_selection=False, "
                "apply_unit_scale=True, axis_forward='-Z', axis_up='Y')",
                "mesh = obj.data",
                "report = {'asset_id': obj.name, 'vertices': len(mesh.vertices), "
                "'polygons': len(mesh.polygons), 'output': str(target), "
                "'authoritative': True, 'license': 'original-procedural'}",
                f"pathlib.Path({str(evidence_dir / f'{asset_id}_report.json')!r}).write_text("
                "json.dumps(report, indent=2), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if blender is None:
        report = {"ok": False, "error": "blender_not_found", "asset_id": asset_id}
        return None, report
    completed = runner(
        [str(blender), "--background", "--factory-startup", "--python", str(script)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    report_path = evidence_dir / f"{asset_id}_report.json"
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else {}
    )
    report.update(
        {
            "ok": completed.returncode == 0 and output.is_file() and output.stat().st_size > 0,
            "exit_code": completed.returncode,
            "stdout": (completed.stdout or "")[-1000:],
            "stderr": (completed.stderr or "")[-1000:],
        }
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return (output if report["ok"] else None), report


def generate_previs_source(
    project_root: Path,
    *,
    runner=subprocess.run,
) -> Path | None:
    """Render an original deterministic source frame for world-model conditioning."""

    project_root = Path(project_root).resolve()
    blender = discover_blender()
    if blender is None:
        return None
    destination = project_root / "previs" / "source-frame.png"
    script = project_root / "previs" / "render_source.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "\n".join(
            [
                "import bpy, math, pathlib",
                "from mathutils import Vector",
                "bpy.ops.wm.read_factory_settings(use_empty=True)",
                "bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))",
                "ground = bpy.context.active_object; ground.name = 'FrontierGround'",
                "mat = bpy.data.materials.new('GroundMaterial')",
                "mat.diffuse_color = (0.04, 0.16, 0.08, 1.0)",
                "ground.data.materials.append(mat)",
                "for i, xyz in enumerate(((-5,2,1.5),(0,5,2.5),(5,1,1.2),(-1,-2,3.0))):",
                "    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=xyz[2], "
                "location=(xyz[0], xyz[1], xyz[2] * 0.7))",
                "    bpy.context.active_object.name = f'FrontierRock_{i}'",
                "bpy.ops.object.light_add(type='SUN', location=(0,0,10))",
                "bpy.context.active_object.rotation_euler = (math.radians(25), 0, math.radians(-35))",
                "bpy.context.active_object.data.energy = 4.0",
                "bpy.ops.object.camera_add(location=(12,-18,9))",
                "camera = bpy.context.active_object",
                "direction = Vector((0,2,1.5)) - camera.location",
                "camera.rotation_euler = direction.to_track_quat('-Z','Y').to_euler()",
                "bpy.context.scene.camera = camera",
                "scene = bpy.context.scene",
                "scene.render.engine = 'BLENDER_EEVEE'",
                "scene.render.resolution_x = 832; scene.render.resolution_y = 480",
                "scene.render.resolution_percentage = 100",
                "scene.world = bpy.data.worlds.new('FrontierWorld')",
                "scene.world.color = (0.03, 0.08, 0.16)",
                f"scene.render.filepath = {str(destination)!r}",
                "bpy.ops.render.render(write_still=True)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    completed = runner(
        [str(blender), "--background", "--factory-startup", "--python", str(script)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return (
        destination
        if completed.returncode == 0
        and destination.is_file()
        and destination.stat().st_size > 0
        else None
    )


def generate_frontier_asset_pack(
    project_root: Path,
    *,
    runner=subprocess.run,
) -> tuple[dict[str, Path], dict[str, object]]:
    """Generate original terrain, foliage, rock, and creature FBXs in Blender."""

    project_root = Path(project_root).resolve()
    blender = discover_blender()
    output_dir = project_root / "Generated" / "Assets"
    texture_dir = project_root / "Generated" / "Textures"
    evidence_dir = project_root / "Evidence" / "blender"
    output_dir.mkdir(parents=True, exist_ok=True)
    texture_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    names = ("FrontierTerrain", "FrontierTree", "FrontierRock", "FrontierCreature")
    outputs = {name: output_dir / f"{name}.fbx" for name in names}
    texture_materials = {
        "ForestGround": (0.025, 0.14, 0.035),
        "Bark": (0.16, 0.045, 0.012),
        "Canopy": (0.015, 0.22, 0.035),
        "Stone": (0.13, 0.17, 0.15),
        "CreatureHide": (0.01, 0.28, 0.19),
        "CreatureLimb": (0.012, 0.12, 0.075),
        "CreatureHorn": (0.46, 0.27, 0.055),
    }
    texture_outputs = {
        material_name: {
            map_name: texture_dir / f"{material_name}_{map_name}.png"
            for map_name in ("BaseColor", "Normal", "ORM")
        }
        for material_name in texture_materials
    }
    script = evidence_dir / "build_frontier_asset_pack.py"
    script.write_text(
        f"""import bpy, json, math, pathlib
import numpy as np

OUTPUTS = {json.dumps({name: str(path) for name, path in outputs.items()}, indent=2)}
TEXTURES = {json.dumps({name: {kind: str(path) for kind, path in maps.items()} for name, maps in texture_outputs.items()}, indent=2)}
TEXTURE_BASES = {json.dumps(texture_materials, indent=2)}

def reset():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def material(name, color, metallic=0.0, roughness=0.7):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.metallic = metallic
    mat.roughness = roughness
    return mat

def finish(name):
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    target = pathlib.Path(OUTPUTS[name])
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(target), use_selection=True, apply_unit_scale=True,
        axis_forward='-Z', axis_up='Y', add_leaf_bones=False
    )

reset()
bpy.ops.mesh.primitive_grid_add(x_subdivisions=25, y_subdivisions=17, size=2)
terrain = bpy.context.active_object
terrain.scale = (40.0, 20.0, 1.0)
for vertex in terrain.data.vertices:
    x, y = vertex.co.x, vertex.co.y
    vertex.co.z = math.sin(x * 8.0) * 0.6 + math.cos(y * 6.0) * 0.35
terrain.data.materials.append(material('ForestGround', (0.035, 0.16, 0.055), 0.0, 0.95))
finish('FrontierTerrain')

reset()
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.45, depth=4.5, location=(0,0,2.25))
bpy.context.active_object.data.materials.append(material('Bark', (0.18, 0.065, 0.025)))
for z, radius in ((4.0, 2.1), (5.2, 1.65), (6.1, 1.15)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius, location=(0,0,z))
    bpy.context.active_object.scale.z = 0.72
    bpy.context.active_object.data.materials.append(material('Canopy', (0.025, 0.24, 0.06)))
finish('FrontierTree')

reset()
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.6)
rock = bpy.context.active_object
rock.scale = (1.35, 0.9, 0.72)
rock.rotation_euler = (0.2, -0.15, 0.4)
rock.data.materials.append(material('Stone', (0.16, 0.19, 0.17), 0.0, 1.0))
finish('FrontierRock')

reset()
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.35, location=(0,0,1.8))
body = bpy.context.active_object
body.scale = (1.8, 0.85, 0.9)
body.data.materials.append(material('CreatureHide', (0.035, 0.28, 0.22), 0.05, 0.48))
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.72, location=(1.75,0,2.15))
bpy.context.active_object.data.materials.append(material('CreatureHide', (0.035, 0.28, 0.22)))
for x in (-0.9, 0.8):
    for y in (-0.58, 0.58):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.22, depth=1.8, location=(x,y,0.85))
        bpy.context.active_object.data.materials.append(material('CreatureLimb', (0.025, 0.16, 0.13)))
for y in (-0.3, 0.3):
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.2, radius2=0.0, depth=0.9, location=(2.15,y,2.75))
    bpy.context.active_object.data.materials.append(material('CreatureHorn', (0.5, 0.36, 0.12)))
finish('FrontierCreature')

def save_texture(path, rgb):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width, _ = rgb.shape
    rgba = np.concatenate(
        (np.clip(rgb, 0.0, 1.0), np.ones((height, width, 1), dtype=np.float32)),
        axis=2,
    ).astype(np.float32)
    image = bpy.data.images.new(path.stem, width=width, height=height, alpha=True)
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = str(path)
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)

def texture_set(name, base, seed, size=1024):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    x /= float(size)
    y /= float(size)
    detail = (
        np.sin((x * (13.0 + seed) + y * 3.0) * math.tau) * 0.34
        + np.sin((y * (29.0 + seed) - x * 7.0) * math.tau) * 0.23
        + np.cos(((x + y) * (61.0 + seed)) * math.tau) * 0.15
        + np.sin((x * 127.0 - y * 89.0 + seed) * math.tau) * 0.08
    )
    detail = np.clip(0.5 + detail, 0.0, 1.0).astype(np.float32)
    base_rgb = np.asarray(base, dtype=np.float32).reshape((1, 1, 3))
    color = np.clip(base_rgb * (0.58 + detail[..., None] * 0.72), 0.0, 1.0)
    grad_y, grad_x = np.gradient(detail)
    normal = np.dstack(
        (
            np.clip(0.5 - grad_x * 8.0, 0.0, 1.0),
            np.clip(0.5 - grad_y * 8.0, 0.0, 1.0),
            np.ones_like(detail),
        )
    ).astype(np.float32)
    ao = np.clip(0.55 + detail * 0.45, 0.0, 1.0)
    roughness = np.clip(0.58 + (1.0 - detail) * 0.34, 0.0, 1.0)
    metallic = np.full_like(detail, 0.04 if name == 'CreatureHide' else 0.0)
    orm = np.dstack((ao, roughness, metallic)).astype(np.float32)
    save_texture(TEXTURES[name]['BaseColor'], color)
    save_texture(TEXTURES[name]['Normal'], normal)
    save_texture(TEXTURES[name]['ORM'], orm)

for index, (name, base) in enumerate(TEXTURE_BASES.items(), start=1):
    texture_set(name, base, index)

report = {{'assets': {{}}, 'textures': {{}}, 'authoritative': True, 'license': 'original-procedural'}}
for name, value in OUTPUTS.items():
    path = pathlib.Path(value)
    report['assets'][name] = {{'path': str(path), 'bytes': path.stat().st_size}}
for name, maps in TEXTURES.items():
    report['textures'][name] = {{}}
    for kind, value in maps.items():
        path = pathlib.Path(value)
        report['textures'][name][kind] = {{'path': str(path), 'bytes': path.stat().st_size}}
pathlib.Path({str(evidence_dir / 'frontier_asset_pack.json')!r}).write_text(
    json.dumps(report, indent=2), encoding='utf-8'
)
""",
        encoding="utf-8",
    )
    if blender is None:
        return {}, {"ok": False, "error": "blender_not_found"}
    completed = runner(
        [str(blender), "--background", "--factory-startup", "--python", str(script)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    valid = {
        name: path
        for name, path in outputs.items()
        if path.is_file() and path.stat().st_size > 0
    }
    valid_textures = {
        material_name: {
            map_name: path
            for map_name, path in maps.items()
            if path.is_file() and path.stat().st_size > 0
        }
        for material_name, maps in texture_outputs.items()
    }
    textures_complete = all(
        len(maps) == len(texture_outputs[material_name])
        for material_name, maps in valid_textures.items()
    )
    report = {
        "ok": (
            completed.returncode == 0
            and len(valid) == len(outputs)
            and textures_complete
        ),
        "exit_code": completed.returncode,
        "assets": {name: str(path) for name, path in valid.items()},
        "textures": {
            material_name: {map_name: str(path) for map_name, path in maps.items()}
            for material_name, maps in valid_textures.items()
        },
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
        "license": "original-procedural",
    }
    (evidence_dir / "frontier_asset_pack_run.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return valid, report


def unreal_commands(
    project_root: Path,
    installation: UnrealInstallation,
    *,
    package: bool,
) -> dict[str, Sequence[str]]:
    project_root = Path(project_root).resolve()
    uprojects = tuple(project_root.glob("*.uproject"))
    if len(uprojects) != 1:
        raise ValueError("expected exactly one .uproject")
    uproject = uprojects[0]
    module = uproject.stem
    commands: dict[str, Sequence[str]] = {
        "build_editor": (
            str(installation.build_tool),
            f"{module}Editor",
            "Win64",
            "Development",
            str(uproject),
            "-WaitMutex",
            "-NoHotReload",
        ),
        "author_world": (
            str(installation.editor_command),
            str(uproject),
            f"-ExecutePythonScript={project_root / 'Content/Python/build_world.py'}",
            "-unattended",
            "-nop4",
            "-nosplash",
            "-NullRHI",
        ),
        "audit_world": (
            str(installation.editor_command),
            str(uproject),
            f"-ExecutePythonScript={project_root / 'Content/Python/audit_world.py'}",
            "-unattended",
            "-nop4",
            "-nosplash",
            "-NullRHI",
        ),
    }
    if package:
        if installation.package_tool is None:
            raise RuntimeError("RunUAT was not discovered")
        archive = project_root / "Build" / "Win64"
        commands["package_win64"] = (
            str(installation.package_tool),
            "BuildCookRun",
            f"-project={uproject}",
            "-noP4",
            "-platform=Win64",
            "-clientconfig=Development",
            "-build",
            "-cook",
            "-stage",
            "-pak",
            "-package",
            "-archive",
            f"-archivedirectory={archive}",
            "-utf8output",
        )
    return commands


def execute_unreal(
    project_root: Path,
    *,
    engine_version: str = "5.8",
    package: bool = False,
    runner=subprocess.run,
) -> tuple[CommandEvidence, ...]:
    project_root = Path(project_root).resolve()
    installation = discover_unreal(preferred=engine_version)
    if installation is None:
        raise RuntimeError(f"Unreal Engine {engine_version} was not discovered")
    records = run_declared_commands(
        unreal_commands(project_root, installation, package=package),
        cwd=project_root,
        evidence_dir=project_root / "Evidence" / "commands",
        runner=runner,
        timeout_seconds=7200,
    )
    report = {
        "engine_version": installation.version,
        "package_requested": package,
        "passed": all(record.passed for record in records),
        "commands": [asdict(record) for record in records],
    }
    report_path = project_root / "Evidence" / "toolchain-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return records


__all__ = [
    "LocalToolchain",
    "discover_blender",
    "discover_local_toolchain",
    "execute_unreal",
    "generate_previs_source",
    "generate_frontier_asset_pack",
    "generate_proof_asset",
    "unreal_commands",
]
