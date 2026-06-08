#!/usr/bin/env python3
"""Audit the MUSE operating-layer files.

This script is intentionally local-only and stdlib-only so it can run safely in
Termux and CI-like shells without network access or credentials.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STAGE_1_DOCS = [
    Path("docs/jarvis-prime-operating-system.md"),
    Path("docs/jarvis-code-operator-workflow.md"),
    Path("docs/mobile-voice-development-workflow.md"),
    Path("docs/slack-mobile-command-policy.md"),
]

STAGE_2_SKILLS = [
    Path("skills/jarvis-prime/SKILL.md"),
    Path("skills/jarvis-code-operator/SKILL.md"),
    Path("skills/mobile-voice-development/SKILL.md"),
]

DOC_REQUIRED_TERMS = [
    "MUSE",
    "AOS Council",
    "Claude Code",
    "Codex",
    "Termux",
    "Slack",
    "JARVIS capture",
]

SKILL_REQUIRED_SECTIONS = [
    "# ",
    "## When to Use",
    "## Prerequisites",
    "## How to Run",
    "## Quick Reference",
    "## Procedure",
    "## Pitfalls",
    "## Verification",
]

PLACEHOLDER_PATTERNS = [
    "TODO",
    "TBD",
    "FIXME",
    "lorem ipsum",
    "placeholder",
    "<insert",
    "<todo",
]


def read_text(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


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


def strip_fenced_blocks(text: str) -> str:
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "\n".join(lines)


def check(condition: bool, label: str, failures: list[str], warnings: list[str] | None = None, warn: bool = False) -> None:
    if condition:
        print(f"PASS {label}")
    elif warn and warnings is not None:
        print(f"WARN {label}")
        warnings.append(label)
    else:
        print(f"FAIL {label}")
        failures.append(label)


def audit() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    print("JARVIS Context Audit")
    print(f"repo={ROOT}")

    combined_docs = ""
    for doc in STAGE_1_DOCS:
        exists = (ROOT / doc).is_file()
        check(exists, f"Stage 1 doc exists: {doc}", failures)
        if exists:
            combined_docs += "\n" + read_text(doc)

    for term in DOC_REQUIRED_TERMS:
        check(term in combined_docs, f"Stage 1 docs mention: {term}", failures)

    for skill in STAGE_2_SKILLS:
        path = ROOT / skill
        exists = path.is_file()
        check(exists, f"Stage 2 skill exists: {skill}", failures)
        if not exists:
            continue
        text = read_text(skill)
        fm = frontmatter(text)
        desc = fm.get("description", "")
        check(bool(fm), f"frontmatter present: {skill}", failures)
        check(bool(desc), f"description present: {skill}", failures)
        check(len(desc) <= 60, f"description <=60 chars: {skill} ({len(desc)})", failures)
        check(desc.endswith("."), f"description ends with period: {skill}", failures)
        check(desc.count(".") == 1, f"description is one sentence: {skill}", failures)
        scan = strip_fenced_blocks(text)
        positions: list[int] = []
        for section in SKILL_REQUIRED_SECTIONS:
            match = re.search(r"^" + re.escape(section), scan, re.MULTILINE)
            check(bool(match), f"required section {section!r}: {skill}", failures)
            if match:
                positions.append(match.start())
        check(positions == sorted(positions), f"modern section order: {skill}", failures)

    for file_path in [*STAGE_1_DOCS, *STAGE_2_SKILLS]:
        path = ROOT / file_path
        if not path.exists():
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for pattern in PLACEHOLDER_PATTERNS:
            check(pattern.lower() not in lowered, f"no placeholder {pattern!r}: {file_path}", failures)

    readme = ROOT / "README.md"
    agents = ROOT / "AGENTS.md"
    if readme.exists():
        readme_text = readme.read_text(encoding="utf-8")
        check("MUSE" in readme_text, "README.md JARVIS integration detected", failures, warnings, warn=True)
    else:
        check(False, "README.md exists", failures, warnings, warn=True)
    if agents.exists():
        agents_text = agents.read_text(encoding="utf-8")
        check("MUSE Operating Layer" in agents_text, "AGENTS.md JARVIS integration detected", failures, warnings, warn=True)
    else:
        check(False, "AGENTS.md exists", failures, warnings, warn=True)

    print(f"SUMMARY failures={len(failures)} warnings={len(warnings)}")
    if failures:
        print("RESULT FAIL")
        return 1
    print("RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(audit())
