"""Unified Agent Pool — autonomous routing without slash commands.

This module builds a single flat pool from every agent-capable definition
in the repo and provides an intent classifier that auto-activates the
right agents based on the user's message — no ``/`` commands required.

**Design goals:**

1. **One pool** — all 670+ agent definitions (AOS council, skills,
   .claude agents, swarm grains, AXIOM kernel modules) indexed into a
   single flat registry with uniform metadata.
2. **Autonomous activation** — the :func:`route` function takes raw user
   text and returns the best-matching agents.  The system prompt injects
   the pool summary so the model *knows* what it can do and *does* it
   directly instead of asking the user to type ``/something``.
3. **Zero new deps** — stdlib only, same invariant as the rest of
   ``jarvis_prime``.

The pool is built once at session start (or on first call) and cached.
It is deliberately lossy: a 670-entry keyword index, not the full text
of every agent file.  The model loads the full SKILL.md / agent .md
on demand via ``skill_view`` or the swarm specialist builder.

Usage from the runtime::

    from hermes_cli.jarvis_prime.agent_pool import get_pool, route

    pool = get_pool()                     # builds + caches
    matches = route("audit this repo's security")  # → top agents
    prompt = pool.system_prompt_excerpt()  # inject into system prompt
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ─── Pool entry ────────────────────────────────────────────────────────

# Source categories — uniform across the entire repo
CAT_AOS_COUNCIL = "aos_council"
CAT_AOS_SPECIALIST = "aos_specialist"
CAT_AOS_WORKER = "aos_worker"
CAT_AOS_RUNNABLE = "aos_runnable"
CAT_AOS_TEMPLATE = "aos_template"
CAT_SKILL = "skill"
CAT_CLAUDE_AGENT = "claude_agent"
CAT_DOTCLAUDE_AGENT = "dotclaude_agent"
CAT_RUNTIME_MODULE = "runtime_module"
CAT_SWARM = "swarm"
CAT_AXIOM = "axiom"

# Domain tags mapped from directory structure
DOMAIN_MAP = {
    "architecture": ["architect", "system design", "infrastructure", "scalability"],
    "business": ["business", "commercial", "revenue", "pricing", "market"],
    "compliance": ["compliance", "regulatory", "gdpr", "hipaa", "pci", "legal"],
    "executive": ["executive", "strategy", "decision", "governance", "ceo"],
    "hazmat-command": ["hazmat", "emergency", "incident", "crisis"],
    "hermes": ["skill", "tool", "integration", "automation"],
    "memory": ["memory", "recall", "knowledge", "context"],
    "nourish": ["nourish", "food", "health", "nutrition"],
    "product": ["product", "roadmap", "feature", "user story"],
    "psychology": ["psychology", "behavior", "ux psychology", "persuasion"],
    "qa": ["qa", "test", "quality", "bug", "regression"],
    "release": ["release", "deploy", "ci/cd", "publish", "ship"],
    "research": ["research", "analysis", "evidence", "citation"],
    "security": ["security", "vulnerability", "audit", "pentest", "crypto"],
    "ux": ["ux", "ui", "design", "accessibility", "interface"],
    "claude-code": ["claude code", "implementation", "coding", "build"],
    "codex": ["codex", "review", "fix", "patch"],
}


@dataclass(frozen=True)
class AgentEntry:
    """One entry in the unified pool."""

    pool_id: str           # e.g. "aos_council:security/security-auditor"
    name: str              # human-readable name
    category: str          # one of CAT_* constants
    domain: str            # e.g. "security", "qa", "hermes"
    path: str              # repo-relative path to the definition file
    description: str       # <=200 char summary
    keywords: tuple[str, ...] = ()  # extracted trigger keywords
    source_line: str = ""  # provenance line

    @property
    def weight(self) -> float:
        """Routing weight — specialists rank higher than general skills."""
        base = {
            CAT_AOS_SPECIALIST: 1.5,
            CAT_AOS_RUNNABLE: 1.4,
            CAT_AOS_WORKER: 1.3,
            CAT_CLAUDE_AGENT: 1.3,
            CAT_DOTCLAUDE_AGENT: 1.3,
            CAT_AOS_COUNCIL: 1.2,
            CAT_SWARM: 1.2,
            CAT_AXIOM: 1.1,
            CAT_AOS_TEMPLATE: 0.9,
            CAT_SKILL: 1.0,
            CAT_RUNTIME_MODULE: 0.7,
        }.get(self.category, 1.0)
        return base


@dataclass
class RouteMatch:
    """A ranked match from :func:`route`."""

    entry: AgentEntry
    score: float
    matched_keywords: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.entry.name,
            "pool_id": self.entry.pool_id,
            "category": self.entry.category,
            "domain": self.entry.domain,
            "score": round(self.score, 3),
            "matched": self.matched_keywords,
            "path": self.entry.path,
        }


# ─── Keyword extraction ────────────────────────────────────────────────

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "this",
    "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
    "what", "which", "who", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "and", "or", "but", "if", "then", "else", "for", "of", "to", "in",
    "on", "at", "by", "with", "from", "up", "about", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "again", "further", "once", "here", "there", "your", "my", "me",
    "them", "their", "his", "her", "its", "our", "us",
})


def _extract_keywords(text: str, max_words: int = 40) -> tuple[str, ...]:
    """Pull the most informative words/short-phrases from text."""
    text = text.lower()
    # Grab hyphenated and underscored terms whole
    special = re.findall(r"[a-z][a-z0-9_-]{2,}", text)
    words = []
    seen = set()
    for w in special:
        w_clean = w.strip("-_")
        if (
            w_clean
            and w_clean not in _STOPWORDS
            and len(w_clean) >= 3
            and w_clean not in seen
        ):
            seen.add(w_clean)
            words.append(w_clean)
            if len(words) >= max_words:
                break
    return tuple(words)


def _extract_from_frontmatter(content: str) -> Tuple[str, str, tuple[str, ...]]:
    """Extract (name, description, keywords) from YAML frontmatter."""
    name = ""
    description = ""
    keywords: tuple[str, ...] = ()

    # Try to parse YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        for line in fm.split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"\'')
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"\'')
            elif line.startswith("tags:"):
                tag_val = line.split(":", 1)[1].strip()
                tags = [t.strip().strip('"\'') for t in tag_val.strip("[]").split(",")]
                keywords = keywords + tuple(t for t in tags if t)

    # Also pull from markdown headings
    if not description:
        heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if heading:
            name = name or heading.group(1).strip()

    # Extract keywords from first few non-frontmatter lines
    body_start = content.find("---\n", content.find("---\n") + 1) + 4 if "---" in content[:200] else 0
    body = content[body_start:body_start + 500] if body_start < len(content) else content[:500]
    if body:
        body_kw = _extract_keywords(body, max_words=20)
        keywords = keywords + body_kw

    return name, description, keywords


# ─── Pool builder ──────────────────────────────────────────────────────

_REPO_ROOT: Optional[Path] = None


def _repo_root() -> Path:
    global _REPO_ROOT
    if _REPO_ROOT is None:
        # Walk up from this file to find the repo root
        p = Path(__file__).resolve()
        for parent in [p.parent, *p.parents]:
            if (parent / "run_agent.py").exists() or (parent / "pyproject.toml").exists():
                _REPO_ROOT = parent
                break
        else:
            _REPO_ROOT = p.parent.parent.parent  # best effort
    return _REPO_ROOT


def _scan_md_agents(base: Path, category: str) -> list[AgentEntry]:
    """Scan a directory of .md agent definitions."""
    entries: list[AgentEntry] = []
    if not base.exists():
        return entries
    for md_file in sorted(base.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            continue

        name, description, kw = _extract_from_frontmatter(content)
        if not name:
            name = md_file.stem

        rel = md_file.relative_to(_repo_root())
        # Infer domain from parent directory
        parts = rel.parts
        domain = "general"
        for part in parts:
            if part in DOMAIN_MAP:
                domain = part
                break

        # Add domain keywords
        domain_kw = DOMAIN_MAP.get(domain, [])
        all_kw = tuple(set(kw + tuple(domain_kw)))

        pool_id = f"{category}:{md_file.stem}"
        entries.append(AgentEntry(
            pool_id=pool_id,
            name=name,
            category=category,
            domain=domain,
            path=str(rel).replace("\\", "/"),
            description=description[:200] if description else f"{category} agent: {name}",
            keywords=all_kw[:25],
            source_line=f"scanned from {rel}",
        ))
    return entries


def _scan_skills(base: Path) -> list[AgentEntry]:
    """Scan SKILL.md files."""
    entries: list[AgentEntry] = []
    if not base.exists():
        return entries
    for skill_md in sorted(base.rglob("SKILL.md")):
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            continue

        name, description, kw = _extract_from_frontmatter(content)
        if not name:
            name = skill_md.parent.name

        rel = skill_md.relative_to(_repo_root())
        # Infer domain from parent category directory
        domain = "skill"
        parts = rel.parts
        if len(parts) >= 3 and parts[1] != "SKILL.md":
            domain = parts[1]

        pool_id = f"skill:{name}"
        entries.append(AgentEntry(
            pool_id=pool_id,
            name=name,
            category=CAT_SKILL,
            domain=domain,
            path=str(rel).replace("\\", "/"),
            description=description[:200] if description else f"skill: {name}",
            keywords=kw[:25],
            source_line=f"skill at {rel}",
        ))
    return entries


def _scan_python_modules(base: Path, category: str, domain: str = "runtime") -> list[AgentEntry]:
    """Scan Python modules as runtime agent capabilities."""
    entries: list[AgentEntry] = []
    if not base.exists():
        return entries
    for py_file in sorted(base.rglob("*.py")):
        if py_file.name in ("__init__.py", "__main__.py", "setup.py"):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")[:1500]
        except Exception:
            continue

        # Extract module docstring
        doc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        doc = doc_match.group(1).strip()[:200] if doc_match else ""
        name = py_file.stem
        kw = _extract_keywords(doc + " " + name, max_words=15)
        rel = py_file.relative_to(_repo_root())
        pool_id = f"{category}:{name}"

        entries.append(AgentEntry(
            pool_id=pool_id,
            name=name,
            category=category,
            domain=domain,
            path=str(rel).replace("\\", "/"),
            description=doc or f"{category}: {name}",
            keywords=kw[:15],
            source_line=f"module at {rel}",
        ))
    return entries


# ─── Pool singleton ────────────────────────────────────────────────────

@dataclass
class AgentPool:
    """The unified agent pool — 670+ entries in one flat registry."""

    entries: list[AgentEntry] = field(default_factory=list)
    _index: dict[str, AgentEntry] = field(default_factory=dict)
    _built_at: float = 0.0

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def domains(self) -> list[str]:
        return sorted(set(e.domain for e in self.entries))

    @property
    def categories(self) -> list[str]:
        return sorted(set(e.category for e in self.entries))

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.category] = counts.get(e.category, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def get(self, pool_id: str) -> Optional[AgentEntry]:
        return self._index.get(pool_id)

    def by_domain(self, domain: str) -> list[AgentEntry]:
        return [e for e in self.entries if e.domain == domain]

    def by_category(self, category: str) -> list[AgentEntry]:
        return [e for e in self.entries if e.category == category]

    def search(self, query: str, limit: int = 20) -> list[AgentEntry]:
        """Simple keyword search over the pool."""
        return [m.entry for m in _score_entries(self.entries, query, limit)]

    def system_prompt_excerpt(self, max_entries: int = 60) -> str:
        """A compact excerpt for the system prompt.

        Shows the model what agent pool is available so it can
        self-activate without slash commands.
        """
        counts = self.category_counts()
        total = len(self.entries)

        lines = [
            f"## Unified Agent Pool ({total} agents)",
            "",
            "You have a unified pool of specialized agents. **Do not ask the user",
            "to type slash commands.** When a task matches an agent's domain,",
            "activate it autonomously by loading the relevant skill or delegating",
            "to a specialist. Categories:",
            "",
        ]

        for cat, count in counts.items():
            # Friendly category name
            display = cat.replace("_", " ").title()
            lines.append(f"- **{display}** ({count} agents)")

        lines.append("")
        lines.append("### Domain index")
        lines.append("")

        # Group by domain, show top entries per domain
        by_domain: dict[str, list[AgentEntry]] = {}
        for e in self.entries:
            by_domain.setdefault(e.domain, []).append(e)

        shown = 0
        for domain in sorted(by_domain.keys()):
            if shown >= max_entries:
                break
            entries_in_domain = by_domain[domain]
            # Show up to 3 representative entries per domain
            for e in entries_in_domain[:3]:
                if shown >= max_entries:
                    break
                desc = e.description[:80] if e.description else ""
                lines.append(f"- `{e.name}` ({domain}) — {desc}")
                shown += 1

        lines.extend([
            "",
            "### How to use the pool",
            "",
            "1. **Understand the user's intent** from their message — no slash command needed.",
            "2. **Match to agents** by domain and keywords.",
            "3. **Activate** by loading the skill (`skill_view`), delegating (`delegate_task`),",
            "   or invoking the swarm pipeline.",
            "4. **Execute autonomously** — do not ask permission for routine work within",
            "   your authorized scope. Only defer for owner-gated actions.",
            "",
        ])

        return "\n".join(lines)


# ─── Scoring / routing ─────────────────────────────────────────────────

def _score_entries(
    entries: list[AgentEntry],
    query: str,
    limit: int,
) -> list[RouteMatch]:
    """Score entries against a query string."""
    query_lower = query.lower()
    query_words = set(_extract_keywords(query_lower))
    # Also add raw words
    query_words.update(w for w in re.findall(r"[a-z]{3,}", query_lower) if w not in _STOPWORDS)

    results: list[RouteMatch] = []
    for entry in entries:
        matched: list[str] = []
        score = 0.0

        for kw in entry.keywords:
            kw_lower = kw.lower()
            if kw_lower in query_words:
                score += 1.0
                matched.append(kw)
            elif any(qw in kw_lower or kw_lower in qw for qw in query_words) and len(kw_lower) >= 4:
                score += 0.5
                matched.append(kw)

        # Domain bonus
        if entry.domain in query_lower:
            score += 0.5
            matched.append(f"domain:{entry.domain}")

        # Name exact match bonus
        if entry.name.lower() in query_lower:
            score += 1.5
            matched.append(f"name:{entry.name}")

        if score > 0:
            score *= entry.weight
            results.append(RouteMatch(entry=entry, score=score, matched_keywords=matched))

    results.sort(key=lambda r: -r.score)
    return results[:limit]


# ─── Pool construction ─────────────────────────────────────────────────

_POOL: Optional[AgentPool] = None
_POOL_HASH: Optional[str] = None


def _compute_pool_hash(paths: list[Path]) -> str:
    """Cheap hash to detect if the pool needs rebuilding."""
    h = hashlib.md5()
    for p in paths:
        try:
            st = p.stat()
            h.update(f"{p}:{st.st_mtime}:{st.st_size}".encode())
        except Exception:
            pass
    return h.hexdigest()


def build_pool(repo_root: Optional[Path] = None) -> AgentPool:
    """Build the unified agent pool from the filesystem.

    Scans every agent-capable definition in the repo and merges them
    into one flat pool with uniform metadata.
    """
    root = repo_root or _repo_root()
    entries: list[AgentEntry] = []

    # 1. AOS council agents (261 across 17 domains)
    aos_agents = root / "skills" / "aos-enterprise-council" / "agents"
    entries.extend(_scan_md_agents(aos_agents, CAT_AOS_COUNCIL))

    # 2. AOS specialists
    specialists = root / "skills" / "aos-enterprise-council" / "specialists"
    entries.extend(_scan_md_agents(specialists, CAT_AOS_SPECIALIST))

    # 3. AOS workers
    workers = root / "skills" / "aos-enterprise-council" / "workers"
    entries.extend(_scan_md_agents(workers, CAT_AOS_WORKER))

    # 4. AOS runnable agents
    runnable = root / "skills" / "aos-enterprise-council" / "runnable-agents"
    entries.extend(_scan_md_agents(runnable, CAT_AOS_RUNNABLE))

    # 5. AOS templates
    templates = root / "skills" / "aos-enterprise-council" / "templates"
    entries.extend(_scan_md_agents(templates, CAT_AOS_TEMPLATE))

    # 6. All skills (SKILL.md files)
    skills_dir = root / "skills"
    entries.extend(_scan_skills(skills_dir))

    # 7. .claude/agents
    claude_agents = root / ".claude" / "agents"
    entries.extend(_scan_md_agents(claude_agents, CAT_CLAUDE_AGENT))

    # 8. dotclaude/agents
    dotclaude_agents = root / "dotclaude" / "agents"
    entries.extend(_scan_md_agents(dotclaude_agents, CAT_DOTCLAUDE_AGENT))

    # 9. Agent Python modules (runtime adapters)
    agent_dir = root / "agent"
    entries.extend(_scan_python_modules(agent_dir, CAT_RUNTIME_MODULE, "runtime"))

    # 10. Swarm modules
    swarm_dir = root / "hermes_cli" / "swarm"
    entries.extend(_scan_python_modules(swarm_dir, CAT_SWARM, "swarm"))

    # 11. AXIOM kernel modules
    axiom_dir = root / "axiom" / "axiom"
    entries.extend(_scan_python_modules(axiom_dir, CAT_AXIOM, "axiom"))

    # Deduplicate by pool_id (keep highest-weight entry)
    seen: dict[str, AgentEntry] = {}
    for e in entries:
        existing = seen.get(e.pool_id)
        if existing is None or e.weight > existing.weight:
            seen[e.pool_id] = e

    final_entries = list(seen.values())
    final_entries.sort(key=lambda e: (e.category, e.domain, e.name))

    pool = AgentPool(
        entries=final_entries,
        _index={e.pool_id: e for e in final_entries},
        _built_at=time.time(),
    )

    logger.info(
        "Agent pool built: %d entries across %d domains, %d categories",
        len(pool), len(pool.domains), len(pool.categories),
    )
    return pool


def get_pool(force_rebuild: bool = False) -> AgentPool:
    """Get the cached pool, building it on first call."""
    global _POOL, _POOL_HASH
    if _POOL is not None and not force_rebuild:
        return _POOL
    _POOL = build_pool()
    return _POOL


# ─── Public routing API ────────────────────────────────────────────────

def route(
    message: str,
    limit: int = 5,
    min_score: float = 0.5,
) -> list[RouteMatch]:
    """Route a user message to the best-matching agents.

    No slash commands required.  The message is classified by domain
    and keyword overlap, and the top agents are returned.

    Args:
        message: Raw user message text.
        limit: Maximum number of matches to return.
        min_score: Minimum score threshold (0-10 scale).

    Returns:
        Ranked list of :class:`RouteMatch` objects.
    """
    pool = get_pool()
    matches = _score_entries(pool.entries, message, limit * 3)
    # Filter by minimum score
    matches = [m for m in matches if m.score >= min_score]
    return matches[:limit]


def route_to_prompt(message: str, limit: int = 5) -> str:
    """Route a message and return a prompt fragment for the model.

    This is injected into the context so the model knows which agents
    are relevant for the current user message and can activate them
    directly.
    """
    matches = route(message, limit=limit)
    if not matches:
        return ""

    lines = [
        "### Autonomous agent activation",
        "",
        "The following specialized agents from the pool (670+) match your request.",
        "Activate them directly — do not ask the user to type any slash command.",
        "",
    ]

    for i, m in enumerate(matches, 1):
        e = m.entry
        lines.append(
            f"{i}. **{e.name}** ({e.category.replace('_', ' ')}, {e.domain}) "
            f"— score {m.score:.1f}"
        )
        if e.description:
            lines.append(f"   {e.description[:120]}")
        if m.matched_keywords:
            kw_str = ', '.join(m.matched_keywords[:5])
            lines.append(f"   matched: {kw_str}")
        lines.append(f"   path: {e.path}")
        lines.append("")

    lines.append(
        "Load the relevant skill with `skill_view` or delegate with `delegate_task` "
        "as appropriate. Execute autonomously within your authorized scope."
    )

    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────────────────────

def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Unified Agent Pool")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("stats", help="Show pool statistics")
    sub.add_parser("domains", help="List all domains")

    p_search = sub.add_parser("search", help="Search the pool")
    p_search.add_argument("query", nargs="+")

    p_route = sub.add_parser("route", help="Route a message")
    p_route.add_argument("message", nargs="+")

    p_prompt = sub.add_parser("prompt", help="System prompt excerpt")
    p_prompt.add_argument("--max", type=int, default=60)

    args = parser.parse_args()
    cmd = args.cmd or "stats"

    if cmd == "stats":
        pool = get_pool()
        print(f"Pool: {len(pool)} agents")
        print(f"Domains: {len(pool.domains)}")
        print(f"\nBy category:")
        for cat, count in pool.category_counts().items():
            print(f"  {cat:25s} {count:4d}")
        print(f"\nDomains: {', '.join(pool.domains)}")

    elif cmd == "domains":
        pool = get_pool()
        for d in pool.domains:
            entries = pool.by_domain(d)
            print(f"\n{d} ({len(entries)}):")
            for e in entries[:5]:
                print(f"  {e.name:40s} [{e.category}]")
            if len(entries) > 5:
                print(f"  ... and {len(entries) - 5} more")

    elif cmd == "search":
        query = " ".join(args.query)
        pool = get_pool()
        for m in pool.search(query, limit=10):
            print(f"  {m.name:40s} [{m.category}/{m.domain}] {m.path}")

    elif cmd == "route":
        message = " ".join(args.message)
        for m in route(message):
            print(f"  {m.score:6.2f}  {m.entry.name:40s} [{m.entry.category}/{m.entry.domain}]")
            print(f"           matched: {', '.join(m.matched_keywords[:5])}")

    elif cmd == "prompt":
        pool = get_pool()
        print(pool.system_prompt_excerpt(max_entries=args.max))

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
