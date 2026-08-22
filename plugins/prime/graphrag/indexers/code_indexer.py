"""Repo code indexer — turn the navigation substrate into graph nodes/edges.

Reuses the existing deterministic navigation modules rather than re-walking the
repo:

* :class:`RepoIndex` — the classified file list, shared with the docs indexer
  so the tree is walked once (FILE nodes).
* :class:`SymbolGraph` — import tokens + defined symbols (IMPORTS edges,
  function/class resolution for CALLS).

On top of those it adds the typed entities the navigator does not model:
FUNCTION and CLASS nodes (python) plus MODULE nodes for python packages.

Cost note: those entities need line numbers and call sites, which
:class:`SymbolGraph` does not retain, so :func:`_index_python_symbols` runs a
second ``ast.parse`` pass over the python files. A full build is therefore
roughly two parses per python file — order a minute on a ten-thousand-file
checkout. Build it once with ``hermes graph build``; the result is a cache.

All signals are deterministic and source-backed; nothing is invented.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from plugins.prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id
from plugins.prime.navigation.repo_index import RepoIndex
from plugins.prime.navigation.symbol_graph import SymbolGraph


def _src(path: str, **extra) -> dict:
    d = {"uri": path, "kind": "repo"}
    d.update(extra)
    return d


def index_code(
    graph: KnowledgeGraph,
    repo_root,
    *,
    index: RepoIndex | None = None,
    max_call_edges: int = 5000,
) -> KnowledgeGraph:
    """Populate ``graph`` with code entities and relationships from the repo
    rooted at ``repo_root``. Returns the same graph for chaining.
    """

    root = Path(repo_root).resolve()
    index = index or RepoIndex.build(root)
    sym = SymbolGraph.build(index)

    # 1. A FILE node for every classified file.
    for f in index.files:
        graph.add_node(
            NodeType.FILE,
            f.path,
            title=f.name,
            attrs={"language": f.language, "role": f.role},
            sources=[_src(f.path)],
        )

    # 2. FUNCTION / CLASS nodes + CALLS edges (python only — stdlib ast).
    _index_python_symbols(graph, index, sym, max_call_edges=max_call_edges)

    # 3. IMPORTS + DEPENDS_ON edges via a single-pass inverted index
    #    (avoids the O(files^2) cost of resolving importers per target).
    _index_imports(graph, index, sym)

    # 4. TESTS edges by naming convention (test_<stem> / <stem>_test),
    #    complementing the import-based TESTS edges added in step 3.
    _index_tests_by_name(graph, index)

    # 5. MODULE nodes for python packages (dirs with __init__.py).
    _index_modules(graph, index)

    return graph


def _index_modules(graph: KnowledgeGraph, index: RepoIndex) -> None:
    """A MODULE node per python package, owning the files directly inside it."""

    # ``IndexedFile.path`` is POSIX-relative, so derive the parent with
    # ``as_posix()`` rather than ``str()`` — on Windows ``str(PurePath.parent)``
    # yields backslashes and the dotted module name below would never be built
    # (the graph cache would differ between platforms for the same repo).
    package_dirs: set[str] = set()
    for f in index.files:
        if f.name == "__init__.py":
            package_dirs.add(Path(f.path).parent.as_posix())
    for f in index.files:
        if f.language != "python" or f.role not in {"source", "test"}:
            continue
        parent = Path(f.path).parent.as_posix()
        if parent not in package_dirs or parent == ".":
            continue
        dotted = parent.replace("/", ".")
        module = graph.add_node(
            NodeType.MODULE, dotted, title=dotted, attrs={"path": parent},
            sources=[_src(parent)],
        )
        file_id = node_id(NodeType.FILE, f.path)
        if file_id in graph.nodes:
            graph.add_edge(module.id, file_id, EdgeType.OWNS, sources=[_src(f.path)])


# Sentinel for "no indexed file" lookups (keeps role access total).
class _NullFile:
    role = ""


_NULL = _NullFile()


def _index_tests_by_name(graph: KnowledgeGraph, index: RepoIndex) -> None:
    stem_to_sources: dict[str, list[str]] = {}
    for f in index.source_files:
        stem_to_sources.setdefault(Path(f.path).stem.lower(), []).append(f.path)
    for t in index.test_files:
        stem = Path(t.path).stem.lower()
        candidates: set[str] = set()
        if stem.startswith("test_"):
            candidates.add(stem[len("test_"):])
        if stem.endswith("_test"):
            candidates.add(stem[: -len("_test")])
        test_id = node_id(NodeType.FILE, t.path)
        if test_id not in graph.nodes:
            continue
        for cand in candidates:
            for src_path in stem_to_sources.get(cand, ()):
                src_id = node_id(NodeType.FILE, src_path)
                if src_id in graph.nodes:
                    graph.add_edge(
                        test_id, src_id, EdgeType.TESTS, sources=[_src(t.path)]
                    )


def _module_path(rel_path: str) -> str:
    parts = list(Path(rel_path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _index_imports(graph: KnowledgeGraph, index: RepoIndex, sym: SymbolGraph) -> None:
    """Resolve ``file imports module`` edges with one inverted index.

    Mirrors :meth:`SymbolGraph.importers_of` matching (module stem + dotted
    path) but inverted so the whole repo is processed in roughly linear time.
    Ambiguous stems shared by many files are skipped to avoid noise/explosion.
    """

    stem_to_files: dict[str, list[str]] = {}
    dotted_to_file: dict[str, str] = {}
    for f in index.files:
        if f.role not in {"source", "test"}:
            continue
        stem = Path(f.path).stem
        stem_to_files.setdefault(stem, []).append(f.path)
        dotted_to_file[_module_path(f.path)] = f.path

    for importer, tokens in sym.imports.items():
        src_id = node_id(NodeType.FILE, importer)
        if src_id not in graph.nodes:
            continue
        targets: set[str] = set()
        for tok in tokens:
            if tok in dotted_to_file:
                targets.add(dotted_to_file[tok])
                continue
            parts = re.split(r"[./]", tok)
            for part in parts:
                files = stem_to_files.get(part)
                # Only resolve unambiguous stems (defined in <=3 files).
                if files and len(files) <= 3:
                    targets.update(files)
        targets.discard(importer)
        is_test = (index.get(importer) or _NULL).role == "test"
        for tgt in sorted(targets):
            tgt_id = node_id(NodeType.FILE, tgt)
            if tgt_id not in graph.nodes:
                continue
            graph.add_edge(src_id, tgt_id, EdgeType.IMPORTS, sources=[_src(importer)])
            graph.add_edge(src_id, tgt_id, EdgeType.DEPENDS_ON, sources=[_src(importer)])
            # A test importing a source file -> TESTS edge (strongest signal).
            if is_test and (index.get(tgt) or _NULL).role == "source":
                graph.add_edge(src_id, tgt_id, EdgeType.TESTS, sources=[_src(importer)])


def _index_python_symbols(
    graph: KnowledgeGraph,
    index: RepoIndex,
    sym: SymbolGraph,
    *,
    max_call_edges: int,
    max_definers: int = 3,
) -> None:
    """Add FUNCTION/CLASS nodes and CALLS edges from python files.

    One ``ast.parse`` per file (defs + calls collected together). CALLS only
    resolves *direct* ``Name`` calls — never attribute/method calls, whose bare
    names (``to_dict``, ``get``, ``build`` …) are defined in dozens of files and
    would explode the graph. Symbols defined in more than ``max_definers`` files
    are treated as too ambiguous to link.
    """

    # Resolution map: symbol -> defining files, only for unambiguous symbols.
    resolvable: dict[str, list[str]] = {
        name: sorted(files)
        for name, files in sym.symbols.items()
        if 0 < len(files) <= max_definers
    }

    # callers: list of (file, caller_func_name, {called names})
    callers: list[tuple[str, str, set[str]]] = []
    for f in index.files:
        if f.language != "python" or f.role not in {"source", "test"}:
            continue
        try:
            text = (index.root / f.path).read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(text)
        except (OSError, SyntaxError, ValueError):
            continue
        file_node_id = node_id(NodeType.FILE, f.path)
        for node in tree.body:
            _add_def_node(graph, f.path, file_node_id, node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                callers.append((f.path, node.name, _called_names(node, resolvable)))

    call_edges = 0
    for file_path, fn_name, called in callers:
        if call_edges >= max_call_edges:
            break
        caller_id = node_id(NodeType.FUNCTION, f"{file_path}::{fn_name}")
        if caller_id not in graph.nodes:
            continue
        for name in called:
            for definer in resolvable.get(name, ()):
                if definer == file_path:
                    continue
                callee_id = node_id(NodeType.FUNCTION, f"{definer}::{name}")
                if callee_id not in graph.nodes:
                    callee_id = node_id(NodeType.CLASS, f"{definer}::{name}")
                if callee_id in graph.nodes and graph.add_edge(
                    caller_id, callee_id, EdgeType.CALLS, sources=[_src(file_path)]
                ):
                    call_edges += 1
                    if call_edges >= max_call_edges:
                        break


def _add_def_node(graph: KnowledgeGraph, file_path: str, file_node_id: str, node) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nt = NodeType.FUNCTION
    elif isinstance(node, ast.ClassDef):
        nt = NodeType.CLASS
    else:
        return
    def_node = graph.add_node(
        nt,
        f"{file_path}::{node.name}",
        title=node.name,
        attrs={"path": file_path, "lineno": getattr(node, "lineno", 0)},
        sources=[_src(file_path, line_ref=str(getattr(node, "lineno", "")))],
    )
    graph.add_edge(file_node_id, def_node.id, EdgeType.OWNS, sources=[_src(file_path)])


def _called_names(func, resolvable: dict[str, list[str]]) -> set[str]:
    """Direct ``Name`` call targets that resolve to a known repo symbol.

    Attribute (method) calls are intentionally excluded — see
    :func:`_index_python_symbols`.
    """

    names: set[str] = set()
    for sub in ast.walk(func):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            if sub.func.id in resolvable:
                names.add(sub.func.id)
    return names

