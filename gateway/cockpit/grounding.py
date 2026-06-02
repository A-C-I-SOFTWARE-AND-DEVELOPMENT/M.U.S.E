"""Reference grounding for the cockpit chat — "read me + the project docs".

Gives JARVIS lightweight, always-available context about **the owner** and
**what reference material exists** (plan + doc files), so replies are grounded
in the project rather than generic. Two bounded blocks, both cached:

* **Owner profile** — a capped excerpt of a persisted profile file if one
  exists (``$HERMES_HOME/profile.md`` or the active profile dir), so JARVIS
  "reads you".
* **Reference index** — paths + first heading of the key docs and plan files
  (``AGENTS.md``, ``CLAUDE.md``, ``README.md``, ``docs/*.md``, and any
  ``*plan*.md`` / ``plan/`` files), so JARVIS knows what it can cite and pull.

We index *titles + paths*, not full bodies: a phone model's context can't hold
every file, and full-content retrieval belongs in the memory layer (recollect).
This block makes JARVIS aware of the references; deep lookups go through memory.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

_PROFILE_BUDGET = 800
_INDEX_BUDGET = 1400
_MAX_FILES = 40


def _repo_root() -> Path:
    env = os.environ.get("HERMES_REPO_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "AGENTS.md").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def _first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s:
                return s.lstrip("# ").strip()[:80]
    except Exception:
        pass
    return ""


def _owner_profile_block() -> str:
    home = Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))
    for candidate in (home / "profile.md", home / "owner.md", home / "profile.txt"):
        try:
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    return "About the owner (from your profile):\n" + text[:_PROFILE_BUDGET]
        except Exception:
            continue
    return ""


def _reference_index_block(root: Path) -> str:
    seen: set[Path] = set()
    files: list[Path] = []
    for name in ("AGENTS.md", "CLAUDE.md", "README.md"):
        p = root / name
        if p.is_file():
            files.append(p)
            seen.add(p)
    for pattern in ("docs/*.md", "docs/**/*plan*.md", "plan/*.md", "*plan*.md"):
        for p in sorted(root.glob(pattern)):
            if p.is_file() and p not in seen:
                files.append(p)
                seen.add(p)
    if not files:
        return ""
    lines = ["Reference material you can cite (ask to open any for detail):"]
    for p in files[:_MAX_FILES]:
        rel = p.relative_to(root)
        heading = _first_heading(p)
        lines.append(f"- {rel}" + (f" — {heading}" if heading else ""))
    block = "\n".join(lines)
    return block[:_INDEX_BUDGET]


@lru_cache(maxsize=1)
def _cached_index(root_str: str) -> str:
    return _reference_index_block(Path(root_str))


def reference_context(repo_root: Optional[str] = None) -> str:
    """Bounded grounding block to append to the persona prompt. Never raises."""
    try:
        root = Path(repo_root) if repo_root else _repo_root()
        parts = [b for b in (_owner_profile_block(), _cached_index(str(root))) if b]
        return ("\n\n".join(parts)) if parts else ""
    except Exception:  # grounding is best-effort — never break chat
        return ""


__all__ = ["reference_context"]
