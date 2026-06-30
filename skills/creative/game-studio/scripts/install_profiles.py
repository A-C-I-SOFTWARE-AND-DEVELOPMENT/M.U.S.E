#!/usr/bin/env python3
"""Bootstrap the Game Studio engine worker profiles into config.yaml.

Turns the documented engine profiles (`game-godot` / `game-ue5` / `game-unity`)
into real worker profiles that `/orchestrate` + `kanban_decompose` can route to
by name.

Safe by default: this **dry-runs** and prints the YAML it would add. Writing
config is a config change, so it only happens with `--apply`, only adds
profiles that are missing (idempotent; `--force` to overwrite), and backs the
original up to ``<config>.bak`` first.

Usage::

    python install_profiles.py                # dry-run: show the snippet
    python install_profiles.py --apply        # merge missing profiles into config
    python install_profiles.py --apply --force  # also overwrite existing ones
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

# Engine worker profiles. Model is a generic provider:family — change it to
# whatever you run. Only `game-godot` builds headlessly without a GPU/licence.
PROFILES = {
    "game-godot": {
        "model": "anthropic:claude-opus",
        "enabled_toolsets": ["terminal", "files", "image_gen", "video_gen", "asset3d_gen"],
        "preloaded_skills": ["game-studio", "comfyui"],
        "environment": "local",
        "environment_config": {"gpu": False, "image": ""},
    },
    "game-ue5": {
        "model": "anthropic:claude-opus",
        "enabled_toolsets": ["terminal", "files", "image_gen", "video_gen", "asset3d_gen"],
        "preloaded_skills": ["game-studio", "ue5-render", "comfyui"],
        "environment": "local",
        "environment_config": {"gpu": True, "image": ""},
    },
    "game-unity": {
        "model": "anthropic:claude-opus",
        "enabled_toolsets": ["terminal", "files", "image_gen", "asset3d_gen"],
        "preloaded_skills": ["game-studio"],
        "environment": "local",
        "environment_config": {"gpu": True},
    },
}


def _default_config_path() -> Path:
    home = os.environ.get("HERMES_HOME")
    base = Path(home) if home else Path.home() / ".hermes"
    return base / "config.yaml"


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Could not parse {path}: {exc}")


def plan(existing: dict, force: bool) -> dict:
    """Return the profiles that would be added (missing, or all if force)."""
    have = existing.get("profiles") or {}
    have = have if isinstance(have, dict) else {}
    return {
        name: spec for name, spec in PROFILES.items()
        if force or name not in have
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Game Studio engine profiles.")
    parser.add_argument("--config", default=None, help="Path to config.yaml (default: $HERMES_HOME/config.yaml).")
    parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry-run).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing game-* profiles.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _default_config_path()
    existing = _load(cfg_path)
    to_add = plan(existing, args.force)

    if not to_add:
        msg = {"config": str(cfg_path), "added": [], "note": "all engine profiles already present"}
        print(json.dumps(msg, indent=2) if args.json else f"Nothing to do — {msg['note']} ({cfg_path}).")
        return 0

    snippet = {"profiles": to_add}
    if not args.apply:
        if args.json:
            print(json.dumps({"config": str(cfg_path), "would_add": list(to_add), "apply": False}, indent=2))
        else:
            print(f"# Dry-run — add to {cfg_path} (re-run with --apply to write):\n")
            print(yaml.safe_dump(snippet, sort_keys=False))
        return 0

    # --apply: merge + write, backing up first.
    merged = dict(existing)
    profiles = dict(merged.get("profiles") or {})
    profiles.update(to_add)
    merged["profiles"] = profiles

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.is_file():
        backup = cfg_path.with_suffix(cfg_path.suffix + ".bak")
        backup.write_text(cfg_path.read_text())
    cfg_path.write_text(yaml.safe_dump(merged, sort_keys=False))

    result = {"config": str(cfg_path), "added": list(to_add), "apply": True}
    print(json.dumps(result, indent=2) if args.json else
          f"Wrote {len(to_add)} profile(s) to {cfg_path}: {', '.join(to_add)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
