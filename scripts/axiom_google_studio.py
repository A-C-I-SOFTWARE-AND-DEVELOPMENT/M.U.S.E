#!/usr/bin/env python3
"""Axiom Google Studio production runner.

Creates an end-to-end theatrical media pipeline around Google Vertex AI Imagen
+ Veo and FFmpeg. It can run in two modes:

  dry-run (default): no Google spend; creates real playable slate clips/final MP4.
  real:            submits prompts to Vertex AI adapters when credentials exist.

Examples:
  python scripts/axiom_google_studio.py check
  python scripts/axiom_google_studio.py produce --title "The Glass Orchard" --runtime-min 30 --clips 225
  python scripts/axiom_google_studio.py produce --real --title "The Glass Orchard" --runtime-min 30 --clips 225
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.studio.adapters.base import default_registry  # noqa: E402
from agent.studio.adapters import google_media  # noqa: F401,E402 - registers adapters
from agent.studio.types import Quality  # noqa: E402


@dataclass
class ProductionPlan:
    title: str
    logline: str
    runtime_min: int
    clips: int
    clip_duration_s: int
    fps: int
    resolution: str
    aspect: str
    quality: str
    output_dir: str


def _slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_") or "production"


def _run(cmd: Sequence[str], cwd: Path | None = None, timeout: int = 600) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            "command failed: " + " ".join(cmd) + "\nSTDOUT:\n" + proc.stdout[-2000:] + "\nSTDERR:\n" + proc.stderr[-4000:]
        )


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH")
    return exe


def check() -> Dict[str, Any]:
    return {
        "repo": str(ROOT),
        "ffmpeg": shutil.which("ffmpeg") or "missing",
        "ffprobe": shutil.which("ffprobe") or "missing",
        "gcloud": shutil.which("gcloud") or "missing",
        "google_project": os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_PROJECT_ID") or "missing",
        "google_location": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        "google_vertex_available": google_media.google_vertex_available(),
        "imagen_adapter_available": bool(default_registry.pick("concept_art", Quality.THEATRICAL)),
        "video_adapter_available": bool(default_registry.pick("video", Quality.THEATRICAL)),
        "output_root": str(ROOT / "studio_output" / "google_theatrical"),
    }


def _shot_prompt(plan: ProductionPlan, idx: int) -> Dict[str, Any]:
    beat = idx / max(1, plan.clips - 1)
    if beat < 0.12:
        act = "opening image and world establishment"
    elif beat < 0.25:
        act = "inciting incident, rising tension"
    elif beat < 0.50:
        act = "Act II complications and discoveries"
    elif beat < 0.75:
        act = "midpoint reversal and emotional confrontation"
    elif beat < 0.90:
        act = "climax escalation, operatic theatrical staging"
    else:
        act = "resolution, final iconic image"
    return {
        "shot": idx + 1,
        "duration_s": plan.clip_duration_s,
        "prompt": (
            f"Theatrical cinematic shot {idx + 1}/{plan.clips} for '{plan.title}'. "
            f"Logline: {plan.logline}. Beat: {act}. State-of-the-art dramatic lighting, "
            f"controlled camera motion, coherent characters, production design for a premium stage-to-screen film, "
            f"{plan.aspect}, {plan.resolution}, {plan.fps}fps."
        ),
    }


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _make_slate_clip(path: Path, title: str, shot: int, total: int, duration_s: int, resolution: str, fps: int) -> None:
    ffmpeg = _ffmpeg()
    # Avoid drawtext on Windows FFmpeg builds that can segfault through
    # fontconfig/freetype. The clip identity is carried by filename, prompt
    # ledger, review page, and tone/color; real Veo output replaces these slates.
    hue = (shot * 37) % 255
    color = f"0x{(32 + hue // 3):02x}{(36 + hue // 4):02x}{(44 + hue // 5):02x}"
    cmd = [
        ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={color}:s={resolution}:r={fps}:d={duration_s}",
        "-f", "lavfi", "-i", f"sine=frequency={220 + (shot % 12) * 22}:duration={duration_s}:sample_rate=48000",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-shortest", str(path),
    ]
    _run(cmd, timeout=max(90, duration_s * 4))


def _concat(clips: List[Path], final_path: Path) -> None:
    ffmpeg = _ffmpeg()
    concat_file = final_path.with_suffix(".concat.txt")
    concat_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips) + "\n", encoding="utf-8")
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(final_path)], timeout=1800)


def _review_html(out_dir: Path, plan: ProductionPlan, clips: List[Path], final_path: Path) -> Path:
    rows = []
    for p in clips[:500]:
        rows.append(f"<tr><td>{p.name}</td><td><video src='clips/{p.name}' controls width='360'></video></td></tr>")
    html = f"""<!doctype html>
