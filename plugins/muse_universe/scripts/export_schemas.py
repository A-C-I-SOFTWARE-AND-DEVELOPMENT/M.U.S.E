from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.muse_universe.models import (  # noqa: E402
    CommandResult,
    UniverseCommand,
    UniverseEvent,
)


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
SCHEMAS = {
    "command_result.schema.json": CommandResult,
    "universe_command.schema.json": UniverseCommand,
    "universe_event.schema.json": UniverseEvent,
}


def _render_schema(model: type[CommandResult | UniverseCommand | UniverseEvent]) -> str:
    return json.dumps(
        model.model_json_schema(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def export_schemas(*, check: bool) -> int:
    stale: list[str] = []
    for filename, model in SCHEMAS.items():
        path = SCHEMA_DIR / filename
        rendered = _render_schema(model)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                stale.append(filename)
            continue
        SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")

    if stale:
        print(f"schema files are missing or stale: {', '.join(stale)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Export MUSE Universe JSON schemas.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated schemas without changing files.",
    )
    args = parser.parse_args()
    return export_schemas(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
