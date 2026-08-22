"""Symbol graph — defined symbols + import edges across the repo.

Python files are parsed with the stdlib ``ast`` module (accurate, no
dependencies). Other languages get a light regex pass good enough for
localization signals. The output is two maps:

- ``symbols``: symbol name -> set of files that define it.
- ``imports``: file -> set of module/path tokens it imports.

This is deliberately lexical/structural, not semantic. It exists to feed the
issue localizer and dependency tracer with cheap, deterministic signals.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from plugins.prime.navigation.repo_index import IndexedFile, RepoIndex

# Lightweight import patterns for non-Python languages.
_JS_IMPORT_RE = re.compile(
    r"""(?:import[^'"]*from\s*['"]([^'"]+)['"])|(?:require\(\s*['"]([^'"]+)['"]\s*\))"""
)
_JS_SYMBOL_RE = re.compile(
    r"""(?:function\s+([A-Za-z_$][\w$]*))"""
    r"""|(?:class\s+([A-Za-z_$][\w$]*))"""
    r"""|(?:(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=)"""
)


@dataclass
class SymbolGraph:
    """Maps symbol names to defining files and files to their imports."""

    symbols: dict[str, set[str]] = field(default_factory=dict)
    imports: dict[str, set[str]] = field(default_factory=dict)
    # file -> set of symbol names it defines (the inverse of `symbols`).
    file_symbols: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, index: RepoIndex) -> "SymbolGraph":
        graph = cls()
        for f in index.files:
            if f.role not in {"source", "test"}:
                continue
            abs_path = index.root / f.path
            text = _read(abs_path)
            if text is None:
                continue
            if f.language == "python":
                defined, imported = _parse_python(text)
            elif f.language in {"javascript", "typescript"}:
                defined, imported = _parse_js_like(text)
            else:
                defined, imported = set(), set()
            graph.file_symbols[f.path] = defined
            graph.imports[f.path] = imported
            for sym in defined:
                graph.symbols.setdefault(sym, set()).add(f.path)
        return graph

    def importers_of(self, target: IndexedFile | str) -> set[str]:
        """Files whose import tokens plausibly reference ``target``.

        Matching is by module stem (``foo`` for ``pkg/foo.py``) and by the
        dotted module path, so both ``import pkg.foo`` and ``from pkg import
        foo`` style references are caught without resolving the import system.
        """

        path = target.path if isinstance(target, IndexedFile) else target
        stem = Path(path).stem
        dotted = _module_path(path)
        out: set[str] = set()
        for importer, tokens in self.imports.items():
            if importer == path:
                continue
            for tok in tokens:
                tok_parts = re.split(r"[./]", tok)
                if stem in tok_parts or tok == dotted or tok.endswith("." + stem):
                    out.add(importer)
                    break
        return out


def _module_path(rel_path: str) -> str:
    p = Path(rel_path)
    parts = list(p.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _parse_python(text: str) -> tuple[set[str], set[str]]:
    defined: set[str] = set()
    imported: set[str] = set()
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return defined, imported
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod:
                imported.add(mod)
            for alias in node.names:
                imported.add(f"{mod}.{alias.name}" if mod else alias.name)
    return defined, imported


def _parse_js_like(text: str) -> tuple[set[str], set[str]]:
    defined: set[str] = set()
    imported: set[str] = set()
    for m in _JS_SYMBOL_RE.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3)
        if name:
            defined.add(name)
    for m in _JS_IMPORT_RE.finditer(text):
        mod = m.group(1) or m.group(2)
        if mod:
            imported.add(mod)
    return defined, imported


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
