"""prime CLI lanes — registration plus a smoke test per subcommand.

Each lane is driven the way ``hermes_cli.main`` drives it: the plugin's
registered ``setup_fn`` builds the argparse tree, the real argv is parsed, and
the registered ``handler_fn`` runs against a HERMES_HOME-isolated store (the
suite conftest points HERMES_HOME at a per-test tmpdir). Nothing is stubbed;
the assertions are on the process exit code and the text/JSON it prints.
"""

from __future__ import annotations

import argparse
import json

import pytest

import plugins.prime as plugin_pkg
from plugins.prime.cli import (
    graph_command,
    memory_tree_command,
    navigate_command,
    register_graph_cli,
    register_memory_tree_cli,
    register_navigate_cli,
    register_research_cli,
    research_command,
)

LANES = {
    "navigate": (register_navigate_cli, navigate_command),
    "graph": (register_graph_cli, graph_command),
    "memory-tree": (register_memory_tree_cli, memory_tree_command),
    "research": (register_research_cli, research_command),
}


def run(capsys, lane: str, *argv: str) -> tuple[int, str]:
    """Parse ``argv`` with the lane's real parser, run its handler, return
    ``(exit_code, stdout)``."""

    setup_fn, handler_fn = LANES[lane]
    parser = argparse.ArgumentParser(prog=f"hermes {lane}")
    setup_fn(parser)
    code = handler_fn(parser.parse_args(list(argv)))
    return code, capsys.readouterr().out


def run_json(capsys, lane: str, *argv: str):
    code, out = run(capsys, lane, *argv)
    assert code == 0, out
    return json.loads(out)


# ── registration ─────────────────────────────────────────────────────────────


class _Ctx:
    def __init__(self):
        self.commands = []
        self.tools = []

    def register_cli_command(self, **kw):
        self.commands.append(kw)

    def register_tool(self, **kw):
        self.tools.append(kw)


def test_register_wires_four_commands_and_one_tool():
    ctx = _Ctx()
    plugin_pkg.register(ctx)
    assert [c["name"] for c in ctx.commands] == [
        "navigate",
        "graph",
        "memory-tree",
        "research",
    ]
    assert all(c["help"] and c["description"] for c in ctx.commands)
    assert [t["name"] for t in ctx.tools] == ["graph_query"]
    assert ctx.tools[0]["toolset"] == "prime"
    assert ctx.tools[0]["check_fn"]() is True


def test_registered_callables_match_the_module_exports():
    ctx = _Ctx()
    plugin_pkg.register(ctx)
    by_name = {c["name"]: c for c in ctx.commands}
    for name, (setup_fn, handler_fn) in LANES.items():
        assert by_name[name]["setup_fn"] is setup_fn
        assert by_name[name]["handler_fn"] is handler_fn


def test_every_lane_prints_usage_and_exits_2_without_a_subcommand(capsys):
    for lane in LANES:
        code, out = run(capsys, lane)
        assert code == 2
        assert out.startswith(f"Usage: hermes {lane} {{")


# ── hermes navigate ──────────────────────────────────────────────────────────


def test_navigate_localize(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "localize", "--no-git",
        "fix load_timeout in timeout_config.py",
    )
    assert code == 0
    assert out.splitlines()[0].strip().endswith(
        "pkg/timeout_config.py   [config, load_timeout, timeout]"
    )


def test_navigate_localize_json(capsys, repo):
    payload = run_json(
        capsys, "navigate", "--repo", str(repo), "--json", "localize", "--no-git",
        "--limit", "1", "fix load_timeout in timeout_config.py",
    )
    assert len(payload) == 1
    assert payload[0]["path"] == "pkg/timeout_config.py"
    assert payload[0]["signals"]["path"] > 0


def test_navigate_localize_reports_no_candidates(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "localize", "--no-git",
        "zzzqqq nonexistent subsystem",
    )
    assert code == 0
    assert out.strip() == "(no candidates)"


def test_navigate_sites(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "sites", "--no-git", "--limit", "1",
        "fix load_timeout in timeout_config.py",
    )
    assert code == 0
    assert "1. pkg/timeout_config.py  (confidence 1.00)" in out
    assert "why: path explicitly referenced" in out
    assert "verify: tests/test_timeout_config.py" in out


def test_navigate_packet(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "packet", "--no-git", "--limit", "2",
        "fix load_timeout in timeout_config.py",
    )
    assert code == 0
    packet = json.loads(out)
    assert packet["candidate_files"][0] == "pkg/timeout_config.py"
    assert packet["verify_with"] == ["tests/test_timeout_config.py"]


