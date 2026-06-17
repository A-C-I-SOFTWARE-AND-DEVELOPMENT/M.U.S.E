#!/usr/bin/env python3
"""Collapse the per-tool reports in docs/_generated/health/ into summary.json.

Read by the `/health` command and (optionally) surfaced at SessionStart. Tolerant
of missing reports — only present tools contribute. Pure stdlib; no third-party
imports so it runs anywhere the repo runs.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

HEALTH = Path("docs/_generated/health")


def _load_json(name: str):
    path = HEALTH / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8") or "null")
    except (ValueError, OSError):
        return None


def _read_text(name: str) -> str:
    path = HEALTH / name
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def main() -> int:
    HEALTH.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "quality_paths": os.environ.get("QUALITY_PATHS", "").split(),
        "gate_failed": os.environ.get("GATE_FAIL", "0") != "0",
    }

    ruff = _load_json("ruff.json")
    if isinstance(ruff, list):
        summary["ruff_violations"] = len(ruff)

    bandit = _load_json("bandit.json")
    if isinstance(bandit, dict):
        results = bandit.get("results")
        if isinstance(results, list):
            summary["bandit_issues"] = len(results)

    todos = _read_text("todos.txt")
    if todos:
        summary["todo_count"] = sum(1 for line in todos.splitlines() if line.strip())

    interrogate = _read_text("interrogate.txt")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", interrogate)
    if m:
        summary["docstring_coverage_pct"] = float(m.group(1))

    xenon = _read_text("xenon.txt")
    if xenon.strip():
        summary["xenon_blocks"] = [
            line.strip() for line in xenon.splitlines() if line.strip()
        ][:20]

    ty = _read_text("ty.txt")
    if ty.strip():
        # ty prints a trailing "Found N diagnostics" style line; capture a count.
        mt = re.search(r"(\d+)\s+(?:diagnostic|error)", ty)
        if mt:
            summary["ty_diagnostics"] = int(mt.group(1))

    vulture = _read_text("vulture.txt")
    if vulture.strip():
        summary["vulture_findings"] = sum(
            1 for line in vulture.splitlines() if line.strip()
        )

    out = HEALTH / "summary.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
