#!/usr/bin/env python3
"""Verify AAA pipeline artifacts and acceptance reports.

Usage::

    python scripts/verify_slice.py <project-root>
    python scripts/verify_slice.py <project-root> --json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_MANIFESTS = (
    "pipeline_manifest.json",
    "manifests/world_manifest.json",
    "manifests/asset_manifest.json",
    "manifests/world_systems.json",
    "checkpoints/pipeline_checkpoint.json",
    "provenance/provenance_index.json",
    "reports/acceptance_report.json",
)

REQUIRED_UE5 = (
    "Config/DefaultEngine.ini",
    "Config/DefaultScalability.ini",
    "Config/WorldPartition.ini",
)


def verify(project_root: str | Path) -> dict:
    root = Path(project_root)
    if not root.is_dir():
        return {"ok": False, "reason": "project root does not exist", "failures": ["root_missing"]}

    failures: list[str] = []
    present: list[str] = []

    for rel in REQUIRED_MANIFESTS:
        path = root / rel
        if path.is_file() and path.stat().st_size > 0:
            present.append(rel)
        else:
            failures.append(f"missing:{rel}")

    ue5_dir = root / "ue5_project"
    if ue5_dir.is_dir():
        uprojects = list(ue5_dir.glob("*.uproject"))
        if not uprojects:
            failures.append("missing:ue5_project/*.uproject")
        else:
            present.append(str(uprojects[0].relative_to(root)))
        for rel in REQUIRED_UE5:
            path = ue5_dir / rel
            if path.is_file() and path.stat().st_size > 0:
                present.append(f"ue5_project/{rel}")
            else:
                failures.append(f"missing:ue5_project/{rel}")
    else:
        failures.append("missing:ue5_project/")

    acceptance_path = root / "reports" / "acceptance_report.json"
    acceptance_data = {}
    if acceptance_path.is_file():
        acceptance_data = json.loads(acceptance_path.read_text(encoding="utf-8"))
        if acceptance_data.get("benchmark_claim") and acceptance_data.get("evidence_complete") is False:
            pass
        elif acceptance_data.get("evidence_complete") and not acceptance_data.get("render_comparisons"):
            failures.append("fabricated:render_evidence")

    previs_path = root / "previs" / "previs_manifest.json"
    if previs_path.is_file():
        previs = json.loads(previs_path.read_text(encoding="utf-8"))
        if previs.get("authoritative"):
            failures.append("previs_marked_authoritative")

    return {
        "ok": not failures,
        "project_root": str(root),
        "present": present,
        "failures": failures,
        "acceptance": {
            "evidence_complete": acceptance_data.get("evidence_complete"),
            "benchmark_claim": acceptance_data.get("benchmark_claim", "")[:120],
        },
        "reason": "ok" if not failures else "verification failed",
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    json_out = "--json" in args
    paths = [a for a in args if a != "--json"]
    if len(paths) != 1:
        print(json.dumps({"ok": False, "reason": "usage: verify_slice.py <project-root> [--json]"}))
        return 2
    result = verify(paths[0])
    if json_out:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