def test_navigate_tests(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "tests", "pkg/timeout_config.py"
    )
    assert code == 0
    assert "tests/test_timeout_config.py" in out
    assert "name-convention" in out


def test_navigate_tests_reports_nothing_found(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "tests", "pkg/unrelated.py"
    )
    assert code == 0
    assert out.strip() == "(no covering tests found)"


def test_navigate_deps(capsys, repo):
    code, out = run(
        capsys, "navigate", "--repo", str(repo), "deps", "pkg/timeout_config.py"
    )
    assert code == 0
    assert "dependents of pkg/timeout_config.py:" in out
    assert "  pkg/client.py" in out


def test_navigate_deps_json(capsys, repo):
    payload = run_json(
        capsys, "navigate", "--repo", str(repo), "--json", "deps", "pkg/unrelated.py"
    )
    assert payload["dependents"] == []
    assert payload["dependent_count"] == 0


def test_navigate_map(capsys, repo):
    code, out = run(capsys, "navigate", "--repo", str(repo), "map", "--max-files", "10")
    assert code == 0
    assert "# Repo map:" in out
    assert "pkg/timeout_config.py: TimeoutConfig" in out


# ── hermes graph ─────────────────────────────────────────────────────────────


def test_graph_build_then_stats_then_query(capsys, repo):
    code, out = run(capsys, "graph", "build", "--repo", str(repo), "--indexers", "code,docs")
    assert code == 0
    assert "node(s)" in out and "edge(s)" in out and "[code, docs]" in out

    code, out = run(capsys, "graph", "stats")
    assert code == 0
    assert out.startswith("graph: ")
    assert "file" in out and "tests" in out

    code, out = run(capsys, "graph", "query", "--mode", "coding", "timeout_config")
    assert code == 0
    assert "# GraphRAG (coding) — timeout_config" in out
    assert "pkg/timeout_config.py" in out


def test_graph_build_json_reports_the_cache_path(capsys, repo):
    payload = run_json(
        capsys, "graph", "--json", "build", "--repo", str(repo), "--indexers", "code"
    )
    assert payload["indexers"] == ["code"]
    assert payload["nodes"] > 0
    assert payload["path"].endswith("graph.json")


def test_graph_query_local_and_global_modes(capsys, repo):
    run(capsys, "graph", "build", "--repo", str(repo))
    for mode in ("local", "global"):
        code, out = run(capsys, "graph", "query", "--mode", mode, "timeout")
        assert code == 0
        assert f"# GraphRAG ({mode})" in out


def test_graph_related(capsys, repo):
    run(capsys, "graph", "build", "--repo", str(repo), "--indexers", "code,docs")
    code, out = run(capsys, "graph", "related", "pkg/timeout_config.py")
    assert code == 0
    assert "## file" in out
    assert "pkg/client.py" in out


def test_graph_related_unknown_key_exits_1(capsys, repo):
    run(capsys, "graph", "build", "--repo", str(repo), "--indexers", "code")
    code, out = run(capsys, "graph", "related", "no/such/file.py")
    assert code == 1
    assert "no graph node matches" in out


# ── hermes memory-tree ───────────────────────────────────────────────────────


def write_memory(capsys, *extra):
    return run(
        capsys, "memory-tree", "write", "The cache lives under HERMES_HOME",
        "--title", "cache location", "--namespace", "prime/test", *extra,
    )


def test_memory_tree_write_and_search(capsys):
    code, out = write_memory(capsys)
    assert code == 0
    assert out.startswith("ok: cache location")
    assert "  id: " in out

    code, out = run(capsys, "memory-tree", "search", "cache")
    assert code == 0
    assert "[prime/test] cache location" in out


def test_memory_tree_search_reports_no_matches(capsys):
    code, out = run(capsys, "memory-tree", "search", "zzzqqq")
    assert code == 0
    assert out.strip() == "(no matches)"


def test_memory_tree_write_rejection_is_reported(capsys):
    code, out = run(
        capsys, "memory-tree", "write", "the answer", "--title", "t",
        "--layer", "durable", "--confidence", "0.9",
    )
    assert code == 0  # the CLI reports the refusal rather than crashing
    assert out.startswith("rejected: t")
    assert "provenance or operator approval" in out


def test_memory_tree_dry_run_does_not_store(capsys):
    code, out = write_memory(capsys, "--dry-run")
    assert code == 0 and out.startswith("ok:")
    _, out = run(capsys, "memory-tree", "outline")
    assert out.strip() == "(memory tree is empty)"


