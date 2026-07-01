"""Source-backed permanent agent registry for GPT and Codex.

The canonical agent lists live in the AOS Enterprise Council registry markdown
files. This module makes those registries machine-readable without duplicating
hundreds of agent bodies into a second source of truth.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
TOP_LEVEL_REGISTRY = REPO_ROOT / "skills/aos-enterprise-council/registry/AOS_AGENT_REGISTRY_COMPLETE.md"
SUB_AGENT_REGISTRY = REPO_ROOT / "skills/aos-enterprise-council/registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md"

_BULLET_RE = re.compile(
    r"^- \*\*`(?P<name>[^`]+)`\*\*(?: \([^)]*\))?\s+[—-]\s+(?P<description>.*)$"
)
_TABLE_RE = re.compile(
    r"^\| \*\*`(?P<name>[^`]+)`\*\* \| `(?P<source>[^`]+)` \| (?P<description>.*?) \|$"
)
_HEADING_RE = re.compile(r"^(?P<level>#{2,3})\s+(?P<title>.+?)\s*$")


@dataclass(frozen=True)
class RegistryEntry:
    """One registered top-level agent or sub-agent role."""

    name: str
    slug: str
    kind: str
    category: str
    bucket: str
    description: str
    source_registry: str
    source_file: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return slug.strip("-")


def _parse_registry(path: Path, *, kind: str) -> list[RegistryEntry]:
    if not path.is_file():
        raise FileNotFoundError(f"registry file not found: {path}")

    entries: list[RegistryEntry] = []
    category = ""
    bucket = ""
    rel_path = path.relative_to(REPO_ROOT).as_posix()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        heading = _HEADING_RE.match(line)
        if heading:
            title = heading.group("title").strip()
            if heading.group("level") == "##":
                category = title
                bucket = ""
            else:
                bucket = title
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            name = bullet.group("name").strip()
            entries.append(
                RegistryEntry(
                    name=name,
                    slug=_slugify(name),
                    kind=kind,
                    category=category,
                    bucket=bucket,
                    description=bullet.group("description").strip(),
                    source_registry=rel_path,
                )
            )
            continue

        table = _TABLE_RE.match(line)
        if table:
            name = table.group("name").strip()
            entries.append(
                RegistryEntry(
                    name=name,
                    slug=_slugify(name),
                    kind=kind,
                    category=category,
                    bucket=bucket or "table",
                    description=table.group("description").strip(),
                    source_registry=rel_path,
                    source_file=table.group("source").strip(),
                )
            )

    return entries


def load_registry_entries() -> list[RegistryEntry]:
    """Load every source-backed registry entry, including aliases."""

    return [
        *_parse_registry(TOP_LEVEL_REGISTRY, kind="top_level_agent"),
        *_parse_registry(SUB_AGENT_REGISTRY, kind="sub_agent"),
    ]


def load_unique_roles(entries: Iterable[RegistryEntry] | None = None) -> list[RegistryEntry]:
    """Return one entry per slug, preserving first source order."""

    seen: set[tuple[str, str]] = set()
    unique: list[RegistryEntry] = []
    for entry in entries if entries is not None else load_registry_entries():
        key = (entry.kind, entry.slug)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


def registry_summary(entries: Iterable[RegistryEntry] | None = None) -> dict[str, int]:
    """Return compact counts used by tests and cockpit/debug surfaces."""

    loaded = list(entries if entries is not None else load_registry_entries())
    unique = load_unique_roles(loaded)
    return {
        "entries_total": len(loaded),
        "unique_roles_total": len(unique),
        "unique_top_level_agents": len([e for e in unique if e.kind == "top_level_agent"]),
        "unique_sub_agents": len([e for e in unique if e.kind == "sub_agent"]),
    }


def export_registry_json(output_path: str | Path) -> Path:
    """Write the full unique registry to ``output_path`` as JSON."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "source_registries": [
            TOP_LEVEL_REGISTRY.relative_to(REPO_ROOT).as_posix(),
            SUB_AGENT_REGISTRY.relative_to(REPO_ROOT).as_posix(),
        ],
        "summary": registry_summary(),
        "roles": [entry.to_dict() for entry in load_unique_roles()],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the Codex/GPT permanent MUSE agent registry.")
    parser.add_argument("--write-json", metavar="PATH", help="write the unique registry to PATH")
    parser.add_argument("--summary", action="store_true", help="print summary counts only")
    args = parser.parse_args()

    if args.write_json:
        path = export_registry_json(args.write_json)
        print(path)
        return 0

    payload = registry_summary() if args.summary else [entry.to_dict() for entry in load_unique_roles()]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
