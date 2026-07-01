#!/usr/bin/env python3
"""Run the muse Game Studio production pipeline from a one-line brief.

Thin, owner-friendly CLI over the existing `agent/studio/` production DAG
(`StudioOrchestrator.produce_game`). Turns a brief into the full set of
generative stages (GDD → narrative → concept art → 3D meshes → gameplay code →
audio → engine scaffold), reusing whatever backends are configured. Every stage
is **stub-safe**: with no API keys the DAG dry-runs end-to-end and emits JSON
manifests describing what *would* be generated, so you can see the whole shape
before spending a cent.

Usage::

    python run_pipeline.py --title "Aether Drift" --genre "sci-fi explorer" \
        --engine godot --setting "a derelict orbital ring" \
        --core-loop "scan, salvage, upgrade, survive" [--offline] [--json]

Honest framing: this drives the *pipeline*; it does not by itself ship a
finished AAA game. For a runnable artifact today, target Godot and pair this
with the reference slice + `export_godot_slice.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ENGINE_TO_PROVIDER = {"godot": "GODOT4", "ue5": "UE5", "unity": "UNITY6"}


def _build_brief(args, GameBrief, Provider, Quality):
    provider = getattr(Provider, _ENGINE_TO_PROVIDER.get(args.engine, "GODOT4"))
    try:
        quality = Quality[args.quality.upper()]
    except (KeyError, AttributeError):
        quality = Quality.PREVIZ
    return GameBrief(
        title=args.title,
        genre=args.genre,
        target=args.target,
        perspective=args.perspective,
        setting=args.setting,
        core_loop=args.core_loop,
        art_style=args.art_style,
        quality=quality,
        engine=provider,
        workdir=Path(args.out) if args.out else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Game Studio production pipeline.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--genre", required=True)
    parser.add_argument("--engine", default="godot", choices=["godot", "ue5", "unity"])
    parser.add_argument("--setting", default="")
    parser.add_argument("--core-loop", dest="core_loop", default="")
    parser.add_argument("--perspective", default="third-person")
    parser.add_argument("--art-style", dest="art_style", default="stylized realism")
    parser.add_argument("--target", default="PC")
    parser.add_argument("--quality", default="previz")
    parser.add_argument("--out", default=None, help="Output root directory (default: a studio temp dir).")
    parser.add_argument("--offline", action="store_true",
                        help="Pin every backend to its stub fallback (no network/spend).")
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary instead of text.")
    args = parser.parse_args(argv)

    if args.offline:
        os.environ["AXIOM_STUDIO_OFFLINE"] = "1"

    try:
        from agent.studio import GameBrief, Provider, Quality, StudioOrchestrator
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"could not import studio engine: {exc}"}))
        return 2

    brief = _build_brief(args, GameBrief, Provider, Quality)
    root = Path(args.out) if args.out else None
    studio = StudioOrchestrator(root=root) if root else StudioOrchestrator()
    manifest = studio.produce_game(brief)

    failed = [s for s in manifest.stages if s.status == "failed"]
    if args.json:
        print(json.dumps({
            "title": manifest.title,
            "engine": args.engine,
            "workdir": str(manifest.workdir),
            "stage_count": len(manifest.stages),
            "failed": [s.stage for s in failed],
            "total_cost_usd": manifest.total_cost_usd,
            "stages": [
                {"stage": s.stage, "status": s.status,
                 "provider": s.provider.value, "notes": s.notes}
                for s in manifest.stages
            ],
        }, indent=2))
    else:
        print(manifest.summary())
        if args.engine == "godot":
            print("\nNote: for a runnable artifact, export the reference slice "
                  "(scripts/export_godot_slice.py) — the studio scaffold is a "
                  "starting point, the slice is the playable proof.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