def test_memory_tree_durable_write_and_contradiction_lane(capsys):
    """The end-to-end contradiction path: the CLI must pass ``--layer`` through
    for ``_detect_contradiction`` (durable-only) to be reachable at all."""

    code, out = write_memory(
        capsys, "--layer", "durable", "--source-uri", "docs/a.md", "--confidence", "0.9"
    )
    assert code == 0 and out.startswith("ok:")

    code, out = run(
        capsys, "memory-tree", "write", "The cache lives in /var/cache",
        "--title", "cache location", "--namespace", "prime/test",
        "--layer", "durable", "--source-uri", "docs/b.md", "--confidence", "0.9",
    )
    assert code == 0
    assert "! contradicts" in out

    code, out = run(capsys, "memory-tree", "contradictions")
    assert code == 0
    assert "conflicting high-confidence facts" in out
    report_id, node_a, _, node_b, *_ = out.split()

    code, out = run(capsys, "memory-tree", "resolve", report_id, node_b, "--note", "newer")
    assert code == 0
    assert f"resolved {report_id}: {node_b} wins, {node_a} superseded" in out

    code, out = run(capsys, "memory-tree", "contradictions")
    assert out.strip() == "(no open contradictions)"


def test_memory_tree_resolve_rejects_a_bad_report(capsys):
    code, out = run(capsys, "memory-tree", "resolve", "nope", "alsonope")
    assert code == 1
    assert out.startswith("cannot resolve:")


def test_memory_tree_source_trust_is_recorded(capsys):
    payload = run_json(
        capsys, "memory-tree", "--json", "write", "A cited fact",
        "--title", "t", "--source-uri", "docs/a.md", "--source-trust", "primary",
    )
    assert payload["node"]["source_trust"] == "primary"


def test_memory_tree_outline_and_exports(capsys):
    write_memory(capsys, "--layer", "durable", "--source-uri", "docs/a.md",
                 "--confidence", "0.9")

    code, out = run(capsys, "memory-tree", "outline")
    assert code == 0
    assert "- prime/test" in out
    assert "cache location (durable)" in out

    code, out = run(capsys, "memory-tree", "export")
    assert code == 0
    assert "# Memory Tree" in out
    assert "source: docs/a.md" in out

    code, out = run(capsys, "memory-tree", "export", "--audit-cards")
    assert code == 0
    assert json.loads(out)[0]["sources"] == ["docs/a.md"]


def test_memory_tree_context_compiles_a_packet(capsys):
    write_memory(capsys)
    code, out = run(
        capsys, "memory-tree", "context", "--budget", "400", "where is the cache"
    )
    assert code == 0
    assert "# Context — where is the cache" in out
    assert "### [mission] mission" in out
    assert "### [memory] prime/test: cache location" in out
    assert "/400 tokens" in out


def test_memory_tree_context_with_research(capsys):
    write_memory(capsys)
    run(capsys, "research", "add", "Cache paper", "https://example.invalid/p",
        "--excerpt", "Caches under HERMES_HOME are disposable.")
    code, out = run(
        capsys, "memory-tree", "context", "--budget", "800", "--with-research",
        "cache HERMES_HOME",
    )
    assert code == 0
    assert "### [research] Cache paper" in out
    assert "sources: https://example.invalid/p" in out


# ── hermes research ──────────────────────────────────────────────────────────


def test_research_add_search_and_list(capsys):
    code, out = run(
        capsys, "research", "add", "GraphRAG paper", "https://example.invalid/p",
        "--excerpt", "Graphs improve retrieval.", "--strength", "primary",
        "--source-type", "paper", "--tags", "graphs,retrieval",
    )
    assert code == 0
    assert out.startswith("filed ")
    assert "(primary) — https://example.invalid/p" in out

    code, out = run(capsys, "research", "search", "graphs")
    assert code == 0
    assert "[primary" in out and "GraphRAG paper" in out

    code, out = run(capsys, "research", "list", "--source-type", "paper")
    assert code == 0
    assert "GraphRAG paper" in out

    code, out = run(capsys, "research", "list", "--source-type", "blog")
    assert out.strip() == "(vault is empty)"


def test_research_add_json_keeps_the_excerpt_verbatim(capsys):
    payload = run_json(
        capsys, "research", "--json", "add", "Paper", "https://example.invalid/p",
        "--excerpt", "An exact quotation.",
    )
    assert payload["excerpt"] == "An exact quotation."
    assert payload["summary"] == "An exact quotation."
    assert payload["checksum"]


