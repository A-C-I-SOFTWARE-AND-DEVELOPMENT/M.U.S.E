"""Repository index — the spine of the HyperAgent-style navigator.

Clean-room reimplementation of the "repo map" idea: walk a repository once
and classify every interesting file (source / test / config / doc) with its
language, path, and a cheap content fingerprint. No LLM calls, no network,
stdlib only. The index is the deterministic substrate the symbol graph,
issue localizer, and edit-site ranker all build on.

Design rules:

- Best-effort and side-effect free. Unreadable files are skipped, never fatal.
- Honour an ignore list (``.git``, ``node_modules``, ``.venv`` …) so large
  repos stay fast and we never index vendored junk.
- Pure data out. Callers decide what to do with it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

# Directories we never descend into. Keeps the walk fast and the map clean.
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".idea",
    ".gradle",
    "target",
    ".next",
    ".tox",
    "site-packages",
})

# Extension -> language. Anything not here is classified "other".
_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sh": "shell",
    ".md": "markdown",
    ".rst": "markdown",
    ".txt": "text",
    ".yaml": "config",
    ".yml": "config",
    ".toml": "config",
    ".ini": "config",
    ".cfg": "config",
    ".json": "config",
}

# Filenames that are configuration regardless of extension.
_CONFIG_NAMES: frozenset[str] = frozenset({
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "tox.ini",
    "dockerfile",
    "docker-compose.yml",
    "makefile",
    "requirements.txt",
    "go.mod",
    "cargo.toml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    ".env.example",
    "plugin.yaml",
})

# Roles a file can play. A file can be source AND nothing else; tests and
# config win over plain source when the signals overlap.
FileRole = str  # "source" | "test" | "config" | "doc" | "other"


@dataclass(frozen=True)
class IndexedFile:
    """One classified repository file."""

    path: str  # POSIX-style path relative to repo root
    language: str
    role: FileRole
    size: int
    lines: int

    @property
    def stem(self) -> str:
        return Path(self.path).stem

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "language": self.language,
            "role": self.role,
            "size": self.size,
            "lines": self.lines,
        }


def classify_role(rel_path: str, language: str) -> FileRole:
    """Decide whether a path is a test, config, doc, source, or other file.

    Pure function of the path + language so it is trivially testable.
    """

    p = Path(rel_path)
    name = p.name.lower()
    parts = {part.lower() for part in p.parts}

    if name in _CONFIG_NAMES or language == "config":
        return "config"

    # Test detection: directory named tests/test, or test_*.py / *_test.* /
    # *.test.* / *.spec.* naming conventions.
    if parts & {"tests", "test", "__tests__", "testing"}:
        return "test"
    if name.startswith("test_") or name.startswith("test."):
        return "test"
    stem = p.stem.lower()
    if stem.endswith("_test") or stem.endswith(".test") or stem.endswith(".spec"):
        return "test"

    if language in {"markdown", "text"} or parts & {"docs", "doc"}:
        return "doc"

    if language in {
        "python",
        "javascript",
        "typescript",
        "kotlin",
        "java",
        "go",
        "rust",
        "ruby",
        "c",
        "cpp",
        "shell",
    }:
        return "source"

    return "other"


def detect_language(rel_path: str) -> str:
    return _LANG_BY_EXT.get(Path(rel_path).suffix.lower(), "other")


@dataclass
class RepoIndex:
    """An immutable-ish snapshot of a repository's classified files."""

    root: Path
    files: list[IndexedFile] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def build(
        cls,
        root: os.PathLike[str] | str,
        *,
        ignore_dirs: Iterable[str] | None = None,
        max_file_bytes: int = 2_000_000,
    ) -> "RepoIndex":
        root_path = Path(root).resolve()
        ignore = DEFAULT_IGNORE_DIRS | set(ignore_dirs or ())
        files: list[IndexedFile] = []
        for rel in _walk(root_path, ignore):
            abs_path = root_path / rel
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            language = detect_language(rel)
            lines = 0
            if size <= max_file_bytes and language in {
                "python",
                "javascript",
                "typescript",
                "kotlin",
                "java",
                "go",
                "rust",
                "ruby",
                "c",
                "cpp",
                "shell",
                "markdown",
                "config",
                "text",
            }:
                lines = _count_lines(abs_path)
            files.append(
                IndexedFile(
                    path=rel,
                    language=language,
                    role=classify_role(rel, language),
                    size=size,
                    lines=lines,
                )
            )
        files.sort(key=lambda f: f.path)
        return cls(root=root_path, files=files)

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def by_role(self, role: FileRole) -> list[IndexedFile]:
        return [f for f in self.files if f.role == role]

    @property
    def source_files(self) -> list[IndexedFile]:
        return self.by_role("source")

    @property
    def test_files(self) -> list[IndexedFile]:
        return self.by_role("test")

    @property
    def config_files(self) -> list[IndexedFile]:
        return self.by_role("config")

    @property
    def doc_files(self) -> list[IndexedFile]:
        return self.by_role("doc")

    def by_language(self) -> dict[str, list[IndexedFile]]:
        out: dict[str, list[IndexedFile]] = {}
        for f in self.files:
            out.setdefault(f.language, []).append(f)
        return out

    def get(self, path: str) -> IndexedFile | None:
        for f in self.files:
            if f.path == path:
                return f
        return None

    def summary(self) -> dict[str, object]:
        langs = self.by_language()
        return {
            "root": str(self.root),
            "total_files": len(self.files),
            "by_role": {
                role: len(self.by_role(role))
                for role in ("source", "test", "config", "doc", "other")
            },
            "by_language": {lang: len(items) for lang, items in sorted(langs.items())},
        }


def _walk(root: Path, ignore: set[str]) -> Iterator[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in place so os.walk never descends.
        dirnames[:] = [
            d for d in dirnames if d not in ignore and not d.startswith(".egg")
        ]
        for fname in filenames:
            if fname.startswith("."):
                # Keep a couple of meaningful dotfiles; skip the rest.
                if fname.lower() not in {".env.example"}:
                    continue
            abs_path = Path(dirpath) / fname
            try:
                rel = abs_path.relative_to(root).as_posix()
            except ValueError:
                continue
            yield rel


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0
