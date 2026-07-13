#!/usr/bin/env python3
"""Sync the vertical slice's game elements and build evidence into muse.

Bridges the Game Studio reference slice to the muse universe through the
existing ``plugins.muse_universe.achievements.AchievementBridge`` — no new
primitives. The slice's contract is ``slice-manifest.json`` (kept truthful by
``tests/skills/test_game_studio_muse_sync.py``); a verified build becomes a
completed *simulation* mission whose evidence references are the artifact
hashes, and the outbox envelope is recorded through the achievements
external-evidence seam when that plugin is installed.

Usage::

    python sync_slice_to_muse.py [--artifact PATH] [--dry-run]

Emits one JSON object::

    {"synced": bool, "outbox": {...}|null, "record": {...}|null,
     "reason": str, "manifest_id": str}

``--dry-run`` builds and prints the outbox without recording anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SLICE = Path(__file__).resolve().parents[1] / "reference-slice"
_MANIFEST = _SLICE / "slice-manifest.json"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from plugins.muse_universe.achievements import AchievementBridge  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path = _MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_mission(manifest: dict, artifact: Path) -> dict:
    """Map a verified build of the slice onto the mission shape the
    achievements bridge accepts. Fails closed: no artifact, no mission."""
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise FileNotFoundError(f"build artifact missing or empty: {artifact}")
    muse = manifest["muse"]
    artifact_hash = _sha256(artifact)
    evidence = [
        f"sha256:{artifact_hash}:{artifact.name}",
        f"elements:{manifest['elements']['objective']}:"
        f"{manifest['elements']['collectibles']}-collectibles",
        f"engine:{manifest['engine']['name']}-{manifest['engine']['version']}",
    ]
    pck = artifact.with_suffix(".pck")
    if pck.is_file() and pck.stat().st_size > 0:
        evidence.insert(1, f"sha256:{_sha256(pck)}:{pck.name}")
    return {
        "id": f"{manifest['id']}-build-{artifact_hash[:12]}",
        "state": "completed",
        "mode": muse["mode"],
        "evidence_label": muse["evidence_label"],
        "evidence": evidence,
        "source_type": muse["source_type"],
        "source_id": muse["source_id"],
    }


def sync(
    artifact: Path,
    *,
    bridge: AchievementBridge | None = None,
    dry_run: bool = False,
    occurred_at: str | None = None,
) -> dict:
    manifest = load_manifest()
    mission = build_mission(manifest, artifact)
    active = bridge if bridge is not None else AchievementBridge()
    outbox = active.outbox_for(
        mission,
        realm_id=manifest["muse"]["realm_id"],
        command_id=f"cmd-slice-sync-{mission['id']}",
    )
    result = {
        "manifest_id": manifest["id"],
        "outbox": outbox,
        "record": None,
        "synced": False,
        "reason": "",
    }
    if outbox is None:
        result["reason"] = (
            "no outbox produced (bridge disabled, adapter missing, or the "
            "mission failed the completed/evidence/simulation-label rules)"
        )
        return result
    if dry_run:
        result["reason"] = "dry run — outbox built, nothing recorded"
        return result
    stamp = occurred_at or datetime.fromtimestamp(
        artifact.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    record = active.record_outbox(outbox, occurred_at=stamp)
    result["record"] = record
    result["synced"] = record is not None
    result["reason"] = (
        "recorded through the achievements external-evidence seam"
        if record is not None
        else "adapter rejected or unavailable — evidence not recorded"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync the slice build into muse.")
    parser.add_argument(
        "--artifact",
        default=str(_SLICE / "build" / "slice.x86_64"),
        help="Exported build artifact (default: reference-slice/build/slice.x86_64).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the outbox envelope without recording it.",
    )
    args = parser.parse_args(argv)
    try:
        result = sync(Path(args.artifact).resolve(), dry_run=args.dry_run)
    except FileNotFoundError as exc:
        result = {
            "manifest_id": None,
            "outbox": None,
            "record": None,
            "synced": False,
            "reason": str(exc),
        }
    print(json.dumps(result, indent=2))
    return 0 if result["synced"] or (args.dry_run and result["outbox"]) else 1


if __name__ == "__main__":
    sys.exit(main())