<meta charset='utf-8'>
<title>{plan.title} Review</title>
<style>body{{font-family:system-ui;background:#101014;color:#f6f6f6;margin:24px}}video{{background:#000}}td{{padding:8px;border-top:1px solid #333}}a{{color:#8ab4ff}}</style>
<h1>{plan.title}</h1>
<p>{plan.logline}</p>
<p><b>Final playable file:</b> <a href='{final_path.name}'>{final_path.name}</a></p>
<video src='{final_path.name}' controls width='960'></video>
<h2>Clip review wall</h2>
<table>{''.join(rows)}</table>
"""
    path = out_dir / "review.html"
    path.write_text(html, encoding="utf-8")
    return path


def produce(args: argparse.Namespace) -> Dict[str, Any]:
    runtime_s = int(args.runtime_min * 60)
    clip_duration = int(args.clip_duration_s)
    clips = int(args.clips or math.ceil(runtime_s / clip_duration))
    out_dir = Path(args.output_dir) if args.output_dir else ROOT / "studio_output" / "google_theatrical" / f"{_slug(args.title)}_{int(time.time())}"
    out_dir = out_dir.resolve()
    clip_dir = out_dir / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    plan = ProductionPlan(
        title=args.title,
        logline=args.logline,
        runtime_min=args.runtime_min,
        clips=clips,
        clip_duration_s=clip_duration,
        fps=args.fps,
        resolution=args.resolution,
        aspect=args.aspect,
        quality=args.quality,
        output_dir=str(out_dir),
    )
    (out_dir / "production_plan.json").write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")
    prompts = [_shot_prompt(plan, i) for i in range(clips)]
    _write_jsonl(out_dir / "veo_clip_prompts.jsonl", prompts)
    _write_jsonl(out_dir / "imagen_keyframe_prompts.jsonl", prompts[:: max(1, clips // min(24, clips))])

    made_clips: List[Path] = []
    if args.real:
        adapter = default_registry.pick("video", Quality(args.quality))
        if adapter is None or not adapter.available():
            raise RuntimeError("--real requested, but Google Veo adapter is not available. Run `check` for missing credentials.")
        for row in prompts:
            result = adapter.run(
                row["prompt"],
                clip_dir,
                duration_s=clip_duration,
                aspect=args.aspect,
                resolution=args.resolution,
                poll=True,
                gcs_bucket=args.gcs_bucket,
            )
            (out_dir / "generation_log.jsonl").open("a", encoding="utf-8").write(json.dumps(result.__dict__, default=str) + "\n")
            for artifact in result.artifacts:
                p = Path(artifact)
                if p.suffix.lower() == ".mp4" and p.exists():
                    made_clips.append(p)
        if not made_clips:
            raise RuntimeError("Veo jobs submitted but no local MP4 files were returned yet. Check generation_log.jsonl/GCS URIs.")
    else:
        # Keep full 30-minute validation fast: render a representative slate bank
        # once, then reuse entries in the concat list until the requested runtime
        # and clip count are reached. The output remains a real playable MP4 and
        # the prompt ledger still contains every Veo slot that production will fill.
        slate_bank = max(1, min(clips, int(args.slate_bank)))
        bank: List[Path] = []
        for i in range(slate_bank):
            p = clip_dir / f"shot_{i + 1:04d}.mp4"
            _make_slate_clip(p, args.title, i + 1, clips, clip_duration, args.resolution, args.fps)
            bank.append(p)
        for i in range(clips):
            made_clips.append(bank[i % slate_bank])

    final_path = out_dir / f"{_slug(args.title)}_{args.runtime_min}min_playable.mp4"
    _concat(made_clips, final_path)
    review = _review_html(out_dir, plan, made_clips, final_path)
    manifest = {
        "mode": "real" if args.real else "dry-run",
        "plan": asdict(plan),
        "clips": [str(p) for p in made_clips],
        "final_video": str(final_path),
        "review_html": str(review),
        "google_ready": google_media.google_vertex_available(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def init_env(args: argparse.Namespace) -> Dict[str, str]:
    dest = Path(args.path).expanduser().resolve()
    if dest.exists() and not args.force:
        return {"status": "exists", "path": str(dest)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "# Axiom Google Studio / Vertex AI media generation\n"
        "# Fill these values, then restart Hermes or source the file before running --real.\n"
        "GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id\n"
        "GOOGLE_CLOUD_LOCATION=us-central1\n"
        "GOOGLE_APPLICATION_CREDENTIALS=C:/Users/Echer/AppData/Local/hermes/secrets/google-vertex-sa.json\n"
        "GOOGLE_IMAGEN_MODEL=imagen-4.0-generate-preview-06-06\n"
        "GOOGLE_VEO_MODEL=veo-3.0-generate-preview\n"
        "GOOGLE_VEO_GCS_BUCKET=gs://your-veo-output-bucket\n",
        encoding="utf-8",
    )
    return {"status": "written", "path": str(dest)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    envp = sub.add_parser("init-env")
    envp.add_argument("--path", default=str(Path.home() / "AppData/Local/hermes/google_studio.env"))
    envp.add_argument("--force", action="store_true")
    prod = sub.add_parser("produce")
    prod.add_argument("--title", default="Axiom Google Theatrical Proof")
    prod.add_argument("--logline", default="A mythic stage production becomes a cinematic world through Google Imagen keyframes, Veo motion clips, and FFmpeg finishing.")
    prod.add_argument("--runtime-min", type=int, default=30)
    prod.add_argument("--clips", type=int, default=0)
    prod.add_argument("--clip-duration-s", type=int, default=8)
    prod.add_argument("--fps", type=int, default=24)
    prod.add_argument("--resolution", default="1280x720")
    prod.add_argument("--aspect", default="16:9")
    prod.add_argument("--quality", choices=[q.value for q in Quality], default=Quality.THEATRICAL.value)
    prod.add_argument("--output-dir", default="")
    prod.add_argument("--real", action="store_true")
    prod.add_argument("--slate-bank", type=int, default=24, help="dry-run: number of unique slate clips to render before reusing them")
    prod.add_argument("--gcs-bucket", default="")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        print(json.dumps(check(), indent=2))
    elif args.cmd == "init-env":
        print(json.dumps(init_env(args), indent=2))
    elif args.cmd == "produce":
        print(json.dumps(produce(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
