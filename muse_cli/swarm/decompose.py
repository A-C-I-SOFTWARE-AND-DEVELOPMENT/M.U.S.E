"""Decomposers — propose how to carve a goal into non-overlapping grains.

The Grainler's deterministic core proves any decomposition disjoint and lowers
it to an execution plan; *this* module is the pluggable front that decides the
carve. Three are provided, smallest-blast-radius first:

* :func:`directory_decomposer` — deterministic, no model. Maps components named
  in the goal onto distinct code directories that exist in the repo, giving each
  its own ``<dir>/**`` domain. Directories are inherently disjoint, so the plan
  always passes ``prove_disjoint``. Falls back to a single whole-repo grain when
  it can't find ≥2 distinct components (which the coordinator then runs inline).
* :func:`keyword_decomposer` — deterministic, maps a small table of component
  keywords (api, web, android, docs, tests, …) to conventional globs.
* :func:`llm_decomposer` — lazily asks a model to propose grain specs, then the
  deterministic proof rejects any overlap. The model never gets to violate the
  non-overlap guarantee; it only proposes.

All three return a list of grain specs (the same shape ``grainler.partition``
accepts), so they are drop-in ``decomposer=`` arguments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
import re

__all__ = [
    "directory_decomposer",
    "keyword_decomposer",
    "llm_decomposer",
    "make_llm_decomposer",
]


# Conventional component → glob table. Kept deliberately small and obvious.
_KEYWORD_GLOBS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("api", "endpoint", "backend", "server"), "api", "src/api/**"),
    (("web", "frontend", "ui", "client"), "web", "src/web/**"),
    (("android", "kotlin", "apk", "mobile"), "android", "apps/android/**"),
    (("doc", "docs", "documentation", "readme"), "docs", "docs/**"),
    (("test", "tests", "coverage"), "tests", "tests/**"),
    (("plugin", "plugins"), "plugins", "plugins/**"),
    (("gateway", "messaging", "telegram", "discord", "slack"), "gateway", "gateway/**"),
    (("skill", "skills"), "skills", "skills/**"),
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _code_dirs(repo: Path) -> list[Path]:
    """Candidate code directories: top-level + one level under common roots."""

    roots: list[Path] = []
    repo = Path(repo)
    skip = {".git", "node_modules", "__pycache__", ".hermes", ".hermes-orchestrator"}
    try:
        for child in sorted(repo.iterdir()):
            if child.is_dir() and child.name not in skip and not child.name.startswith("."):
                roots.append(child)
                # one level deeper for conventional containers
                if child.name in {"src", "apps", "packages", "services"}:
                    for sub in sorted(child.iterdir()):
                        if sub.is_dir() and not sub.name.startswith("."):
                            roots.append(sub)
    except OSError:
        return []
    return roots


def directory_decomposer(goal: str, repo_root: str) -> list[dict]:
    """Split ``goal`` across distinct repo directories it names.

    Each matched directory becomes a grain owning ``<reldir>/**``. Returns a
    single whole-repo grain when fewer than two distinct directories match.
    """

    repo = Path(repo_root)
    goal_tokens = _tokens(goal)
    matched: list[tuple[str, str]] = []  # (reldir, glob)
    seen: set[str] = set()
    for d in _code_dirs(repo):
        try:
            rel = d.relative_to(repo).as_posix()
        except ValueError:
            continue
        # A directory matches when its basename (or its rel path segment) is
        # named in the goal.
        if d.name.lower() in goal_tokens and rel not in seen:
            matched.append((rel, f"{rel}/**"))
            seen.add(rel)

    # Prefer the deepest, most specific matches and drop ancestors so domains
    # stay disjoint (e.g. keep src/api/** but not src/** when both matched).
    matched = _drop_ancestor_dirs(matched)

    if len(matched) < 2:
        return [{"intent": goal, "globs": ["**"]}]

    return [
        {
            "intent": f"{goal} — work scoped to {rel}/",
            "globs": [glob],
            "grain_id": f"g{idx:02d}-{re.sub(r'[^a-z0-9]+', '-', rel.lower()).strip('-')}",
        }
        for idx, (rel, glob) in enumerate(matched)
    ]


def _drop_ancestor_dirs(matched: list[tuple[str, str]]) -> list[tuple[str, str]]:
    rels = [r for r, _ in matched]
    keep: list[tuple[str, str]] = []
    for rel, glob in matched:
        # Drop rel if some other matched dir is strictly deeper under it.
        if any(other != rel and other.startswith(rel + "/") for other in rels):
            continue
        keep.append((rel, glob))
    return keep


def keyword_decomposer(goal: str, repo_root: str) -> list[dict]:
    """Map component keywords named in the goal to conventional globs."""

    goal_tokens = _tokens(goal)
    specs: list[dict] = []
    used: set[str] = set()
    for keywords, name, glob in _KEYWORD_GLOBS:
        if goal_tokens & set(keywords) and glob not in used:
            specs.append(
                {
                    "intent": f"{goal} — {name}",
                    "globs": [glob],
                    "grain_id": f"g{len(specs):02d}-{name}",
                }
            )
            used.add(glob)
    if len(specs) < 2:
        return [{"intent": goal, "globs": ["**"]}]
    return specs


def make_llm_decomposer(agent_factory):
    """Build an ``llm_decomposer`` bound to an agent factory (for DI/testing).

    ``agent_factory()`` must return an object with a ``chat(prompt) -> str``
    method that returns a JSON array of ``{intent, globs}`` specs. The returned
    decomposer parses that, and ``grainler.partition`` proves it disjoint —
    rejecting any overlapping proposal the model makes.
    """

    import json

    def _decompose(goal: str, repo_root: str) -> list[dict]:
        prompt = _LLM_PROMPT.format(goal=goal, repo=repo_root)
        agent = agent_factory()
        raw = agent.chat(prompt)
        specs = _parse_specs(raw, json)
        return specs or [{"intent": goal, "globs": ["**"]}]

    return _decompose


def llm_decomposer(goal: str, repo_root: str) -> list[dict]:
    """Default LLM decomposer: lazily build a plain agent and ask for grains."""

    def _factory():
        from run_agent import AIAgent

        return AIAgent(skip_context_files=True, skip_memory=True)

    return make_llm_decomposer(_factory)(goal, repo_root)


def _parse_specs(raw: str, json_mod) -> list[dict]:
    text = (raw or "").strip()
    # Tolerate a fenced ```json block.
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json_mod.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        intent = item.get("intent") or item.get("mission")
        globs = item.get("globs") or item.get("allowed_files")
        if not intent or not globs:
            continue
        spec = {"intent": str(intent), "globs": [str(g) for g in globs]}
        if item.get("model_lane"):
            spec["model_lane"] = str(item["model_lane"])
        out.append(spec)
    return out


_LLM_PROMPT = """You are the Grainler — you decompose a coding goal into parallel,
NON-OVERLAPPING grains. Each grain owns a disjoint set of file globs; no two
grains may share any file. Return ONLY a JSON array of objects:
[{{"intent": "...", "globs": ["dir/**"], "model_lane": "claude"}}]

Rules:
- Grains MUST own disjoint file-domains (no shared paths). If you can't split
  cleanly, return a single grain owning ["**"].
- Prefer directory-scoped globs (e.g. "src/api/**", "src/web/**").
- 2-6 grains for a multi-component goal.

Repo root: {repo}
Goal: {goal}
"""
