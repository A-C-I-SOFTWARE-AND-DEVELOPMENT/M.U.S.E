#!/usr/bin/env python
"""Guide-first runner: pick official + tutorial, write a LEGO instruction card.

No GPU. Safe while QLoRA is training. Does not download videos.
Does not scrape paid courses. Ledger is the allowlist.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_OFFICIAL = [
    {"id": "blender-fbx", "task": "fbx-ue", "title": "Blender FBX exporter",
     "url": "https://docs.blender.org/manual/en/latest/addons/import_export/scene_fbx.html"},
    {"id": "blender-bevel", "task": "blender-kit", "title": "Bevel modifier",
     "url": "https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html"},
    {"id": "blender-extrude", "task": "blender-kit", "title": "Extrude",
     "url": "https://docs.blender.org/manual/en/latest/modeling/meshes/editing/mesh/extrude.html"},
    {"id": "blender-uv", "task": "blender-kit", "title": "UV unwrapping",
     "url": "https://docs.blender.org/manual/en/latest/modeling/meshes/uv/unwrapping.html"},
    {"id": "polyhaven-api", "task": "pbr", "title": "Poly Haven files API",
     "url": "https://polyhaven.com/our-api"},
    {"id": "ue-landscape", "task": "landscape", "title": "Landscape Technical Guide",
     "url": "https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-technical-guide-in-unreal-engine"},
    {"id": "ue-nanite", "task": "fbx-ue", "title": "Nanite virtualized geometry",
     "url": "https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine"},
    {"id": "ue-pcg", "task": "pcg", "title": "PCG overview",
     "url": "https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview"},
    {"id": "ue-wp", "task": "landscape", "title": "World Partition",
     "url": "https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine"},
]

LEDGER_TUTORIAL = [
    {"id": "grant-game-assets", "task": "blender-kit",
     "title": "Grant Abbitt — Blender game assets (latest ≥4.0)",
     "url": "https://www.youtube.com/@grantabbitt"},
    {"id": "default-cube-hard", "task": "blender-kit",
     "title": "Default Cube — hard-surface / bevels",
     "url": "https://www.youtube.com/@DefaultCube"},
    {"id": "blender-guru-pbr", "task": "pbr",
     "title": "Blender Guru — PBR / lighting",
     "url": "https://www.youtube.com/@blenderguru"},
    {"id": "aziel-landscape", "task": "landscape",
     "title": "Aziel Arts — Open World Landscapes",
     "url": "https://www.youtube.com/watch?v=B2f6EoOXRHg"},
    {"id": "gorka-openworld", "task": "pcg",
     "title": "Gorka Games — Open World PCG+Landmass+Water+WP",
     "url": "https://www.youtube.com/watch?v=Uvce5nRrzk8"},
    {"id": "pcg-mode", "task": "pcg",
     "title": "Procedural Minds — PCG Mode 5.7+",
     "url": "https://www.youtube.com/watch?v=IPwVOhvQ2bo"},
]

REFUSE = (
    "60 seconds", "10 minute AAA", "ai generate 3d", "meshy only",
    "no retopo", "blender 2.79", "blender 2.8 tutorial",
)

STEPS = {
    "blender-kit": [
        ("Block the silhouette with boxes. Do not detail.",
         "Name the block `{subject}_block`. Delete leftover Cube."),
        ("Add supporting loops / Bevel modifier (limit Weight, 2–3 segments).",
         "On `{subject}` bevel only hard corners. Keep the grounded ring."),
        ("Apply scale (Ctrl-A). Origin to geometry. min_z = 0.",
         "Snap `{subject}` so the trunk/base sits on Z=0."),
        ("Unwrap (Smart UV or seams). No 0-area islands. Texel consistent.",
         "Unwrap `{subject}` after bevels so UVs are not stretched."),
        ("Assign PBR: albedo + normal + roughness from CC0 (Poly Haven / ambientCG).",
         "Pick the biome map that matches `{subject}` (bark/wood/stone). No purple."),
        ("Export FBX: selected only, FBX_SCALE_NONE, -Z forward, Y up, apply triangulate.",
         "Write `assets/kits/{subject}.fbx` + provenance URL in assets/README.md."),
    ],
    "fbx-ue": [
        ("Read official FBX exporter + Nanite import pages.",
         "Cite both URLs in lookups.md before touching Unreal."),
        ("Export selected, scale none, -Z/Y, triangulate, apply modifiers.",
         "`{subject}.fbx` only — not the whole scene."),
        ("Import as Static Mesh. Enable Nanite on hero rocks / kits ≥ mid-poly.",
         "Do not Nanite tiny clutter (use HISM)."),
        ("Ground: mesh bounds min Z ≈ 0. No float.",
         "Reimport `{subject}` if the pivot is mid-mesh."),
    ],
    "pbr": [
        ("Official: Poly Haven / ambientCG API or browser. License CC0.",
         "Download 2K (disk) or 4–8K if owner asked. Never Megascans scrape."),
        ("Need diff + nor_gl + rough (or ARM). Write the page URL.",
         "Folder `assets/pbr/{id}/`."),
        ("Build a material. No hex-dump purple.",
         "M_{id} on `{subject}` only."),
    ],
    "landscape": [
        ("Official Landscape Technical Guide + World Partition page.",
         "Cite both. Do not invent a third importer."),
        ("Heightmap size power-of-two+1 (e.g. 4033). One stream.",
         "Use `levels/terrain/height.png` — do not claim a 37 km² FBX."),
        ("One dated tutorial (Aziel). Execute only those import steps.",
         "Write URLs to reports/<hold>/lookups.md."),
    ],
    "pcg": [
        ("Official PCG overview. Then one dated video (Gorka or PCG Mode).",
         "Do not mix 5.0 and 5.7 node names."),
        ("Instance kits, do not spawn unique meshes.",
         "`{subject}` = 1 mesh, HISM / PCG count."),
    ],
    "lighting": [
        ("Look-dev from a World Vision clip or still. Official Lumen page if UE.",
         "Teal/emerald/amber only. No purple."),
        ("Support-region refine. Do not rewrite the height field.",
         "Two stills + reports/<hold>/lookdev.md."),
    ],
}

VERIFY = {
    "blender-kit": [
        "No default Cube/Plane/Suzanne in the file",
        "Bevel or support loops on hard edges",
        "UVs present, no 0-area islands",
        "PBR trio assigned",
        "min_z ≈ 0, origin at ground",
        "FBX exported with scale none / -Z / Y",
        "lookups.md + instruction-card.json written",
    ],
    "fbx-ue": ["Nanite policy recorded", "no float", "lookups cited"],
    "pbr": ["license=CC0 + URL", "diff/nor/rough on disk", "no purple"],
    "landscape": ["official + Aziel cited", "heightmap +1 size", "no 37km FBX claim"],
    "pcg": ["official + one tutorial", "instances not uniques"],
    "lighting": ["no purple", "support-region only"],
}

FAIL_IF = [
    "blocky 90° box with no bevels",
    "default material / grey plastic",
    "floating (min_z != 0)",
    "same tutorial URL retried after FAIL",
    "clickbait / 60-second / undated 2.79 video",
    "no instruction card",
]


def pick(task: str, exclude: list[str]) -> tuple[dict, dict]:
    official = next((x for x in LEDGER_OFFICIAL if x["task"] == task and x["id"] not in exclude), None)
    if official is None:
        official = next(x for x in LEDGER_OFFICIAL if x["id"] not in exclude)
    tutorial = next((x for x in LEDGER_TUTORIAL if x["task"] == task and x["id"] not in exclude), None)
    if tutorial is None:
        tutorial = next((x for x in LEDGER_TUTORIAL if x["id"] not in exclude), LEDGER_TUTORIAL[0])
    return official, tutorial


def card(task: str, subject: str, exclude: list[str], swap: int) -> dict:
    official, tutorial = pick(task, exclude)
    raw = STEPS.get(task, STEPS["blender-kit"])
    steps = [
        {"n": i + 1, "do": do, "adapt": adapt.format(subject=subject)}
        for i, (do, adapt) in enumerate(raw)
    ]
    return {
        "task": task,
        "subject": subject,
        "official": official,
        "tutorial": tutorial,
        "tried": exclude + [official["id"], tutorial["id"]],
        "swap": swap,
        "steps": steps,
        "verify": VERIFY.get(task, VERIFY["blender-kit"]),
        "fail_if": FAIL_IF,
        "ideology": "LEGO box: numbered steps from a real guide. Do not invent.",
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_lookups(out: Path, c: dict, symptom: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    md = out / "lookups.md"
    block = (
        f"\n## Guide-first {c['issued_at']} — {c['subject']} ({c['task']})\n"
        f"Symptom: {symptom or 'none'}\n"
        f"- Official: {c['official']['title']} — {c['official']['url']}\n"
        f"- Tutorial: {c['tutorial']['title']} — {c['tutorial']['url']}\n"
        f"- Swap: {c['swap']}/2\n"
    )
    prev = md.read_text(encoding="utf-8") if md.exists() else "# Tutorial lookups (cite, do not invent)\n"
    md.write_text(prev.rstrip() + "\n" + block, encoding="utf-8")
    (out / "instruction-card.json").write_text(json.dumps(c, indent=2), encoding="utf-8")


def judge_mesh(path: Path) -> dict:
    reasons: list[str] = []
    ok = True
    if not path.exists():
        return {"pass": False, "reasons": [f"missing {path}"]}
    size = path.stat().st_size
    if size < 800:
        ok = False
        reasons.append(f"tiny file ({size} B) — likely empty/box")
    name = path.name.lower()
    if "cube" in name or "suzanne" in name:
        ok = False
        reasons.append("default object name")
    # FBX ASCII/binary existence is not beauty. Call that out.
    reasons.append("file exists; visual blocky/crap still needs a render (qa-playtest)")
    return {"pass": ok, "path": str(path), "bytes": size, "reasons": reasons}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task", default="blender-kit",
                   choices=sorted(STEPS))
    p.add_argument("--subject", default="kit")
    p.add_argument("--symptom", default="")
    p.add_argument("--exclude", default="", help="comma ids already tried")
    p.add_argument("--swap", type=int, default=0)
    p.add_argument("--out", default="")
    p.add_argument("--judge", default="", help="optional mesh path")
    args = p.parse_args()
    symptom = args.symptom.lower()
    for bad in REFUSE:
        if bad in symptom:
            print(json.dumps({"refuse": bad, "reason": "low-quality guide class — pick ledger instead"}))
            return 2
    exclude = [x for x in args.exclude.split(",") if x]
    if args.swap > 2:
        print(json.dumps({"pass": False, "reason": "swap budget exhausted — return to artist with card"}))
        return 3
    c = card(args.task, args.subject, exclude, args.swap)
    out = Path(args.out) if args.out else Path.cwd()
    write_lookups(out, c, args.symptom)
    result = {"card": c, "wrote": str(out / "instruction-card.json")}
    if args.judge:
        result["judge"] = judge_mesh(Path(args.judge))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
