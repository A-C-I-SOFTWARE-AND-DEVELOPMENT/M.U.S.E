"""Skill metadata caching and indexing for fast discovery.

Provides a TTL-based cache for skill metadata to avoid repeated disk scans
and YAML parsing. The cache is invalidated when skills directories change.

Usage:
    from tools.skill_cache import get_cached_skills, search_skills, invalidate_cache

    # Get all skills (cached, TTL 5 min)
    skills = get_cached_skills()

    # Search by query (name, description, tags)
    results = search_skills("llm fine-tuning")

    # Force refresh
    invalidate_cache()
"""

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300  # 5 minutes
INDEX_FILE = ".skills-index.json"

_cache_lock = threading.RLock()
_cache: Optional["SkillCache"] = None


@dataclass
class SkillEntry:
    """Cached skill metadata."""
    name: str
    description: str
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)
    path: Optional[str] = None
    has_references: bool = False
    has_templates: bool = False
    has_scripts: bool = False
    has_assets: bool = False
    platforms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "related_skills": self.related_skills,
            "path": self.path,
            "has_references": self.has_references,
            "has_templates": self.has_templates,
            "has_scripts": self.has_scripts,
            "has_assets": self.has_assets,
            "platforms": self.platforms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillEntry":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category"),
            tags=data.get("tags", []),
            related_skills=data.get("related_skills", []),
            path=data.get("path"),
            has_references=data.get("has_references", False),
            has_templates=data.get("has_templates", False),
            has_scripts=data.get("has_scripts", False),
            has_assets=data.get("has_assets", False),
            platforms=data.get("platforms", []),
        )