def test_research_exports(capsys):
    run(capsys, "research", "add", "Paper", "https://example.invalid/p",
        "--excerpt", "A claim.")
    code, out = run(capsys, "research", "export")
    assert code == 0
    assert "# Research Vault" in out and "## Paper" in out

    code, out = run(capsys, "research", "export", "--audit-cards")
    assert code == 0
    assert json.loads(out)[0]["claim"] == "A claim."


def test_memory_tree_freshness_due_is_recorded_and_penalises_ranking(capsys):
    """``--freshness-due`` is the only producer for the staleness penalty.

    Without it ``MemoryNode.freshness_due`` is never set by any live caller,
    so ``_is_stale`` and its ranking penalty are unreachable in production.
    """

    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    run(capsys, "memory-tree", "write", "the cache tuning note is current",
        "--title", "fresh note", "--freshness-due", future)
    run(capsys, "memory-tree", "write", "the cache tuning note is expired",
        "--title", "stale note", "--freshness-due", past)

    payload = run_json(capsys, "memory-tree", "--json", "search", "cache tuning note")
    assert [h["node"]["title"] for h in payload] == ["fresh note", "stale note"]
    assert payload[0]["node"]["freshness_due"] == future
    assert payload[0]["score"] > payload[1]["score"]


def test_a_corrupt_store_line_is_reported_on_stderr(capsys, tmp_path, monkeypatch):
    """A skipped record must not be silent.

    The JSONL stores tolerate a bad line rather than refusing to start, but
    ``load_diagnostics`` had no reader anywhere outside the tests — so in
    production a dropped record left no trace at all.
    """

    import os

    home = tmp_path / "home"
    (home / "prime").mkdir(parents=True)
    (home / "prime" / "memory_tree.jsonl").write_bytes(
        b'{"type": "node", "id": "a", "namespace": "ns", "title": "ok"}\n'
        b"{not json at all}\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    assert os.environ["HERMES_HOME"] == str(home)

    parser = argparse.ArgumentParser(prog="hermes memory-tree")
    register_memory_tree_cli(parser)
    code = memory_tree_command(parser.parse_args(["outline"]))
    captured = capsys.readouterr()
    out, err = captured.out, captured.err
    assert code == 0
    assert "ok" in out  # the good record still loaded
    assert "warning: memory tree: line 2" in err


# ── the graph_query agent tool ───────────────────────────────────────────────


def test_graph_query_tool_answers_from_the_cache(capsys, repo, monkeypatch):
    from plugins.prime.tools import GRAPH_QUERY_SCHEMA, _handler, graph_query

    monkeypatch.chdir(repo)
    run(capsys, "graph", "build", "--repo", str(repo))
    assert GRAPH_QUERY_SCHEMA["parameters"]["required"] == ["question"]
    out = graph_query("timeout_config", mode="coding", limit=4)
    assert "pkg/timeout_config.py" in out
    assert _handler({"question": "timeout_config"}) == graph_query("timeout_config")


def test_graph_query_tool_never_builds_the_graph_itself(repo, monkeypatch):
    """An agent tool call must not block on a full repo index.

    Building parses every python file in the tree (order of a minute on a
    large checkout), so with no cache present the tool has to decline and
    name the command that creates one — never build on demand.
    """

    from plugins.prime import graphrag
    from plugins.prime.tools import graph_query

    monkeypatch.chdir(repo)

    def _must_not_run(*a, **kw):  # pragma: no cover - fails the test if hit
        raise AssertionError("graph_query built the graph")

    monkeypatch.setattr(graphrag.builder, "build_graph", _must_not_run)
    monkeypatch.setattr(graphrag, "build_graph", _must_not_run, raising=False)

    out = graph_query("timeout_config")
    assert "no knowledge graph cached" in out
    assert "hermes graph build" in out


def test_graph_query_tool_requires_a_question():
    from plugins.prime.tools import graph_query

    assert graph_query("") == "graph_query: provide a 'question'."


@pytest.mark.parametrize("mode", ["local", "global", "coding"])
def test_graph_query_tool_supports_every_mode(capsys, repo, monkeypatch, mode):
    from plugins.prime.tools import graph_query

    monkeypatch.chdir(repo)
    run(capsys, "graph", "build", "--repo", str(repo))
    assert f"# GraphRAG ({mode})" in graph_query("timeout", mode=mode)
