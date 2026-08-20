"""Guard against merges that ship imports of symbols which do not exist.

The v0.20.0 upstream merge resolved file-by-file inconsistently: it kept one
side's version of ``hermes_cli/auth.py``, ``config.py`` and ``checkpoints.py``
while keeping the *other* side's modules that import from them. The result was
67 dangling symbols -- 13 of which crashed on import, taking down the TUI
gateway in a restart loop with ``error: gateway exited (1)``.

Nothing caught it, because a dangling ``from X import NAME`` is only a runtime
error and no test imported those paths on Windows.

This test parses the tree and fails on any ``from <internal module> import
NAME`` where NAME is never defined at module level in the target. It is pure
AST -- nothing is imported, so it has no side effects and runs in ~1s.

See docs/consolidation/PORT-LEDGER.md for the incident this guards against.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories that are not part of the importable application surface.
SKIP_DIRS = {
    ".git", "venv", ".venv", "node_modules", "__pycache__", "tests", "test",
    "recovered-agent-sources", "ui-tui", "apps", "build", "dist",
    "site-packages", "benchmarks", "website", "third_party", ".tanstack",
}

# Imports that are intentionally optional: the module genuinely may not exist
# in a given deployment and every call site guards with try/except. Keep this
# list short and justified -- it is an allowlist for *known* absent modules,
# not a dumping ground for new breakage.
KNOWN_OPTIONAL = {
    ("plugins.memory", "sqlite"),
    ("plugins.github_assistant", "api"),
}


def _iter_py_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _module_name(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_level_names(tree: ast.Module) -> tuple[set[str], bool]:
    """Every name bound at module import time, and whether the true surface is
    unknowable statically -- either a star-import, or a module-level
    ``__getattr__`` (PEP 562) that resolves attributes dynamically.

    ``tools/skills_hub.py`` is the live example: it serves ``HUB_DIR``,
    ``SKILLS_DIR`` and friends through ``__getattr__`` so they follow the
    active profile override. Those imports resolve fine at runtime, so
    flagging them would be a false positive.
    """
    names: set[str] = set()
    star = False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
            star = True  # dynamic surface; cannot judge statically
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    star = True
                else:
                    names.add(alias.asname or alias.name)
    return names, star


@pytest.fixture(scope="module")
def tree_index():
    exports: dict[str, set[str]] = {}
    trees: dict[Path, ast.Module] = {}
    for path in _iter_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue  # not our problem; a syntax test would catch it
        trees[path] = tree
        names, star = _module_level_names(tree)
        if star:
            names.add("*STAR*")
        exports[_module_name(path)] = names
    return exports, trees


def test_no_dangling_internal_imports(tree_index):
    exports, trees = tree_index
    offences: list[str] = []

    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            target = node.module
            if not target or target not in exports:
                continue  # third-party or namespace package
            available = exports[target]
            if "*STAR*" in available:
                continue  # star-import makes the real surface unknowable
            for alias in node.names:
                name = alias.name
                if name == "*":
                    continue
                if (target, name) in KNOWN_OPTIONAL:
                    continue
                # `from package import submodule` is legal.
                if f"{target}.{name}" in exports:
                    continue
                if name not in available:
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    offences.append(f"{rel}:{node.lineno}: {target}.{name}")

    assert not offences, (
        f"{len(offences)} import(s) reference symbols that do not exist.\n"
        "This is what a bad merge looks like: a module was taken from one side "
        "while its importers came from the other.\n"
        "Restore the definition from the merge parent that has it, or fix the "
        "import to point at the symbol's real home.\n\n"
        + "\n".join(f"  {o}" for o in sorted(offences))
    )
