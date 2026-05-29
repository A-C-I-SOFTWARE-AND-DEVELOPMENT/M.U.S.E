"""Tests for the navigation repo index, symbol graph, code map, dep tracer."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.navigation.code_map import CodeMap
from hermes_cli.jarvis_prime.navigation.dependency_trace import DependencyTracer
from hermes_cli.jarvis_prime.navigation.repo_index import (
    RepoIndex,
    classify_role,
    detect_language,
)
from hermes_cli.jarvis_prime.navigation.symbol_graph import SymbolGraph


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "calculator.py").write_text(
        "from pkg.helpers import clamp\n\n\n"
        "def add(a, b):\n    return clamp(a + b)\n\n\n"
        "class Calculator:\n    def total(self, items):\n        return sum(items)\n"
    )
    (tmp_path / "pkg" / "helpers.py").write_text(
        "def clamp(x):\n    return max(0, x)\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calculator.py").write_text(
        "from pkg.calculator import add, Calculator\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "README.md").write_text("# Sample\n")
    # A vendored dir that must be ignored.
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("module.exports = 1\n")
    return tmp_path


def test_detect_language_and_role():
    assert detect_language("a/b/c.py") == "python"
    assert detect_language("x.toml") == "config"
    assert classify_role("tests/test_foo.py", "python") == "test"
    assert classify_role("src/foo_test.py", "python") == "test"
    assert classify_role("pyproject.toml", "config") == "config"
    assert classify_role("docs/guide.md", "markdown") == "doc"
    assert classify_role("pkg/calculator.py", "python") == "source"


def test_index_classifies_and_ignores(sample_repo: Path):
    index = RepoIndex.build(sample_repo)
    paths = {f.path for f in index.files}
    assert "pkg/calculator.py" in paths
    assert "tests/test_calculator.py" in paths
    assert "pyproject.toml" in paths
    # node_modules must be pruned.
    assert not any(p.startswith("node_modules") for p in paths)

    assert {f.path for f in index.source_files} >= {
        "pkg/calculator.py",
        "pkg/helpers.py",
    }
    assert [f.path for f in index.test_files] == ["tests/test_calculator.py"]
    assert "pyproject.toml" in {f.path for f in index.config_files}
    assert "README.md" in {f.path for f in index.doc_files}


def test_symbol_graph_and_imports(sample_repo: Path):
    index = RepoIndex.build(sample_repo)
    graph = SymbolGraph.build(index)
    assert "pkg/calculator.py" in graph.symbols.get("Calculator", set())
    assert "pkg/calculator.py" in graph.symbols.get("add", set())
    assert "pkg/helpers.py" in graph.symbols.get("clamp", set())

    # calculator imports helpers -> helpers is imported by calculator.
    importers = graph.importers_of(index.get("pkg/helpers.py"))
    assert "pkg/calculator.py" in importers


def test_code_map_render(sample_repo: Path):
    cmap = CodeMap.build(sample_repo)
    rendered = cmap.render()
    assert "Repo map" in rendered
    assert "pkg/calculator.py" in rendered
    assert "Calculator" in rendered


def test_dependency_tracer_finds_tests(sample_repo: Path):
    index = RepoIndex.build(sample_repo)
    graph = SymbolGraph.build(index)
    tracer = DependencyTracer(index=index, graph=graph)
    links = tracer.trace_tests("pkg/calculator.py")
    assert links, "expected at least one test link"
    assert links[0].test_path == "tests/test_calculator.py"
    # The name-convention reason should be present for the strongest match.
    assert any("name-convention" in r for r in links[0].reasons)


def test_blast_radius_lists_dependents(sample_repo: Path):
    index = RepoIndex.build(sample_repo)
    graph = SymbolGraph.build(index)
    tracer = DependencyTracer(index=index, graph=graph)
    radius = tracer.blast_radius("pkg/helpers.py")
    assert "pkg/calculator.py" in radius["dependents"]
