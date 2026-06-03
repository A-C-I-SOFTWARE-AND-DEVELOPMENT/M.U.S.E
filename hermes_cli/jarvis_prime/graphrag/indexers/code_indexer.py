"""Repo code indexer — turn the HyperAgent navigation substrate into graph
nodes and edges.

Reuses the existing deterministic navigation modules rather than re-walking or
re-parsing the repo from scratch:

* :class:`RepoIndex` — the classified file list (FILE nodes).
* :class:`SymbolGraph` — import tokens + defined symbols (IMPORTS edges,
  function/class resolution for CALLS).
* :class:`DependencyTracer` — test links + dependents (TESTS / DEPENDS_ON).

On top of those it adds the typed entities the GraphRAG vocabulary needs but
the navigator does not model: FUNCTION / CLASS (python, via stdlib ``ast``),
SCREEN (Android ``*Screen.kt``), and API / ROUTE (cockpit-style route tables).

All signals are deterministic and source-backed; nothing is invented.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from hermes_cli.jarvis_prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id
from hermes_cli.jarvis_prime.navigation.repo_index import RepoIndex
from hermes_cli.jarvis_prime.navigation.symbol_graph import SymbolGraph

# Recognise a stdlib router route tuple, e.g.
#   ("GET", _compile("/v1/cockpit/jobs"), h.jobs_list, True),
_ROUTE_RE = re.compile(
    r"""\(\s*["'](GET|POST|PUT|PATCH|DELETE)["']\s*,\s*"""
    r"""_compile\(\s*["']([^"']+)["']\s*\)\s*,\s*"""
    r"""([A-Za-z_][\w.]*)"""
)


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

    # 1. FILE / SCREEN nodes for every classified file.
    for f in index.files:
        is_screen = (
            f.language == "kotlin"
            and f.name.endswith("Screen.kt")
            and "android" in f.path.lower()
        )
        if is_screen:
            screen = graph.add_node(
                NodeType.SCREEN,
                f.stem,
                title=f.stem,
                attrs={"path": f.path, "language": f.language},
                sources=[_src(f.path)],
            )
            file_node = graph.add_node(
                NodeType.FILE,
                f.path,
                title=f.name,
                attrs={"language": f.language, "role": f.role},
                sources=[_src(f.path)],
            )
            graph.add_edge(
                file_node.id, screen.id, EdgeType.OWNS, sources=[_src(f.path)]
            )
        else:
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

    # 5. API / ROUTE nodes from route tables (cockpit-style).
    _index_routes(graph, index)

    # 6. MODULE nodes for python packages (dirs with __init__.py).
    _index_modules(graph, index)

    return graph


def _index_modules(graph: KnowledgeGraph, index: RepoIndex) -> None:
    """A MODULE node per python package, owning the files directly inside it."""

    package_dirs: set[str] = set()
    for f in index.files:
        if f.name == "__init__.py":
            package_dirs.add(str(Path(f.path).parent))
    for f in index.files:
        if f.language != "python" or f.role not in {"source", "test"}:
            continue
        parent = str(Path(f.path).parent)
        if parent not in package_dirs:
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


def _index_routes(graph: KnowledgeGraph, index: RepoIndex) -> None:
    for f in index.files:
        if not f.path.endswith("server.py"):
            continue
        try:
            text = (index.root / f.path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        matches = _ROUTE_RE.findall(text)
        if not matches:
            continue
        api = graph.add_node(
            NodeType.API,
            f.path,
            title=f"API: {Path(f.path).parent.name}",
            attrs={"path": f.path, "route_count": len(matches)},
            sources=[_src(f.path)],
        )
        for method, path, handler in matches:
            route = graph.add_node(
                NodeType.ROUTE,
                f"{method} {path}",
                title=f"{method} {path}",
                attrs={"method": method, "path": path, "handler": handler},
                sources=[_src(f.path)],
            )
            graph.add_edge(api.id, route.id, EdgeType.OWNS, sources=[_src(f.path)])
            # routes_to: connect the route to the file that owns the handler.
            file_node_id = node_id(NodeType.FILE, f.path)
            if file_node_id in graph.nodes:
                graph.add_edge(
                    route.id, file_node_id, EdgeType.ROUTES_TO, sources=[_src(f.path)]
                )
