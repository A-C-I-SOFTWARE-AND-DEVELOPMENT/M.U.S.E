"""Compile the Essencebound master prompt into atomic auditable requirements."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .ontology import CATEGORIES

_SECTION_RE = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SourceSection:
    number: int
    title: str
    body: str


_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("PERFORMANCE", ("performance", "vram", "frame-time", "frame time", "instance budget")),
    ("INSTANCING", ("instanc", "hism", "spatial cell", "localized bounds")),
    ("CULLING", ("culling", "distance-aware", "distance aware", "hlod")),
    ("BRIDGES", ("bridge", "causeway", "deckseg", "span")),
    ("SKYWAYS", ("skyway", "teleport gate", "fast-travel", "fast travel")),
    ("TRAVERSAL", ("traversal", "reachable", "route", "landing", "dead end", "dead-end")),
    ("PLAYER_SCALE", ("player scale", "walkway", "door width", "railing", "stair rise", "180 cm")),
    ("ESSENCE_INFRASTRUCTURE", ("essence conduit", "floor channel", "power originate", "infrastructure")),
    ("ARCHITECTURAL_PURPOSE", ("building logic", "architectural purpose", "why is it located")),
    ("ARCHITECTURE", ("architecture", "buttress", "tall arch", "foundation", "structure")),
    ("FLOATING_ISLAND_GEOLOGY", ("geology", "undercut", "sediment", "rock dome", "smooth cone")),
    ("LANDMASS", ("landmass", "island radius", "coast", "terrain")),
    ("WILDERNESS", ("wilderness", "landscape clutter", "plants", "ravine")),
    ("ROADS", ("road", "junction", "milestone", "kerb", "service route")),
    ("SETTLEMENTS", ("settlement", "capital", "village", "residence")),
    ("MARKETS", ("market", "stall", "vendor")),
    ("SHOPS", ("shop", "blacksmith", "alchemist", "tavern")),
    ("INTERIORS", ("interior", "enterable", "circulation")),
    ("ENVIRONMENTAL_STORYTELLING", ("environmental storytelling", "evidence of use", "history")),
    ("MATERIALS", ("material", "stone", "bronze", "weathering")),
    ("LIGHTING", ("lighting", "firelight", "amber", "fog")),
    ("CRYSTALS", ("crystal", "mineral vein")),
    ("MAGIC", ("magic", "emissive", "rune", "particle", "levitat")),
    ("COMPOSITION", ("composition", "foreground", "midground", "background", "focal point")),
    ("SILHOUETTE", ("silhouette", "skyline", "strong vertical")),
    ("DESTRUCTION", ("destruct", "breakable", "destroy")),
    ("INTERACTION", ("interact", "usable", "feedback")),
    ("COLLISION", ("collision", "clearance", "navmesh")),
    ("OBJECT_INTERSECTIONS", ("intersection", "intersect", "hovering", "floating building")),
    ("BLENDER", ("blender", "collection structure", "qa camera")),
    ("UNREAL", ("unreal", ".umap", "/game/ess/maps", "world partition")),
    ("PYTHON_GENERATION", ("python", "generator", "procedural")),
    ("REPO_REASONING", ("repository", "repo", "manifest", "actual files", "file existence")),
    ("VERIFICATION", ("verifier", "verification", "evidence", "inspect", "measured run")),
    ("FAILURE_DETECTION", ("failure", "invalid", "wrong", "defect", "negative")),
    ("QUALITY_GATES", ("quality gate", "gate metrics", "aaa screenshot", "polish gate")),
    ("COMPLETION_STATUS", ("completion", "complete", "unverified", "claim success")),
    ("TASK_PRIORITIZATION", ("priority", "what should", "next step", "stage ordering")),
    ("CONCEPT_FIDELITY", ("concept", "visual language", "generic fantasy", "essencebound")),
    ("MACRO_LAYOUT", ("macro", "topology", "world layout", "axiom core", "hero location")),
)

_PREFIX = {
    category: "".join(part[0] for part in category.split("_"))[:6]
    for category in CATEGORIES
}
_PREFIX.update(
    {
        "TRAVERSAL": "TRAV",
        "BRIDGES": "BRDG",
        "ARCHITECTURE": "ARCH",
        "PERFORMANCE": "PERF",
        "REPO_REASONING": "REPO",
        "VERIFICATION": "VERIFY",
        "CONCEPT_FIDELITY": "CONCEPT",
    }
)


def parse_sections(text: str) -> list[SourceSection]:
    """Parse numbered top-level sections without treating subheadings as peers."""
    sections: list[SourceSection] = []
    current_number: int | None = None
    current_title = ""
    body: list[str] = []
    for line in text.splitlines():
        match = _SECTION_RE.match(line)
        if match:
            if current_number is not None:
                sections.append(SourceSection(current_number, current_title, "\n".join(body)))
            current_number = int(match.group(1))
            current_title = match.group(2).strip()
            body = []
        elif current_number is not None:
            body.append(line)
    if current_number is not None:
        sections.append(SourceSection(current_number, current_title, "\n".join(body)))
    return sections


def _clean_directive(line: str) -> str:
    value = _LIST_RE.sub("", line.strip())
    value = value.strip("` ")
    value = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", value)
    return _SPACE_RE.sub(" ", value).strip()


def _atomic_directives(section: SourceSection) -> list[str]:
    directives: list[str] = []
    seen: set[str] = set()
    in_fence = False
    for raw in section.body.splitlines():
        if raw.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not raw.strip() or raw.lstrip().startswith(("#", "|", "---")):
            continue
        value = _clean_directive(raw)
        if len(value) < 12 or value.endswith(":"):
            continue
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        directives.append(value)
    if not directives:
        directives.append(f"Apply the {section.title.lower()} specification.")
    return directives


def _category(section: SourceSection, directive: str) -> str:
    text = f"{section.title} {directive}".casefold()
    for category, hints in _CATEGORY_RULES:
        if any(hint in text for hint in hints):
            return category
    return "VERIFICATION" if section.number >= 30 else "CONCEPT_FIDELITY"


def _testability(category: str, text: str) -> tuple[str, list[str]]:
    value = text.casefold()
    if category in {"PERFORMANCE", "INSTANCING", "CULLING"} or any(
        term in value for term in ("measure", "vram", "frame-time", "instance count")
    ):
        return "measurement", ["performance_measurement"]
    if category == "REPO_REASONING" or any(
        term in value for term in ("repository", "repo", "manifest", "actual file")
    ):
        return "repository", ["repository_state"]
    if category in {"BLENDER", "UNREAL", "COLLISION", "OBJECT_INTERSECTIONS"}:
        return "scene", ["scene_state", "validator_output"]
    if category == "CONCEPT_FIDELITY":
        return "visual", ["concept_sheet", "player_eye_render"]
    return "deterministic", ["supplied_scenario"]


def _severity(text: str) -> str:
    value = text.casefold()
    blocking = ("must", "never", "critical", "fail", "do not", "no ", "≤", "unreachable")
    return "blocking" if any(term in value for term in blocking) else "important"


def _rule_kind(section_number: int, directive: str) -> str:
    if section_number >= 30:
        return "FOUNDRY_RULE"
    if section_number in {26, 27} or "current project" in directive.casefold():
        return "PROJECT_STATE"
    return "DESIGN_RULE"


def compile_requirements(text: str) -> list[dict]:
    """Atomize all numbered sections into stable, evidence-aware records."""
    rows: list[dict] = []
    category_counts: dict[str, int] = {}
    for section in parse_sections(text):
        for directive in _atomic_directives(section):
            category = _category(section, directive)
            category_counts[category] = category_counts.get(category, 0) + 1
            requirement_id = f"EB-{_PREFIX[category]}-{category_counts[category]:03d}"
            testability, evidence = _testability(category, f"{section.title} {directive}")
            severity = _severity(directive)
            rows.append(
                {
                    "requirement_id": requirement_id,
                    "source_section": section.title,
                    "source_section_number": section.number,
                    "requirement": directive,
                    "category": category,
                    "severity": severity,
                    "testability": testability,
                    "required_evidence": evidence,
                    "rule_kind": _rule_kind(section.number, directive),
                    "source_excerpt_hash": hashlib.sha256(directive.encode("utf-8")).hexdigest(),
                    "positive_examples": 1,
                    "negative_examples": 1,
                    "adversarial_examples": 1 if severity == "blocking" else 0,
                }
            )
    return rows
