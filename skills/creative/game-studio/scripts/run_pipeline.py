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
finished AAA game. For high-fidelity UE5 production, use
`scripts/run_pipeline.py` at the repo root (AAA pipeline with typed manifests,
checkpoints, and acceptance gates). For a runnable Godot artifact today,
target Godot and pair this with the reference slice + `export_godot_slice.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Prefer the active M.U.S.E checkout over an older site-packages/install copy.
for _candidate in (
    Path(os.environ.get("MUSE_ROOT", "")).expanduser(),
    Path.cwd(),
    Path.home() / "M.U.S.E",
    Path(__file__).resolve().parents[4],
):
    if (_candidate / "agent" / "studio" / "__init__.py").is_file():
        _value = str(_candidate.resolve())
        if _value in sys.path:
            sys.path.remove(_value)
        sys.path.insert(0, _value)
        break

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
    parser.add_argument("--title", default="")
    parser.add_argument("--genre", default="")
    parser.add_argument(
        "--prompt",
        default="",
        help="One natural-language game prompt (used by --vertical-slice).",
    )
    parser.add_argument(
        "--vertical-slice",
        action="store_true",
        help="Generate a source-complete UE5.8 vertical slice.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run owner-gated UE compile/map/audit/package/smoke gates.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-run passed build gates instead of using verified gate state.",
    )
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

    if args.vertical_slice:
        if not args.prompt:
            parser.error("--vertical-slice requires --prompt")
        if args.engine != "ue5":
            parser.error("--vertical-slice currently targets --engine ue5")
        try:
            from agent.studio import (
                GameFoundry,
                parse_vertical_slice_prompt,
                to_game_production_spec,
            )
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"error": f"could not import vertical-slice engine: {exc}"}))
            return 2
        try:
            vertical = parse_vertical_slice_prompt(args.prompt)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            return 2
        production = to_game_production_spec(vertical)
        root = Path(args.out) if args.out else Path.cwd() / "studio_output" / "vertical-slices"
        foundry = GameFoundry(root)
        if args.build:
            manifest = foundry.build_vertical_slice(
                production,
                allow_spawn=os.environ.get("MUSE_GAME_ALLOW_SPAWN") == "1",
                resume=not args.no_resume,
            )
        else:
            manifest = foundry.create(production)
        result = {
            "title": manifest.title,
            "project_id": manifest.project_id,
            "engine": manifest.engine,
            "engine_version": manifest.engine_version,
            "root": str(manifest.root),
            "compiled": manifest.compiled,
            "package_verified": manifest.package_verified,
            "smoke_verified": manifest.smoke_verified,
            "playable": manifest.playable,
            "engine_validation": manifest.engine_validation,
            "unavailable_reason": manifest.unavailable_reason,
            "gate_results": list(manifest.gate_results),
            "manifest": str(manifest.root / "game-build-manifest.json"),
        }
        print(json.dumps(result, indent=2))
        if args.build and not manifest.playable:
            return 3
        return 0

    if not args.title or not args.genre:
        parser.error("--title and --genre are required unless --vertical-slice is used")

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