class SkillCache:
    """In-memory skill metadata cache with disk persistence."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self.skills: Dict[str, SkillEntry] = {}
        self.by_category: Dict[str, List[str]] = {}
        self.by_tag: Dict[str, Set[str]] = {}
        self.inverted_index: Dict[str, Set[str]] = {}  # term -> skill names
        self.last_refresh: float = 0
        self.dir_hash: str = ""

    def _compute_dir_hash(self) -> str:
        """Compute a hash of skills directory state for invalidation."""
        from agent.skill_utils import get_all_skills_dirs

        hasher = hashlib.md5()
        for skills_dir in get_all_skills_dirs():
            if not skills_dir.exists():
                continue
            try:
                stat = skills_dir.stat()
                hasher.update(f"{skills_dir}:{stat.st_mtime_ns}".encode())
                for skill_md in skills_dir.rglob("SKILL.md"):
                    try:
                        md_stat = skill_md.stat()
                        hasher.update(f"{skill_md}:{md_stat.st_mtime_ns}".encode())
                    except OSError:
                        continue
            except OSError:
                continue
        return hasher.hexdigest()

    def is_valid(self) -> bool:
        """Check if cache is still valid (within TTL and no dir changes)."""
        if not self.skills:
            return False
        if time.time() - self.last_refresh > self.ttl_seconds:
            return False
        current_hash = self._compute_dir_hash()
        if current_hash != self.dir_hash:
            return False
        return True

    def refresh(self) -> None:
        """Rebuild cache from disk."""
        from agent.skill_utils import (
            get_all_skills_dirs,
            get_disabled_skill_names,
            iter_skill_index_files,
            parse_frontmatter,
            skill_matches_platform,
            EXCLUDED_SKILL_DIRS,
        )

        self.skills.clear()
        self.by_category.clear()
        self.by_tag.clear()
        self.inverted_index.clear()

        disabled = get_disabled_skill_names()

        for skills_dir in get_all_skills_dirs():
            if not skills_dir.exists():
                continue

            for skill_md in iter_skill_index_files(skills_dir, "SKILL.md"):
                if any(part in EXCLUDED_SKILL_DIRS for part in skill_md.parts):
                    continue

                skill_dir = skill_md.parent

                try:
                    content = skill_md.read_text(encoding="utf-8")[:4000]
                    frontmatter, body = parse_frontmatter(content)

                    if not skill_matches_platform(frontmatter):
                        continue

                    name = frontmatter.get("name", skill_dir.name)[:64]
                    if name in self.skills or name in disabled:
                        continue

                    description = frontmatter.get("description", "")
                    if not description:
                        for line in body.strip().split("\n"):
                            line = line.strip()
                            if line and not line.startswith("#"):
                                description = line[:1024]
                                break

                    try:
                        rel_path = str(skill_md.relative_to(skills_dir))
                    except ValueError:
                        rel_path = str(skill_md)

                    category = None
                    parts = Path(rel_path).parts
                    if len(parts) >= 3:
                        category = parts[0]

                    metadata = frontmatter.get("metadata", {})
                    hermes_meta = metadata.get("hermes", {}) if isinstance(metadata, dict) else {}

                    tags = _parse_list(hermes_meta.get("tags") or frontmatter.get("tags", []))
                    related = _parse_list(hermes_meta.get("related_skills") or frontmatter.get("related_skills", []))
                    platforms = _parse_list(frontmatter.get("platforms", []))

                    entry = SkillEntry(
                        name=name,
                        description=description[:1024],
                        category=category,
                        tags=tags,
                        related_skills=related,
                        path=rel_path,
                        has_references=(skill_dir / "references").is_dir(),
                        has_templates=(skill_dir / "templates").is_dir(),
                        has_scripts=(skill_dir / "scripts").is_dir(),
                        has_assets=(skill_dir / "assets").is_dir(),
                        platforms=platforms,
                    )

                    self.skills[name] = entry

                    if category:
                        self.by_category.setdefault(category, []).append(name)

                    for tag in tags:
                        self.by_tag.setdefault(tag.lower(), set()).add(name)

                    self._index_skill(entry)

                except Exception as e:
                    logger.debug("Failed to cache skill %s: %s", skill_md, e)
                    continue

        self.last_refresh = time.time()
        self.dir_hash = self._compute_dir_hash()

        self._persist_to_disk()

    def _index_skill(self, entry: SkillEntry) -> None:
        """Build inverted index for full-text search."""
        terms = set()

        for word in _tokenize(entry.name):
            terms.add(word)

        for word in _tokenize(entry.description):
            terms.add(word)

        for tag in entry.tags:
            for word in _tokenize(tag):
                terms.add(word)

        if entry.category:
            for word in _tokenize(entry.category):
                terms.add(word)

        for term in terms:
            self.inverted_index.setdefault(term, set()).add(entry.name)

    def _persist_to_disk(self) -> None:
        """Save cache to disk for faster cold starts."""
        try:
            index_path = get_hermes_home() / "skills" / INDEX_FILE
            data = {
                "version": 1,
                "last_refresh": self.last_refresh,
                "dir_hash": self.dir_hash,
                "skills": {name: e.to_dict() for name, e in self.skills.items()},
            }
            index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to persist skill cache: %s", e)

    def _load_from_disk(self) -> bool:
        """Try to load cache from disk. Returns True if valid cache found."""
        try:
            index_path = get_hermes_home() / "skills" / INDEX_FILE
            if not index_path.exists():
                return False

            data = json.loads(index_path.read_text(encoding="utf-8"))
            if data.get("version") != 1:
                return False

            current_hash = self._compute_dir_hash()
            if data.get("dir_hash") != current_hash:
                return False

            age = time.time() - data.get("last_refresh", 0)
            if age > self.ttl_seconds:
                return False

            for name, skill_data in data.get("skills", {}).items():
                entry = SkillEntry.from_dict(skill_data)
                self.skills[name] = entry

                if entry.category:
                    self.by_category.setdefault(entry.category, []).append(name)

                for tag in entry.tags:
                    self.by_tag.setdefault(tag.lower(), set()).add(name)

                self._index_skill(entry)

            self.last_refresh = data.get("last_refresh", 0)
            self.dir_hash = data.get("dir_hash", "")
            return True

        except Exception as e:
            logger.debug("Failed to load skill cache from disk: %s", e)
            return False

    def search(self, query: str, limit: int = 20) -> List[Tuple[str, float]]:
        """Search skills by query. Returns (name, score) tuples sorted by relevance."""
        if not query.strip():
            return [(name, 1.0) for name in sorted(self.skills.keys())[:limit]]

        query_terms = _tokenize(query)
        if not query_terms:
            return []

        scores: Dict[str, float] = {}

        for term in query_terms:
            if term in self.inverted_index:
                for name in self.inverted_index[term]:
                    scores[name] = scores.get(name, 0) + 1.0

            for indexed_term, names in self.inverted_index.items():
                if indexed_term.startswith(term) or term.startswith(indexed_term):
                    for name in names:
                        scores[name] = scores.get(name, 0) + 0.5

        for name, entry in self.skills.items():
            query_lower = query.lower()
            if query_lower in entry.name.lower():
                scores[name] = scores.get(name, 0) + 3.0
            if query_lower in entry.description.lower():
                scores[name] = scores.get(name, 0) + 1.5
            for tag in entry.tags:
                if query_lower == tag.lower():
                    scores[name] = scores.get(name, 0) + 2.0

        sorted_results = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return sorted_results[:limit]

    def get_by_tag(self, tag: str) -> List[str]:
        """Get all skill names with a specific tag."""
        return list(self.by_tag.get(tag.lower(), set()))

    def get_by_category(self, category: str) -> List[str]:
        """Get all skill names in a category."""
        return self.by_category.get(category, [])

    def get_recommendations(self, name: str, limit: int = 5) -> List[str]:
        """Get recommended skills similar to the given skill."""
        if name not in self.skills:
            return []

        entry = self.skills[name]
        scores: Dict[str, float] = {}

        for related in entry.related_skills:
            if related in self.skills and related != name:
                scores[related] = scores.get(related, 0) + 5.0

        for tag in entry.tags:
            for other_name in self.by_tag.get(tag.lower(), set()):
                if other_name != name:
                    scores[other_name] = scores.get(other_name, 0) + 1.0

        if entry.category:
            for other_name in self.by_category.get(entry.category, []):
                if other_name != name:
                    scores[other_name] = scores.get(other_name, 0) + 0.5

        sorted_results = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return [name for name, _ in sorted_results[:limit]]


def _parse_list(value: Any) -> List[str]:
    """Parse a list from various input formats."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        return [v.strip().strip("\"'") for v in value.split(",") if v.strip()]
    return []


