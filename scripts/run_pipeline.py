#!/usr/bin/env python3
"""Run the MUSE AAA high-fidelity game production pipeline.

Usage::

    python scripts/run_pipeline.py --title "Frontier Hunt" \\
        --genre "creature-hunting action-RPG" \\
        --profile high_fidelity --offline

    python scripts/run_pipeline.py --creature-hunting --offline --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AAA game production pipeline.")
    parser.add_argument("--title", default="Frontier Hunt")
    parser.add_argument("--genre", default="creature-hunting action-RPG")
    parser.add_argument("--setting", default="vast frontier biomes")
    parser.add_argument("--core-loop", dest="core_loop", default="track, hunt, craft, explore")
    parser.add_argument("--profile", default="high_fidelity",
                        choices=["previz", "high_fidelity", "aaa_benchmark"])
    parser.add_argument("--engine-version", default="5.8",
                        help="Target Unreal Engine version (default: installed UE 5.8)")
    parser.add_argument("--out", default=None, help="Output root directory")
    parser.add_argument("--no-resume", action="store_true",
                        help="Regenerate pipeline stages instead of loading checkpoints")
    parser.add_argument("--offline", action="store_true",
                        help="Offline mode — stub providers, defer UE render evidence")
    parser.add_argument("--creature-hunting", action="store_true",
                        help="Use the representative creature-hunting open-world brief")
    parser.add_argument("--world-previs", action="store_true",
                        help="Generate Reactor/LingBot world previs with UE camera conditioning")
    parser.add_argument("--previs-image", default="",
                        help="Optional source image; Blender renders one when omitted")
    parser.add_argument("--previs-backend", choices=["auto", "lingbot", "reactor"],
                        default="auto")
    parser.add_argument("--execute-blender", action="store_true",
                        help="Run Blender 5.2 and emit a verified procedural proof FBX")
    parser.add_argument("--execute-unreal", action="store_true",
                        help="Compile and author the generated project with local UE5")
    parser.add_argument("--package", action="store_true",
                        help="Cook and package Win64 (implies --execute-unreal)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.offline:
        os.environ["AXIOM_STUDIO_OFFLINE"] = "1"

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from agent.studio.aaa_pipeline import (
            AAAPipeline,
            AAAPipelineBrief,
            run_creature_hunting_pipeline,
        )
    except ImportError as exc:
        print(json.dumps({"error": f"could not import aaa pipeline: {exc}"}))
        return 2

    root = Path(args.out) if args.out else Path.cwd() / "aaa_pipeline_output"

    if args.creature_hunting:
        result = run_creature_hunting_pipeline(
            root,
            title=args.title,
            offline=args.offline,
            engine_version=args.engine_version,
            generate_previs=args.world_previs,
            previs_source_image=args.previs_image,
            previs_backend=args.previs_backend,
            resume=not args.no_resume,
        )
    else:
        brief = AAAPipelineBrief(
            title=args.title,
            genre=args.genre,
            setting=args.setting,
            core_loop=args.core_loop,
            profile=args.profile,
            engine_version=args.engine_version,
            generate_previs=args.world_previs,
            previs_source_image=args.previs_image,
            previs_backend=args.previs_backend,
            offline=args.offline,
        )
        result = AAAPipeline(root, resume=not args.no_resume).run(brief)

    toolchain_payload: dict[str, object] = {}
    toolchain_failed = False
    if args.execute_blender or args.execute_unreal or args.package:
        from agent.studio.local_toolchain import (
            discover_local_toolchain,
            execute_unreal,
            generate_proof_asset,
        )

        toolchain = discover_local_toolchain(args.engine_version)
        toolchain_payload["detected"] = {
            "ready": toolchain.ready,
            "blender": toolchain.blender,
            "unreal": toolchain.unreal.version if toolchain.unreal else "",
            "gpu_name": toolchain.gpu_name,
            "vram_gb": toolchain.vram_gb,
        }
        if args.execute_blender:
            asset_path, report = generate_proof_asset(result.root)
            toolchain_failed = toolchain_failed or not bool(report.get("ok"))
            toolchain_payload["blender"] = {
                "asset": str(asset_path or ""),
                "report": report,
            }
        if args.execute_unreal or args.package:
            records = execute_unreal(
                result.root / "ue5_project",
                engine_version=args.engine_version,
                package=args.package,
            )
            toolchain_payload["unreal"] = [
                {
                    "lane": record.lane,
                    "passed": record.passed,
                    "exit_code": record.exit_code,
                    "stdout_path": record.stdout_path,
                    "stderr_path": record.stderr_path,
                }
                for record in records
            ]
            toolchain_failed = toolchain_failed or not all(record.passed for record in records)

    payload = {
        "project_id": result.project_id,
        "root": str(result.root),
        "profile": result.profile,
        "stages_completed": list(result.pipeline_manifest.stages_completed),
        "stages_failed": list(result.stages_failed),
        "gates_passed": result.gates_passed,
        "acceptance_passed": result.acceptance_report.passed,
        "evidence_complete": result.acceptance_report.evidence_complete,
        "total_cost_usd": result.total_cost_usd,
        "duration_s": round(result.duration_s, 2),
        "benchmark_claim": result.acceptance_report.benchmark_claim,
        "toolchain": toolchain_payload,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Project: {result.project_id}")
        print(f"Root: {result.root}")
        print(f"Profile: {result.profile}")
        print(f"Stages: {', '.join(result.pipeline_manifest.stages_completed)}")
        print(f"Acceptance evidence complete: {result.acceptance_report.evidence_complete}")
        print(f"Duration: {result.duration_s:.1f}s")
        if result.acceptance_report.benchmark_claim:
            print(result.acceptance_report.benchmark_claim)

    return 1 if result.stages_failed or toolchain_failed else 0


if __name__ == "__main__":
    sys.exit(main())
