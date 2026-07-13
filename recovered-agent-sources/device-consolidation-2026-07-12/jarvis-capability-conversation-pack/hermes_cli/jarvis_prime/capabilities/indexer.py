"""Build a :class:`CapabilityGraph` from the repository.

The indexer is the only module that touches the filesystem. It reads:

- ``skills/aos-enterprise-council/operating-registry/registry.json`` for
  the verified council, specialists, super-skills, and workers.
- ``skills/aos-enterprise-council/personas/`` and ``product-roles/`` for
  persona/product-role overlays (tone and viewpoint, not workers).
- ``skills/aos-enterprise-council/archive/`` for historical references
  that must never be routed to live.
- ``skills/*/SKILL.md`` for top-level Hermes skills (tags +
  activation_phrases live in the metadata block).

The indexer never raises on missing files: a partial graph is better
than a crashed runtime. Callers can inspect ``len(graph)`` and
``graph.skills`` if they want to assert completeness.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from hermes_cli.jarvis_prime.capabilities.graph import CapabilityGraph
from hermes_cli.jarvis_prime.capabilities.schemas import (
    Capability,
    CapabilityType,
)

# Where the AOS Enterprise Council skill lives relative to the project root.
_COUNCIL_SKILL_REL = Path("skills") / "aos-enterprise-council"


class CapabilityIndexer:
    """Walk the repo and emit a :class:`CapabilityGraph`."""

    def __init__(self, project_root: Path) -> None:
        self._root = Path(project_root)

    # ------------------------------------------------------------------

    def build(self) -> CapabilityGraph:
        graph = CapabilityGraph()
        self._index_registry(graph)
        self._index_personas(graph)
        self._index_product_roles(graph)
        self._index_archive(graph)
        self._index_top_level_skills(graph)
        return graph

    # -- registry -------------------------------------------------------

    def _index_registry(self, graph: CapabilityGraph) -> None:
        path = self._root / _COUNCIL_SKILL_REL / "operating-registry" / "registry.json"
        data = _safe_load_json(path)
        if not data:
            return
        for agent in data.get("active_council", []):
            graph.add(
                Capability(
                    id=agent["id"],
                    type=CapabilityType.RUNNABLE_AGENT,
                    description=agent.get("role", ""),
                    tags=("council", "decision"),
                    path=agent.get("path"),
                    metadata={"slack_default": agent.get("slack_default", False)},
                )
            )
        for spec in data.get("domain_specialists", []):
            graph.add(
                Capability(
                    id=spec["id"],
                    type=CapabilityType.DOMAIN_SPECIALIST,
                    description=spec.get("when_to_use", ""),
                    domain=spec.get("domain"),
                    tags=_specialist_tags(spec),
                    owner_gate_required=bool(spec.get("owner_gate")),
                    metadata={
                        "when_to_use": spec.get("when_to_use"),
                        "when_not_to_use": spec.get("when_not_to_use"),
                        "required_inputs": spec.get("required_inputs", []),
                        "required_output": spec.get("required_output"),
                        "verification_method": spec.get("verification_method"),
                    },
                )
            )
        for skill in data.get("super_specialist_skills", []):
            graph.add(
                Capability(
                    id=skill["id"],
                    type=CapabilityType.SKILL,
                    description=skill.get("description", ""),
                    tags=_skill_tags_from_id(skill["id"]),
                    path=skill.get("path"),
                )
            )
        for worker in data.get("worker_templates", []):
            graph.add(
                Capability(
                    id=worker["id"],
                    type=CapabilityType.WORKER,
                    description=worker.get("purpose", ""),
                    tags=_worker_tags(worker["id"]),
                    path=worker.get("path"),
                )
            )

    # -- personas / product roles / archive ----------------------------

    def _index_personas(self, graph: CapabilityGraph) -> None:
        directory = self._root / _COUNCIL_SKILL_REL / "personas"
        if not directory.exists():
            return
        for md in directory.glob("*.md"):
            if md.name.lower() in {"readme.md"}:
                continue
            graph.add(
                Capability(
                    id=f"persona:{md.stem}",
                    type=CapabilityType.PERSONA,
                    description=_first_paragraph(md),
                    tags=("persona", "tone"),
                    path=str(md.relative_to(self._root)),
                )
            )

    def _index_product_roles(self, graph: CapabilityGraph) -> None:
        directory = self._root / _COUNCIL_SKILL_REL / "product-roles"
        if not directory.exists():
            return
        for md in directory.glob("*.md"):
            if md.name.lower() in {"readme.md"}:
                continue
            graph.add(
                Capability(
                    id=f"role:{md.stem}",
                    type=CapabilityType.PRODUCT_ROLE,
                    description=_first_paragraph(md),
                    tags=("product-role", "viewpoint"),
                    path=str(md.relative_to(self._root)),
                )
            )

    def _index_archive(self, graph: CapabilityGraph) -> None:
        directory = self._root / _COUNCIL_SKILL_REL / "archive"
        if not directory.exists():
            return
        for md in directory.rglob("*.md"):
            if md.name.lower() == "readme.md":
                continue
            graph.add(
                Capability(
                    id=f"archive:{md.stem}",
                    type=CapabilityType.ARCHIVE,
                    description=_first_paragraph(md),
                    tags=("archive", "historical"),
                    path=str(md.relative_to(self._root)),
                )
            )

    # -- top-level skills ----------------------------------------------

    def _index_top_level_skills(self, graph: CapabilityGraph) -> None:
        skills_dir = self._root / "skills"
        if not skills_dir.exists():
            return
        for skill_md in skills_dir.glob("*/SKILL.md"):
            cap = _capability_from_skill_md(skill_md, self._root)
            if cap is not None:
                graph.add(cap)


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------


def _safe_load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _first_paragraph(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for block in text.split("\n\n"):
        cleaned = block.strip()
        if cleaned and not cleaned.startswith("#") and not cleaned.startswith("---"):
            return cleaned.splitlines()[0][:200]
    return ""


# Skill metadata is YAML-ish but we deliberately don't pull in PyYAML for the
# selector. The simple parser below reads the frontmatter as a flat
# key/value/list form, which matches the SKILL.md files in this repo.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _capability_from_skill_md(skill_md: Path, project_root: Path) -> Optional[Capability]:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    frontmatter = _parse_simple_frontmatter(match.group(1))
    name = frontmatter.get("name") or skill_md.parent.name
    description = frontmatter.get("description") or ""
    tags = tuple(frontmatter.get("__tags__", []))
    activation_phrases = tuple(frontmatter.get("__activation_phrases__", []))
    return Capability(
        id=name,
        type=CapabilityType.SKILL,
        description=description.strip().strip('"'),
        tags=tags or _skill_tags_from_id(name),
        activation_phrases=activation_phrases,
        path=str(skill_md.relative_to(project_root)),
    )


def _parse_simple_frontmatter(block: str) -> dict:
    """Tolerant frontmatter parser for the SKILL.md style used in this repo.

    Returns a dict with top-level scalar keys plus two synthetic keys:
    ``__tags__`` and ``__activation_phrases__`` aggregated from the
    ``metadata.hermes.tags`` and ``metadata.hermes.activation_phrases``
    blocks. We only need these two lists for routing; anything else is
    available via the description and the path on disk.
    """
    out: dict[str, object] = {}
    tags: list[str] = []
    activation_phrases: list[str] = []

    current_list_key: Optional[str] = None

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current_list_key = None
            continue
        stripped = line.lstrip()
        # list item
        if stripped.startswith("- "):
            value = stripped[2:].strip().strip('"')
            if current_list_key == "tags":
                tags.append(value)
            elif current_list_key == "activation_phrases":
                activation_phrases.append(value)
            continue
        # key block
        if stripped.endswith(":"):
            key = stripped[:-1].strip()
            if key in {"tags", "activation_phrases"}:
                current_list_key = key
            else:
                current_list_key = None
            continue
        # scalar key: value
        if ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"')
            if value:
                out[key] = value
            current_list_key = None

    out["__tags__"] = tags
    out["__activation_phrases__"] = activation_phrases
    return out


def _specialist_tags(spec: dict) -> tuple[str, ...]:
    tags = ["specialist"]
    domain = spec.get("domain")
    if domain:
        tags.extend(re.split(r"[\s/]+", domain.lower()))
    for word in re.split(r"\W+", spec.get("when_to_use", "").lower()):
        if word and len(word) > 3:
            tags.append(word)
    return tuple(sorted(set(tags)))


def _worker_tags(worker_id: str) -> tuple[str, ...]:
    base = [w for w in worker_id.split("-") if w]
    base.append("worker")
    return tuple(sorted(set(base)))


def _skill_tags_from_id(skill_id: str) -> tuple[str, ...]:
    base = [w for w in skill_id.split("-") if w]
    base.append("skill")
    return tuple(sorted(set(base)))


__all__ = ["CapabilityIndexer"]