def _tokenize(text: str) -> List[str]:
    """Tokenize text into searchable terms."""
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = text.split()
    return [w for w in words if len(w) >= 2]


def get_cache() -> SkillCache:
    """Get the global skill cache instance, refreshing if needed."""
    global _cache

    with _cache_lock:
        if _cache is None:
            _cache = SkillCache()
            if not _cache._load_from_disk():
                _cache.refresh()
        elif not _cache.is_valid():
            _cache.refresh()

        return _cache


def get_cached_skills(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> List[Dict[str, Any]]:
    """Get all cached skills as a list of dicts."""
    cache = get_cache()
    if cache.ttl_seconds != ttl_seconds:
        cache.ttl_seconds = ttl_seconds

    return [entry.to_dict() for entry in cache.skills.values()]


def search_skills(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search skills by query. Returns list of skill dicts with scores."""
    cache = get_cache()
    results = cache.search(query, limit=limit)

    return [
        {**cache.skills[name].to_dict(), "score": score}
        for name, score in results
        if name in cache.skills
    ]


def get_skill_recommendations(name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get skills similar to the given skill."""
    cache = get_cache()
    recommendations = cache.get_recommendations(name, limit=limit)

    return [
        cache.skills[rec_name].to_dict()
        for rec_name in recommendations
        if rec_name in cache.skills
    ]


def get_skills_by_tag(tag: str) -> List[Dict[str, Any]]:
    """Get all skills with a specific tag."""
    cache = get_cache()
    names = cache.get_by_tag(tag)

    return [cache.skills[name].to_dict() for name in names if name in cache.skills]


def get_skills_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all skills in a category."""
    cache = get_cache()
    names = cache.get_by_category(category)

    return [cache.skills[name].to_dict() for name in names if name in cache.skills]


def get_all_tags() -> List[Tuple[str, int]]:
    """Get all tags with their usage counts."""
    cache = get_cache()
    return sorted(
        [(tag, len(names)) for tag, names in cache.by_tag.items()],
        key=lambda x: (-x[1], x[0])
    )


def get_all_categories() -> List[Tuple[str, int]]:
    """Get all categories with their skill counts."""
    cache = get_cache()
    return sorted(
        [(cat, len(names)) for cat, names in cache.by_category.items()],
        key=lambda x: (-x[1], x[0])
    )


def invalidate_cache() -> None:
    """Force cache invalidation."""
    global _cache
    with _cache_lock:
        _cache = None

    try:
        index_path = get_hermes_home() / "skills" / INDEX_FILE
        if index_path.exists():
            index_path.unlink()
    except Exception:
        pass
