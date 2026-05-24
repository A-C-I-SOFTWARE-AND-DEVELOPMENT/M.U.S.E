#!/usr/bin/env python3
"""Verify the AOS operating registry against Hermes standards."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "operating-registry" / "registry.json"
REQUIRED_SPECIALIST_FIELDS = {
    "id",
    "domain",
    "when_to_use",
    "when_not_to_use",
    "required_inputs",
    "required_output",
    "verification_method",
    "owner_gate",
}
OWNER_GATE_VALUE = "Yes, with authorization."


def fail(errors: list[str]) -> None:
    if errors:
        print("AOS registry verification failed:")
        for err in errors:
            print(f"- {err}")
        sys.exit(1)
    print("AOS registry verification passed.")


def frontmatter_description(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    for line in parts[1].splitlines():
        if line.strip().startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def one_sentence(desc: str) -> bool:
    return desc.endswith(".") and len(re.findall(r"[.!?]", desc)) == 1


def main() -> None:
    errors: list[str] = []
    data = json.loads(REGISTRY.read_text())

    active = data.get("active_council", [])
    if len(active) > 6:
        errors.append(f"active_council has {len(active)} entries; max is 6")
    policies = data.get("policies", {})
    if not policies.get("no_more_always_active_agents"):
        errors.append("no_more_always_active_agents policy must be true")
    if policies.get("owner_gate_phrase") != OWNER_GATE_VALUE:
        errors.append("owner_gate_phrase must be 'Yes, with authorization.'")

    ids: set[str] = set()
    for section in ("active_council", "domain_specialists", "super_specialist_skills", "worker_templates"):
        for item in data.get(section, []):
            item_id = item.get("id")
            if not item_id:
                errors.append(f"{section} item missing id")
                continue
            if item_id in ids:
                errors.append(f"duplicate id: {item_id}")
            ids.add(item_id)

    for specialist in data.get("domain_specialists", []):
        name = specialist.get("id", "<unknown>")
        missing = REQUIRED_SPECIALIST_FIELDS - specialist.keys()
        if missing:
            errors.append(f"specialist {name} missing {sorted(missing)}")
        if not specialist.get("required_inputs"):
            errors.append(f"specialist {name} has no required_inputs")
        if specialist.get("owner_gate") != OWNER_GATE_VALUE:
            errors.append(f"specialist {name} owner_gate must be {OWNER_GATE_VALUE!r}")

    for skill in data.get("super_specialist_skills", []):
        desc = skill.get("description", "")
        if len(desc) > 60:
            errors.append(f"skill {skill.get('id')} description is {len(desc)} chars")
        if not one_sentence(desc):
            errors.append(f"skill {skill.get('id')} description must be one sentence ending with a period")

    for worker in data.get("worker_templates", []):
        purpose = worker.get("purpose", "").lower()
        if "not " not in purpose:
            errors.append(f"worker {worker.get('id')} must state it is not a decision agent/authority")

    for skill_md in ROOT.rglob("SKILL.md"):
        desc = frontmatter_description(skill_md.read_text())
        if desc is None:
            errors.append(f"{skill_md.relative_to(ROOT)} missing frontmatter description")
            continue
        if len(desc) > 60:
            errors.append(f"{skill_md.relative_to(ROOT)} description is {len(desc)} chars")
        if not one_sentence(desc):
            errors.append(f"{skill_md.relative_to(ROOT)} description must be one sentence ending with a period")

    folders = data.get("separated_collections", {})
    for key, rel in folders.items():
        if not (ROOT / rel).exists():
            errors.append(f"separated collection {key} path missing: {rel}")

    historical = data.get("source_of_truth", {})
    for key in ("historical_registry", "historical_subagents", "historical_prompts", "historical_workflows", "historical_memory_context"):
        rel = historical.get(key)
        if not rel or not (ROOT / rel).exists():
            errors.append(f"historical reference missing: {key} -> {rel}")

    fail(errors)


if __name__ == "__main__":
    main()
