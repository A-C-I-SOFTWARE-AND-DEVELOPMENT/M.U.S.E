from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "provenance.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _updated_manifest() -> dict[str, object]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assets = data.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("provenance assets must be a list")
    for record in assets:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError("every provenance asset requires a relative path")
        path = (ROOT / record["path"]).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            raise ValueError(f"asset path escapes or is missing: {record['path']}")
        record["sha256"] = _sha256(path)
    data["assets"] = sorted(assets, key=lambda record: str(record["path"]))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Atlas Crown provenance")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    updated = _updated_manifest()
    encoded = json.dumps(updated, indent=2, sort_keys=True) + "\n"
    current = MANIFEST.read_text(encoding="utf-8")
    if args.check:
        if current != encoded:
            print("Atlas Crown provenance hashes or ordering are stale")
            return 1
        print("Atlas Crown provenance is current")
        return 0
    MANIFEST.write_text(encoded, encoding="utf-8")
    print("Updated Atlas Crown provenance hashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

