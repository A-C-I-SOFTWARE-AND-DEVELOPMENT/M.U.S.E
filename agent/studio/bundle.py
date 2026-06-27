"""Axiom Studio bundle producer.

Takes a finished ProjectManifest and packages everything — artifacts,
manifest summary, index.json, README — into a single distributable ZIP.

This is the literal "1 with all contained in it": one file you hand off
to a producer, NLE, game engine importer, or upload to a portfolio site.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from agent.studio.types import ProjectManifest, StageResult


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify_artifact(path: Path) -> str:
    suf = path.suffix.lower()
    return {
        ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
        ".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".flac": "audio",
        ".mp4": "video", ".webm": "video", ".mov": "video",
        ".md": "text",  ".txt": "text", ".jsonl": "text",
        ".json": "data", ".edl": "data", ".uproject": "project",
        ".glb": "mesh3d", ".gltf": "mesh3d", ".fbx": "mesh3d", ".obj": "mesh3d",
    }.get(suf, "other")


def build_index(manifest: ProjectManifest) -> Dict:
    """Build a structured index.json describing every artifact."""
    artifacts: List[Dict] = []
    for stage in manifest.stages:
        for art_path in stage.artifacts:
            p = Path(art_path)
            if not p.exists() or p.is_dir():
                # Engine project dirs land here — descend
                if p.is_dir():
                    for child in p.rglob("*"):
                        if child.is_file():
                            artifacts.append({
                                "stage": stage.stage,
                                "provider": stage.provider.value,
                                "kind": _classify_artifact(child),
                                "path": str(child.relative_to(manifest.workdir)),
                                "size": child.stat().st_size,
                                "sha256": _sha256(child),
                            })
                continue
            artifacts.append({
                "stage": stage.stage,
                "provider": stage.provider.value,
                "kind": _classify_artifact(p),
                "path": str(p.relative_to(manifest.workdir)) if p.is_relative_to(manifest.workdir) else str(p),
                "size": p.stat().st_size,
                "sha256": _sha256(p),
                "status": stage.status,
                "notes": stage.notes,
            })

    by_kind: Dict[str, int] = {}
    by_stage: Dict[str, int] = {}
    total_bytes = 0
    for a in artifacts:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
        by_stage[a["stage"]] = by_stage.get(a["stage"], 0) + 1
        total_bytes += a["size"]

    return {
        "schema": "axiom.studio.bundle/1",
        "title": manifest.title,
        "kind": manifest.kind,
        "quality": manifest.quality.value,
        "generated_at": int(time.time()),
        "totals": {
            "stages": len(manifest.stages),
            "artifacts": len(artifacts),
            "bytes": total_bytes,
            "cost_usd": manifest.total_cost_usd,
            "duration_s": manifest.total_duration_s,
            "by_kind": by_kind,
            "by_stage": by_stage,
        },
        "stage_status": {
            s.stage: {"status": s.status, "provider": s.provider.value,
                      "duration_s": s.duration_s, "notes": s.notes}
            for s in manifest.stages
        },
        "artifacts": artifacts,
    }


def _readme(manifest: ProjectManifest, index: Dict) -> str:
    t = index["totals"]
    by_kind = ", ".join(f"{k}={v}" for k, v in sorted(t["by_kind"].items()))
    layout_blurb = (
        "## Bundle layout\n\n"
        "    manifest.txt        human-readable stage list\n"
        "    index.json          structured artifact inventory (sha256-keyed)\n"
        "    artifacts/<stage>/  every generated file, grouped by pipeline stage\n"
        "\n"
        "## Importing\n\n"
        "- **Film**: drop `artifacts/edl/timeline.edl` into DaVinci Resolve or "
        "Premiere; the concept-art PNGs become reference; the dialogue MP3s "
        "import to the audio bin.\n"
        "- **Game**: open `artifacts/engine_project/<engine>/Project.uproject` "
        "(UE5) or the corresponding Unity/Godot folder. The GDD, world bible, "
        "and gameplay-code starter modules live alongside as design refs.\n"
    )
    return (
        f"# {manifest.title}\n\n"
        f"_Axiom Studio bundle ({manifest.kind})_\n\n"
        f"- Quality: **{manifest.quality.value}**\n"
        f"- Stages: **{t['stages']}** ({sum(1 for s in manifest.stages if s.status == 'ok')} ok)\n"
        f"- Artifacts: **{t['artifacts']}** ({by_kind})\n"
        f"- Size: **{t['bytes']/1e6:.1f} MB**\n"
        f"- Cost: **${t['cost_usd']:.2f}**\n"
        f"- Wall time: **{t['duration_s']:.1f}s**\n\n"
        f"{layout_blurb}\n"
    )


def make_bundle(
    manifest: ProjectManifest,
    bundle_path: Optional[Path] = None,
    include_engine_dirs: bool = True,
) -> Path:
    """Pack a ProjectManifest into a single ZIP. Returns the bundle path.

    Layout inside the zip:
        manifest.txt
        index.json
        README.md
        artifacts/<stage>/<original-filename>
        artifacts/<stage>/<dir-name>/...   (for engine projects)
    """
    index = build_index(manifest)
    readme = _readme(manifest, index)
    manifest_txt = manifest.summary()

    if bundle_path is None:
        slug = "".join(c if c.isalnum() else "_" for c in manifest.title.lower()).strip("_")
        bundle_path = manifest.workdir.parent / f"{slug}_bundle_{int(time.time())}.zip"

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.txt", manifest_txt)
        zf.writestr("index.json", json.dumps(index, indent=2))
        zf.writestr("README.md", readme)
        # Track seen arcnames to avoid duplicate-name warnings when stages
        # produce files with colliding millisecond timestamps.
        seen: Dict[str, int] = {}
        def _unique(arcname: str) -> str:
            if arcname not in seen:
                seen[arcname] = 1
                return arcname
            seen[arcname] += 1
            n = seen[arcname]
            p = Path(arcname)
            return str(p.with_name(f"{p.stem}__{n}{p.suffix}"))
        for idx_i, stage in enumerate(manifest.stages):
            for art_path in stage.artifacts:
                p = Path(art_path)
                if not p.exists():
                    continue
                if p.is_dir():
                    if not include_engine_dirs:
                        continue
                    for child in p.rglob("*"):
                        if child.is_file():
                            rel = child.relative_to(p.parent)
                            zf.write(child,
                                     arcname=_unique(f"artifacts/{stage.stage}/{rel}"))
                else:
                    zf.write(p, arcname=_unique(f"artifacts/{stage.stage}/{p.name}"))
    return bundle_path


def make_bundle_dir(
    manifest: ProjectManifest,
    out_dir: Optional[Path] = None,
) -> Path:
    """Same content as make_bundle but laid out on disk (no zip)."""
    index = build_index(manifest)
    readme = _readme(manifest, index)
    manifest_txt = manifest.summary()

    if out_dir is None:
        slug = "".join(c if c.isalnum() else "_" for c in manifest.title.lower()).strip("_")
        out_dir = manifest.workdir.parent / f"{slug}_bundle_{int(time.time())}"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.txt").write_text(manifest_txt, encoding="utf-8")
    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    for stage in manifest.stages:
        stage_dir = out_dir / "artifacts" / stage.stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        for art_path in stage.artifacts:
            p = Path(art_path)
            if not p.exists():
                continue
            if p.is_dir():
                shutil.copytree(p, stage_dir / p.name, dirs_exist_ok=True)
            else:
                shutil.copy2(p, stage_dir / p.name)
    return out_dir
