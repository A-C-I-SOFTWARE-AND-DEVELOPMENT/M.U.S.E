#!/usr/bin/env python3
"""Verify a Game Studio build artifact exists and is non-empty.

Used by `qa-playtest` and the slice smoke test as the "verify, don't vibe"
evidence — a build claim must be backed by a real, non-empty artifact.

Usage::

    python verify_slice.py <artifact-path>

Emits a JSON object and exits non-zero on failure::

    {"ok": bool, "artifact": str, "size_bytes": int, "reason": str}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def verify(artifact: str | Path) -> dict:
    path = Path(artifact)
    if not path.exists():
        return {"ok": False, "artifact": str(path), "size_bytes": 0,
                "reason": "artifact does not exist"}
    if not path.is_file():
        return {"ok": False, "artifact": str(path), "size_bytes": 0,
                "reason": "artifact is not a file"}
    size = path.stat().st_size
    if size <= 0:
        return {"ok": False, "artifact": str(path), "size_bytes": 0,
                "reason": "artifact is empty"}
    return {"ok": True, "artifact": str(path), "size_bytes": size, "reason": "ok"}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(json.dumps({
            "ok": False, "artifact": None, "size_bytes": 0,
            "reason": "usage: verify_slice.py <artifact-path>",
        }))
        return 2
    result = verify(args[0])
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
