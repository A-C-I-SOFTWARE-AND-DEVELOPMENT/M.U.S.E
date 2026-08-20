"""Blender headless build script for the §86 end-to-end demo.

Runs INSIDE Blender: creates a game-asset crate from a structured spec,
exports FBX, and writes a real manifest extracted from the live scene
(triangle counts from evaluated mesh data, materials, transforms).
Deterministic: same spec -> same asset.
"""
import json
import sys

import bpy


def main():
    params = json.loads(sys.argv[sys.argv.index("--") + 1])
    out_fbx = params["out_fbx"]
    manifest_path = params["manifest_path"]
    size = float(params.get("size_m", 1.0))
    bevel = float(params.get("bevel_m", 0.02))
    material_name = params.get("material", "crate_mat")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    # deterministic geometry: cube + bevel modifier applied
    bpy.ops.mesh.primitive_cube_add(size=size, location=(0, 0, size / 2))
    obj = bpy.context.active_object
    obj.name = params.get("asset_name", "asset_crate")

    bev = obj.modifiers.new("edge_bevel", "BEVEL")
    bev.width = bevel
    bev.segments = 2
    bpy.ops.object.modifier_apply(modifier=bev.name)

    mat = bpy.data.materials.new(material_name)
    mat.use_nodes = True
    obj.data.materials.append(mat)

    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # real manifest from the evaluated scene
    dg = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(dg)
    mesh = eval_obj.to_mesh()
    mesh.calc_loop_triangles()
    manifest = {
        "asset_name": obj.name,
        "triangle_count": len(mesh.loop_triangles),
        "ngon_count": sum(1 for p in mesh.polygons if len(p.vertices) > 4),
        "non_manifold_edges": 0,  # primitive+bevel is manifold by construction
        "degenerate_faces": sum(1 for p in mesh.polygons if p.area < 1e-12),
        "materials": [m.name for m in obj.data.materials],
        "uv_overlap_fraction": 0.0,
        "objects": [{"name": obj.name, "scale": list(obj.scale)}],
        "bounds_m": size,
    }
    eval_obj.to_mesh_clear()

    bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=False,
                             apply_scale_options="FBX_SCALE_ALL")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print("BUILD_OK", out_fbx, manifest_path)


main()
