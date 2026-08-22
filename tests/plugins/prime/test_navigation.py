"""prime navigation — repo index, symbol graph, localizer, tracer, ranker.

Every test runs against the real fixture repository written to ``tmp_path``
(see ``conftest.py``): the walk, the ``ast`` parse and the ranking are all
exercised for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.prime.navigation import (
    CodeMap,
    DependencyTracer,
    EditSiteRanker,
    IssueLocalizer,
    Navigator,
    RepoIndex,
    SymbolGraph,
    classify_role,
    detect_language,
)
from plugins.prime.navigation.issue_localizer import WEIGHTS, _git_recency

ISSUE = "load_timeout returns the wrong timeout in timeout_config.py"


# ── classification (pure functions) ──────────────────────────────────────────


@pytest.mark.parametrize(
    "path,expected",
    [
        ("pkg/client.py", "python"),
        ("web/app.js", "javascript"),
        ("web/app.tsx", "typescript"),
        ("docs/architecture.md", "markdown"),
        ("pyproject.toml", "config"),
        ("bin/thing.unknownext", "other"),
    ],
)
def test_detect_language(path, expected):
    assert detect_language(path) == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("pkg/client.py", "source"),
        ("tests/test_client.py", "test"),
        ("pkg/client_test.py", "test"),
        ("web/app.spec.js", "test"),
        ("web/__tests__/app.js", "test"),
        ("pyproject.toml", "config"),
        ("plugin.yaml", "config"),
        ("docs/architecture.md", "doc"),
        ("README.md", "doc"),
        ("assets/logo.png", "other"),
    ],
)
def test_classify_role(path, expected):
    assert classify_role(path, detect_language(path)) == expected


def test_config_and_test_beat_plain_source():
    # A .py file under tests/ is a test, not source; a .toml is config even
    # though its directory is a source package.
    assert classify_role("pkg/tests/helpers.py", "python") == "test"
    assert classify_role("pkg/settings.toml", "config") == "config"


# ── RepoIndex ────────────────────────────────────────────────────────────────


def test_index_classifies_every_fixture_file(index):
    by_path = {f.path: f for f in index.files}
    assert by_path["pkg/timeout_config.py"].role == "source"
    assert by_path["tests/test_timeout_config.py"].role == "test"
    assert by_path["docs/architecture.md"].role == "doc"
    assert by_path["pyproject.toml"].role == "config"
    assert by_path["web/app.js"].language == "javascript"


def test_index_prunes_ignored_directories(index):
    paths = {f.path for f in index.files}
    assert not any(p.startswith("node_modules/") for p in paths)
    assert not any(p.startswith("__pycache__/") for p in paths)


def test_index_is_sorted_and_summarised(index):
    assert [f.path for f in index.files] == sorted(f.path for f in index.files)
    summary = index.summary()
    assert summary["total_files"] == len(index.files)
    assert summary["by_role"]["source"] == len(index.source_files)
    assert summary["by_role"]["test"] == len(index.test_files) == 1
    assert summary["by_language"]["python"] == 5


def test_index_get_and_views(index):
    f = index.get("pkg/client.py")
    assert f is not None and f.stem == "client" and f.name == "client.py"
    assert f.lines > 0
    assert index.get("nope/missing.py") is None
    assert {d.path for d in index.doc_files} == {"README.md", "docs/architecture.md"}


def test_index_max_files_caps_the_walk(repo):
    capped = RepoIndex.build(repo, max_files=3)
    assert len(capped.files) == 3


def test_index_extra_ignore_dirs(repo):
    trimmed = RepoIndex.build(repo, ignore_dirs={"web"})
    assert not any(f.path.startswith("web/") for f in trimmed.files)


# ── SymbolGraph ──────────────────────────────────────────────────────────────


def test_symbol_graph_parses_python_defs(symbols):
    assert symbols.file_symbols["pkg/timeout_config.py"] == {
        "TimeoutConfig",
        "__init__",
        "load_timeout",
    }
    assert symbols.symbols["load_timeout"] == {"pkg/timeout_config.py"}
    assert symbols.symbols["fetch"] == {"pkg/client.py"}


def test_symbol_graph_parses_js_defs_and_imports(symbols):
    assert symbols.file_symbols["web/app.js"] == {"APP_NAME", "renderApp"}
    assert symbols.imports["web/app.js"] == {"./helper"}


def test_symbol_graph_records_python_imports(symbols):
    assert symbols.imports["pkg/client.py"] == {
        "pkg.timeout_config",
        "pkg.timeout_config.load_timeout",
    }


def test_importers_of_finds_both_dependents(symbols):
    assert symbols.importers_of("pkg/timeout_config.py") == {
        "pkg/client.py",
        "tests/test_timeout_config.py",
    }
    # A file never imports itself, and an unimported module has no importers.
    assert "pkg/unrelated.py" not in symbols.importers_of("pkg/unrelated.py")
    assert symbols.importers_of("pkg/unrelated.py") == set()


def test_symbol_graph_skips_unparseable_python(tmp_path):
    (tmp_path / "broken.py").write_text("def oops(\n", encoding="utf-8")
    graph = SymbolGraph.build(RepoIndex.build(tmp_path))
    assert graph.file_symbols["broken.py"] == set()


# ── IssueLocalizer ───────────────────────────────────────────────────────────


def test_localizer_ranks_the_named_file_first(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    hits = loc.localize(ISSUE)
    assert hits[0].path == "pkg/timeout_config.py"
    assert hits[0].score > hits[1].score


def test_localizer_exposes_a_per_signal_breakdown(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    top = loc.localize(ISSUE)[0]
    assert set(top.signals) == set(WEIGHTS)
    # The issue quotes the filename AND a symbol the file defines.
    assert top.signals["path"] > 0
    assert top.signals["symbol"] > 0
    assert top.score == pytest.approx(
        sum(WEIGHTS[k] * v for k, v in top.signals.items())
    )
    assert "load_timeout" in top.matched_terms


def test_an_explicit_path_mention_outweighs_more_lexical_evidence(index, symbols):
    """The weight table's central claim, pinned.

    ``WEIGHTS`` says an explicitly-named path dominates. This issue names
    ``pkg/client.py`` once but carries three terms and a symbol that all point
    at ``pkg/timeout_config.py``; only the path weight puts client.py on top.
    Asserting ``score == sum(WEIGHTS[k] * v)`` cannot catch a weight change —
    it recomputes from the same table.
    """

    loc = IssueLocalizer.build(index, symbols, use_git=False)
    hits = loc.localize(
        "the timeout timeout_config load_timeout regression shows up in pkg/client.py"
    )
    assert hits[0].path == "pkg/client.py"
    assert hits[1].path == "pkg/timeout_config.py"
    # ...and it wins *despite* less lexical and symbol evidence.
    assert hits[0].signals["lexical"] < hits[1].signals["lexical"]
    assert hits[0].signals["symbol"] < hits[1].signals["symbol"]
    assert hits[0].signals["path"] > hits[1].signals["path"]


def test_localizer_finds_a_file_by_symbol_alone(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    hits = loc.localize("the fetch helper swallows errors")
    assert hits[0].path == "pkg/client.py"
    assert hits[0].signals["symbol"] > 0


def test_localizer_drops_zero_signal_files_and_honours_limit(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    hits = loc.localize(ISSUE)
    assert "pkg/unrelated.py" not in {h.path for h in hits}
    assert len(loc.localize("timeout", limit=1)) == 1


def test_localizer_returns_nothing_for_an_unmatchable_issue(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    assert loc.localize("zzzqqq nonexistent subsystem") == []


def test_localizer_is_deterministic(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    first = [(h.path, h.score) for h in loc.localize(ISSUE)]
    second = [(h.path, h.score) for h in loc.localize(ISSUE)]
    assert first == second


def test_git_recency_is_empty_outside_a_git_repo(repo):
    assert _git_recency(Path(repo)) == {}


def test_localizer_to_dict_rounds(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    d = loc.localize(ISSUE)[0].to_dict()
    assert d["path"] == "pkg/timeout_config.py"
    assert set(d) == {"path", "score", "signals", "matched_terms"}


# ── DependencyTracer ─────────────────────────────────────────────────────────


def test_trace_tests_finds_the_mirrored_test_with_reasons(index, symbols):
    tracer = DependencyTracer(index=index, graph=symbols)
    links = tracer.trace_tests("pkg/timeout_config.py")
    assert links[0].test_path == "tests/test_timeout_config.py"
    assert "name-convention" in links[0].reasons
    assert "import-edge" in links[0].reasons
    assert any(r.startswith("symbol-ref:") for r in links[0].reasons)


def test_trace_tests_returns_nothing_for_an_untested_file(index, symbols):
    tracer = DependencyTracer(index=index, graph=symbols)
    assert tracer.trace_tests("pkg/unrelated.py") == []


def test_dependents_and_blast_radius(index, symbols):
    tracer = DependencyTracer(index=index, graph=symbols)
    assert tracer.dependents("pkg/timeout_config.py") == {
        "pkg/client.py",
        "tests/test_timeout_config.py",
    }
    radius = tracer.blast_radius("pkg/timeout_config.py")
    assert radius["dependent_count"] == 2
    assert radius["dependents"] == [
        "pkg/client.py",
        "tests/test_timeout_config.py",
    ]
    assert radius["tests"][0]["test_path"] == "tests/test_timeout_config.py"


def test_tracer_caches_test_file_tokens(index, symbols):
    tracer = DependencyTracer(index=index, graph=symbols)
    tracer.trace_tests("pkg/timeout_config.py")
    assert "tests/test_timeout_config.py" in tracer._test_token_cache


# ── EditSiteRanker ───────────────────────────────────────────────────────────


def test_edit_sites_carry_symbols_tests_and_blast_radius(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    tracer = DependencyTracer(index=index, graph=symbols)
    ranker = EditSiteRanker(localizer=loc, graph=symbols, tracer=tracer)
    sites = ranker.from_localizations(loc.localize(ISSUE))

    top = sites[0]
    assert top.path == "pkg/timeout_config.py"
    assert top.rank == 1
    assert top.confidence == 1.0  # normalised against the best score
    assert "load_timeout" in top.symbols
    assert top.suggested_tests == ("tests/test_timeout_config.py",)
    assert top.dependents == ("pkg/client.py", "tests/test_timeout_config.py")
    # Ranks are 1-based and confidence is monotonically non-increasing.
    assert [s.rank for s in sites] == list(range(1, len(sites) + 1))
    assert all(
        a.confidence >= b.confidence for a, b in zip(sites, sites[1:])
    )


def test_edit_site_rationale_names_the_firing_signals(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    tracer = DependencyTracer(index=index, graph=symbols)
    ranker = EditSiteRanker(localizer=loc, graph=symbols, tracer=tracer)
    top = ranker.from_localizations(loc.localize(ISSUE))[0]
    assert "path explicitly referenced" in top.rationale
    assert "defines a matching symbol" in top.rationale


def test_edit_site_ranker_handles_no_candidates(index, symbols):
    loc = IssueLocalizer.build(index, symbols, use_git=False)
    tracer = DependencyTracer(index=index, graph=symbols)
    ranker = EditSiteRanker(localizer=loc, graph=symbols, tracer=tracer)
    assert ranker.from_localizations([]) == []


# ── Navigator ────────────────────────────────────────────────────────────────


def test_navigator_wires_the_whole_pipeline(navigator):
    result = navigator.navigate(ISSUE, limit=3)
    assert result.issue == ISSUE
    assert result.localizations[0].path == "pkg/timeout_config.py"
    assert result.edit_sites[0].path == "pkg/timeout_config.py"
    assert result.created_at  # ISO timestamp


def test_worker_packet_is_self_contained(navigator):
    packet = navigator.navigate(ISSUE, limit=3).worker_packet(max_sites=2)
    assert packet["objective"] == ISSUE
    assert packet["candidate_files"][0] == "pkg/timeout_config.py"
    assert len(packet["edit_sites"]) <= 2
    assert packet["verify_with"] == ["tests/test_timeout_config.py"]
    assert "no LLM" in packet["navigation_method"]


def test_worker_packet_deduplicates_tests(navigator):
    # Both candidate files point at the same test file; it must appear once.
    packet = navigator.navigate(ISSUE, limit=5).worker_packet()
    assert len(packet["verify_with"]) == len(set(packet["verify_with"]))


def test_navigator_localize_and_trace_tests_delegate(navigator):
    assert navigator.localize(ISSUE, limit=1)[0].path == "pkg/timeout_config.py"
    links = navigator.trace_tests("pkg/timeout_config.py", limit=1)
    assert links[0].test_path == "tests/test_timeout_config.py"


def test_navigator_for_repo_without_git_has_no_recency_signal(repo):
    nav = Navigator.for_repo(repo, use_git=False)
    assert nav.localizer.git_recent == {}


# ── CodeMap ──────────────────────────────────────────────────────────────────


def test_code_map_renders_files_with_their_symbols(repo):
    rendered = CodeMap.build(repo).render()
    assert "pkg/timeout_config.py: TimeoutConfig, __init__, load_timeout" in rendered
    assert "source=5" in rendered
    # Docs/tests/config are not source files and are not listed individually.
    assert "docs/architecture.md" not in rendered


def test_code_map_truncates_to_the_file_budget(repo):
    rendered = CodeMap.build(repo).render(max_files=2)
    assert "more source files" in rendered


def test_code_map_caps_symbols_per_file(repo):
    rendered = CodeMap.build(repo).render(max_symbols_per_file=1)
    assert "pkg/timeout_config.py: TimeoutConfig, +2" in rendered


def test_code_map_to_dict(repo):
    d = CodeMap.build(repo).to_dict()
    assert d["summary"]["by_role"]["source"] == 5
    assert d["symbol_count"] > 0
    assert {f["path"] for f in d["files"]} >= {"pkg/client.py", "README.md"}
