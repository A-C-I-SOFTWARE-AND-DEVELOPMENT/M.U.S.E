#!/usr/bin/env python3
"""Verify AOS registry classification hygiene.

The script is local-only and stdlib-only. It reports missing optional registry
paths as warnings so it can run before the registry cleanup PR is complete.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AOS_ROOT = ROOT / "skills" / "aos-enterprise-council"

EXPECTED_PATHS = {
    "runnable_agents": AOS_ROOT / "runnable-agents",
    "skills": AOS_ROOT / "skills",
    "workers": AOS_ROOT / "workers",
    "personas": AOS_ROOT / "personas",
    "product_roles": AOS_ROOT / "product-roles",
    "archive": AOS_ROOT / "archive",
    "operating_registry": AOS_ROOT / "operating-registry",
}

REFERENCE_ONLY_DIRS = [
    EXPECTED_PATHS["personas"],
    EXPECTED_PATHS["product_roles"],
]

PLACEHOLDER_PATTERNS = ["TODO", "TBD", "FIXME", "lorem ipsum", "<insert", "<todo"]


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ": " in line and not line.startswith(" "):
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip().strip('"')
    return fields


def check(condition: bool, label: str, failures: list[str], warnings: list[str] | None = None, warn: bool = False) -> None:
    if condition:
        print(f"PASS {label}")
    elif warn and warnings is not None:
        print(f"WARN {label}")
        warnings.append(label)
    else:
        print(f"FAIL {label}")
        failures.append(label)


def markdown_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(p for p in path.rglob("*.md") if p.is_file())


def contains_reference_only_marker(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "reference-only",
        "reference only",
        "not runnable",
        "non-runnable",
        "not an agent",
        "persona",
        "product role",
    ]
    return any(marker in lowered for marker in markers)


def stale_path_candidates(text: str) -> list[str]:
    candidates = sorted(set(re.findall(r"(?:skills|docs|scripts|agents|workers|personas|product-roles|runnable-agents)/[A-Za-z0-9_./-]+", text)))
    stale: list[str] = []
    for candidate in candidates:
        cleaned = candidate.rstrip(".,;:)]")
        if not (ROOT / cleaned).exists():
            stale.append(cleaned)
    return stale


def audit_skill_file(path: Path, failures: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    fm = frontmatter(text)
    rel = path.relative_to(ROOT)
    check(bool(fm), f"SKILL.md frontmatter present: {rel}", failures)
    desc = fm.get("description", "")
    if desc:
        check(len(desc) <= 60, f"SKILL.md description <=60 chars: {rel} ({len(desc)})", failures)
        check(desc.endswith("."), f"SKILL.md description ends with period: {rel}", failures)
    else:
        check(False, f"SKILL.md description present: {rel}", failures)


def audit() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    print("AOS Registry Verification")
    print(f"repo={ROOT}")
    print(f"aos_root={AOS_ROOT}")

    check(AOS_ROOT.exists(), "AOS council root exists", failures, warnings, warn=True)

    for name, path in EXPECTED_PATHS.items():
        check(path.exists(), f"AOS registry path exists: {name} -> {path.relative_to(ROOT)}", failures, warnings, warn=True)

    runnable = EXPECTED_PATHS["runnable_agents"]
    skills_dir = EXPECTED_PATHS["skills"]
    workers = EXPECTED_PATHS["workers"]
    personas = EXPECTED_PATHS["personas"]
    product_roles = EXPECTED_PATHS["product_roles"]

    check(runnable != skills_dir and runnable != workers, "runnable agents path is separate from skills/workers", failures)
    check(personas != runnable and product_roles != runnable, "personas/product roles path is separate from runnable agents", failures)

    for ref_dir in REFERENCE_ONLY_DIRS:
        for file_path in markdown_files(ref_dir):
            text = file_path.read_text(encoding="utf-8")
            rel = file_path.relative_to(ROOT)
            check(contains_reference_only_marker(text), f"reference-only marker: {rel}", failures, warnings, warn=True)

    for skill in sorted(AOS_ROOT.rglob("SKILL.md")) if AOS_ROOT.exists() else []:
        audit_skill_file(skill, failures)

    scan_roots = [path for path in EXPECTED_PATHS.values() if path.exists()]
    stale_paths: list[tuple[Path, str]] = []
    for root in scan_roots:
        for file_path in markdown_files(root):
            text = file_path.read_text(encoding="utf-8")
            for stale in stale_path_candidates(text):
                stale_paths.append((file_path, stale))
            lowered = text.lower()
            for pattern in PLACEHOLDER_PATTERNS:
                check(pattern.lower() not in lowered, f"no placeholder {pattern!r}: {file_path.relative_to(ROOT)}", failures, warnings, warn=True)

    if stale_paths:
        for file_path, stale in stale_paths[:50]:
            print(f"WARN stale path reference: {file_path.relative_to(ROOT)} -> {stale}")
        warnings.append(f"stale path references: {len(stale_paths)}")
    else:
        print("PASS stale path references not detected")

    if runnable.exists():
        runnable_files = markdown_files(runnable)
        check(bool(runnable_files), "runnable agents are distinguishable by directory", failures, warnings, warn=True)
    if workers.exists():
        worker_files = markdown_files(workers)
        check(bool(worker_files), "workers are distinguishable by directory", failures, warnings, warn=True)
    if skills_dir.exists():
        skill_files = markdown_files(skills_dir)
        check(bool(skill_files), "super-specialist skills are distinguishable by directory", failures, warnings, warn=True)

    print(f"SUMMARY failures={len(failures)} warnings={len(warnings)}")
    if failures:
        print("RESULT FAIL")
        return 1
    print("RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(audit())
