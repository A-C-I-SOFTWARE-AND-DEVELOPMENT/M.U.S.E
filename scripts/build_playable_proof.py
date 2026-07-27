#!/usr/bin/env python3
"""Build, package, and smoke-test an original UE5.8 proof game."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default=(
            'Frontier Hunt: a stylized realism action RPG set in an original '
            "ancient forest frontier where a ranger tracks creatures, recovers "
            "three relics, and activates a beacon."
        ),
    )
    parser.add_argument("--out", default="proof_game_output")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from agent.studio.game_foundry import GameFoundry
    from agent.studio.local_toolchain import generate_frontier_asset_pack
    from agent.studio.prompt_spec import (
        parse_vertical_slice_prompt,
        to_game_production_spec,
    )

    slice_spec = parse_vertical_slice_prompt(args.prompt)
    production_spec = to_game_production_spec(slice_spec)
    output_root = Path(args.out).resolve()
    project_root = output_root / slice_spec.project_id
    assets, asset_report = generate_frontier_asset_pack(project_root)
    if not asset_report.get("ok"):
        print(
            json.dumps(
                {
                    "project_id": slice_spec.project_id,
                    "root": str(project_root),
                    "playable": False,
                    "error": "frontier_asset_generation_failed",
                    "asset_report": asset_report,
                },
                indent=2,
            )
        )
        return 1
    previous = os.environ.get("MUSE_GAME_ALLOW_SPAWN")
    os.environ["MUSE_GAME_ALLOW_SPAWN"] = "1"
    try:
        manifest = GameFoundry(output_root).build_vertical_slice(
            production_spec,
            allow_spawn=True,
            resume=not args.no_resume,
        )
    finally:
        if previous is None:
            os.environ.pop("MUSE_GAME_ALLOW_SPAWN", None)
        else:
            os.environ["MUSE_GAME_ALLOW_SPAWN"] = previous

    payload = {
        "project_id": manifest.project_id,
        "root": str(manifest.root),
        "engine_version": manifest.engine_version,
        "engine_validation": manifest.engine_validation,
        "compiled": manifest.compiled,
        "package_verified": manifest.package_verified,
        "smoke_verified": manifest.smoke_verified,
        "playable": manifest.playable,
        "gate_results": list(manifest.gate_results),
        "generated_assets": {name: str(path) for name, path in assets.items()},
        "asset_report": asset_report,
        "unavailable_reason": manifest.unavailable_reason,
    }
    print(json.dumps(payload, indent=2))
    return 0 if manifest.playable else 1


if __name__ == "__main__":
    raise SystemExit(main())
