"""Operator CLI for the ``prime`` plugin.

Wires four top-level commands, each backed by a module in this package:

  ``hermes navigate``    — deterministic repo navigation (:mod:`plugins.prime.navigation`)
  ``hermes graph``       — the GraphRAG knowledge graph (:mod:`plugins.prime.graphrag`)
  ``hermes memory-tree`` — the Memory Tree store (:mod:`plugins.prime.memory_tree`)
  ``hermes research``    — the Research Vault (:mod:`plugins.prime.research_vault`)

Everything here is local and deterministic: no network calls, no model calls.
Each command takes ``--json`` for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _report_diagnostics(label: str, diagnostics: list[str]) -> None:
    """Surface skipped-record diagnostics from a store load.

    The JSONL stores tolerate a corrupt line rather than refusing to start,
    but a silently dropped record is data loss the operator never sees. Print
    them on stderr so stdout stays machine-readable.
    """

    for diag in diagnostics:
        print(f"warning: {label}: {diag}", file=sys.stderr)


def _emit(args: argparse.Namespace, payload: Any, text: str) -> int:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(text)
    return 0


def _usage(parser_name: str, actions: str) -> int:
    print(f"Usage: hermes {parser_name} {{{actions}}}  (see --help)")
    return 2


# ---------------------------------------------------------------------------
# hermes navigate
# ---------------------------------------------------------------------------

def register_navigate_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo", default=".", help="Repository root to index (default: cwd)"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    subs = parser.add_subparsers(dest="navigate_action")

    loc = subs.add_parser("localize", help="Rank the files an issue most likely lives in")
    loc.add_argument("issue", nargs="+", help="Issue text / bug report / task")
    loc.add_argument("--limit", type=int, default=8)
    loc.add_argument("--no-git", action="store_true", help="Skip the git-recency signal")

    sites = subs.add_parser("sites", help="Rank concrete edit sites, with tests to run")
    sites.add_argument("issue", nargs="+")
    sites.add_argument("--limit", type=int, default=5)
    sites.add_argument("--no-git", action="store_true")

    pkt = subs.add_parser("packet", help="Emit a worker edit packet for an issue")
    pkt.add_argument("issue", nargs="+")
    pkt.add_argument("--limit", type=int, default=5)
    pkt.add_argument("--no-git", action="store_true")

    tests = subs.add_parser("tests", help="Which tests cover a source file")
    tests.add_argument("path", help="Repo-relative source path")
    tests.add_argument("--limit", type=int, default=5)

    dep = subs.add_parser("deps", help="Blast radius: what depends on a source file")
    dep.add_argument("path", help="Repo-relative source path")

    mp = subs.add_parser("map", help="Render a repo map (files grouped by role)")
    mp.add_argument("--max-files", type=int, default=60)


def navigate_command(args: argparse.Namespace) -> int:
    action = getattr(args, "navigate_action", None)
    if not action:
        return _usage("navigate", "localize|sites|packet|tests|deps|map")

    from plugins.prime.navigation import CodeMap, Navigator

    if action == "map":
        cmap = CodeMap.build(args.repo)
        return _emit(args, cmap.to_dict(), cmap.render(max_files=args.max_files))

    nav = Navigator.for_repo(args.repo, use_git=not getattr(args, "no_git", False))

    if action == "tests":
        links = nav.trace_tests(args.path, limit=args.limit)
        payload = [t.to_dict() for t in links]
        text = "\n".join(
            f"{t.score:6.2f}  {t.test_path}   ({', '.join(t.reasons)})" for t in links
        ) or "(no covering tests found)"
        return _emit(args, payload, text)

    if action == "deps":
        radius = nav.tracer.blast_radius(args.path)
        listed = "\n".join(f"  {d}" for d in radius.get("dependents", [])) or "  (none)"
        return _emit(args, radius, f"dependents of {args.path}:\n{listed}")

    issue = " ".join(args.issue)

    if action == "localize":
        hits = nav.localize(issue, limit=args.limit)
        payload = [h.to_dict() for h in hits]
        text = "\n".join(
            f"{h.score:6.2f}  {h.path}   [{', '.join(h.matched_terms[:6])}]"
            for h in hits
        ) or "(no candidates)"
        return _emit(args, payload, text)

    result = nav.navigate(issue, limit=args.limit)

    if action == "packet":
        packet = result.worker_packet(max_sites=args.limit)
        return _emit(args, packet, json.dumps(packet, indent=2, default=str))

    sites = result.edit_sites
    payload = [s.to_dict() for s in sites]
    lines: list[str] = []
    for s in sites:
        lines.append(f"{s.rank}. {s.path}  (confidence {s.confidence:.2f})")
        lines.append(f"     why: {s.rationale}")
        if s.suggested_tests:
            lines.append(f"     verify: {', '.join(s.suggested_tests)}")
    return _emit(args, payload, "\n".join(lines) or "(no edit sites)")


# ---------------------------------------------------------------------------
# hermes graph
# ---------------------------------------------------------------------------

def register_graph_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    subs = parser.add_subparsers(dest="graph_action")

    b = subs.add_parser("build", help="Build (or rebuild) the knowledge graph")
    b.add_argument("--repo", default=".", help="Repository root (default: cwd)")
    b.add_argument(
        "--indexers",
        default="",
        help="Comma-separated subset of: code,docs,evidence,memory",
    )

    q = subs.add_parser("query", help="Query the graph")
    q.add_argument("question", nargs="+")
    q.add_argument("--mode", choices=["coding", "local", "global"], default="coding")
    q.add_argument("--limit", type=int, default=8)

    r = subs.add_parser("related", help="Neighbours of one node, bucketed")
    r.add_argument("key", help="Node id, repo path, or memory id")
    r.add_argument("--limit", type=int, default=10)

    subs.add_parser("stats", help="Node/edge counts by type, and the cache path")


def graph_command(args: argparse.Namespace) -> int:
    action = getattr(args, "graph_action", None)
    if not action:
        return _usage("graph", "build|query|related|stats")

    from plugins.prime.graphrag import (
        ALL_INDEXERS,
        GraphStore,
        build_and_save,
        coding_query,
        find_entity_node,
        global_query,
        load_or_build,
        local_query,
        related_items,
    )

    store = GraphStore()

    if action == "build":
        selected = (
            [s.strip() for s in args.indexers.split(",") if s.strip()]
            if args.indexers
            else list(ALL_INDEXERS)
        )
        graph, path = build_and_save(args.repo, indexers=selected, store=store)
        payload = {
            "path": str(path),
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "indexers": selected,
        }
        return _emit(
            args,
            payload,
            f"built {len(graph.nodes)} node(s) / {len(graph.edges)} edge(s) "
            f"from [{', '.join(selected)}] -> {path}",
        )

    graph = load_or_build(".", store=store)
    _report_diagnostics("knowledge graph", store.load_diagnostics)

    if action == "stats":
        stats = graph.stats()
        payload = {"path": str(store.path), **stats}
        lines = [f"graph: {store.path}", f"nodes: {stats['nodes']}"]
        lines += [f"  {k:<12} {v}" for k, v in stats["by_node_type"].items()]
        lines.append(f"edges: {stats['edges']}")
        lines += [f"  {k:<12} {v}" for k, v in stats["by_edge_type"].items()]
        return _emit(args, payload, "\n".join(lines))

    if action == "related":
        node_id = find_entity_node(graph, key=args.key)
        if node_id is None:
            print(f"no graph node matches {args.key!r}. Try `hermes graph build`.")
            return 1
        items = related_items(graph, node_id, limit=args.limit)
        lines: list[str] = []
        current = ""
        for it in items:
            if it["kind"] != current:
                current = it["kind"]
                lines.append(f"## {current}")
            mark = "" if it["source_backed"] else "  (no source)"
            lines.append(
                f"  - [{it['relation']}] {it['title']} — {it['ref']}{mark}"
            )
        return _emit(args, items, "\n".join(lines) or "(nothing related)")

    question = " ".join(args.question)
    if args.mode == "global":
        answer = global_query(graph, question, max_communities=max(1, args.limit // 2))
    elif args.mode == "local":
        answer = local_query(graph, question, limit=args.limit)
    else:
        answer = coding_query(graph, question, limit=args.limit)
    return _emit(args, answer.to_dict(), answer.render())


# ---------------------------------------------------------------------------
# hermes memory-tree
# ---------------------------------------------------------------------------

def _source_trust_choices() -> list[str]:
    from plugins.prime.memory_tree import SourceTrust

    return [t.value for t in SourceTrust]


def register_memory_tree_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    subs = parser.add_subparsers(dest="memory_tree_action")

    w = subs.add_parser("write", help="Write a memory node (policy-checked)")
    w.add_argument("text", help="The fact to remember")
    w.add_argument("--title", required=True)
    w.add_argument("--namespace", default="prime/general")
    w.add_argument("--summary", default="")
    w.add_argument("--source-uri", default=None, help="Where this came from")
    w.add_argument(
        "--source-trust",
        default="unverified",
        choices=_source_trust_choices(),
        help="How much the source is trusted (weights retrieval ranking)",
    )
    w.add_argument("--confidence", type=float, default=0.5)
    w.add_argument(
        "--freshness-due",
        default=None,
        metavar="ISO8601",
        help=(
            "When this fact should be re-checked (e.g. 2027-01-01T00:00:00Z). "
            "Past that instant it is penalised in retrieval ranking."
        ),
    )
    w.add_argument(
        "--layer",
        default="session",
        choices=["working", "session", "durable"],
        help=(
            "Storage layer. 'durable' applies the strict write gate "
            "(provenance or --approve, plus the confidence floor) and runs "
            "contradiction detection against existing durable facts."
        ),
    )
    w.add_argument(
        "--approve",
        action="store_true",
        help="Record an explicit operator approval (satisfies the durable gate)",
    )
    w.add_argument("--tags", default="", help="Comma-separated")
    w.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the write policy and report, without storing",
    )

    s = subs.add_parser("search", help="Rank stored memory against a query")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--namespace", action="append", default=None)
    s.add_argument("--include-contested", action="store_true")

    subs.add_parser("outline", help="Tree outline of every stored node")

    ctx = subs.add_parser(
        "context", help="Compile a token-bounded context packet (TokenJuice)"
    )
    ctx.add_argument("mission", nargs="+", help="What the context is for")
    ctx.add_argument("--budget", type=int, default=2000, help="Token budget")
    ctx.add_argument("--namespace", action="append", default=None)
    ctx.add_argument(
        "--with-research",
        action="store_true",
        help="Also pack matching Research Vault artifacts",
    )
    ctx.add_argument("--include-contested", action="store_true")

    subs.add_parser("contradictions", help="List open contradiction reports")

    r = subs.add_parser("resolve", help="Resolve a contradiction report")
    r.add_argument("report_id", help="Report id from `memory-tree contradictions`")
    r.add_argument("winner_id", help="Node id that wins; the other is superseded")
    r.add_argument("--note", default="", help="Why the winner was chosen")

    e = subs.add_parser("export", help="Export the tree as markdown or audit cards")
    e.add_argument("--namespace", default=None)
    e.add_argument("--audit-cards", action="store_true")


def memory_tree_command(args: argparse.Namespace) -> int:
    action = getattr(args, "memory_tree_action", None)
    if not action:
        return _usage(
            "memory-tree", "write|search|outline|context|contradictions|resolve|export"
        )

    from plugins.prime.memory_tree import MemoryTreeStore

    store = MemoryTreeStore.load()
    _report_diagnostics("memory tree", store.load_diagnostics)

    if action == "write":
        from plugins.prime.memory_tree import MemoryLayer, SourceTrust

        result = store.write(
            args.text,
            namespace=args.namespace,
            title=args.title,
            layer=MemoryLayer(args.layer),
            summary=args.summary,
            source_uri=args.source_uri,
            source_trust=SourceTrust(args.source_trust),
            confidence=args.confidence,
            freshness_due=args.freshness_due,
            operator_approved=args.approve,
            tags=[t.strip() for t in args.tags.split(",") if t.strip()],
            dry_run=args.dry_run,
        )
        lines = [("ok: " if result.ok else "rejected: ") + args.title]
        lines += [f"  - {r}" for r in result.reasons]
        if result.contradiction is not None:
            c = result.contradiction
            other = (
                c.node_a_id
                if result.node is not None and c.node_b_id == result.node.id
                else c.node_b_id
            )
            lines.append(f"  ! contradicts {other} (report {c.id})")
        if result.node is not None:
            lines.append(f"  id: {result.node.id}")
        return _emit(args, result.to_dict(), "\n".join(lines))

    if action == "search":
        hits = store.search(
            " ".join(args.query),
            namespaces=args.namespace,
            include_contested=args.include_contested,
            limit=args.limit,
        )
        payload = [h.to_dict() for h in hits]
        text = "\n".join(
            f"{h.score:6.2f}  [{h.node.namespace}] {h.node.title}" for h in hits
        ) or "(no matches)"
        return _emit(args, payload, text)

    if action == "outline":
        text = store.outline() or "(memory tree is empty)"
        return _emit(args, {"outline": text}, text)

    if action == "contradictions":
        reports = store.open_contradictions()
        payload = [r.to_dict() for r in reports]
        text = "\n".join(
            f"{r.id}  {r.node_a_id} <> {r.node_b_id}  ({r.reason})" for r in reports
        ) or "(no open contradictions)"
        return _emit(args, payload, text)

    if action == "resolve":
        try:
            report = store.resolve_contradiction(
                args.report_id, args.winner_id, args.note
            )
        except (KeyError, ValueError) as exc:
            print(f"cannot resolve: {exc}")
            return 1
        loser = (
            report.node_b_id
            if args.winner_id == report.node_a_id
            else report.node_a_id
        )
        return _emit(
            args,
            report.to_dict(),
            f"resolved {report.id}: {args.winner_id} wins, {loser} superseded",
        )

    if action == "export":
        if args.audit_cards:
            cards = store.export_audit_cards(args.namespace)
            return _emit(args, cards, json.dumps(cards, indent=2, default=str))
        text = store.export_markdown(args.namespace)
        return _emit(args, {"markdown": text}, text)

    # context — TokenJuice
    from plugins.prime.tokenjuice import TokenJuiceCompiler

    mission = " ".join(args.mission)
    artifacts: list = []
    if args.with_research:
        from plugins.prime.research_vault import ResearchVault

        vault = ResearchVault.load()
        _report_diagnostics("research vault", vault.load_diagnostics)
        artifacts = vault.search(mission, limit=10)
    compiled = TokenJuiceCompiler().compile(
        mission,
        args.budget,
        memory_store=store,
        memory_namespaces=args.namespace,
        research_artifacts=artifacts,
        include_contested=args.include_contested,
    )
    return _emit(args, compiled.to_dict(), compiled.render())


# ---------------------------------------------------------------------------
# hermes research
# ---------------------------------------------------------------------------

def _source_type_choices() -> list[str]:
    from plugins.prime.research_vault import SourceType

    return [t.value for t in SourceType]


def register_research_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    subs = parser.add_subparsers(dest="research_action")

    a = subs.add_parser("add", help="File an evidence artifact in the vault")
    a.add_argument("title")
    a.add_argument("source_uri", help="URL or repo path the claim comes from")
    a.add_argument(
        "--excerpt", default="", help="Verbatim excerpt (summaries derive from this)"
    )
    a.add_argument("--summary", default="")
    a.add_argument(
        "--strength",
        default="moderate",
        choices=["primary", "strong", "moderate", "weak", "vendor_reported"],
    )
    a.add_argument(
        "--source-type",
        default="manual",
        choices=_source_type_choices(),
        help="What kind of source this is (filters `research list`)",
    )
    a.add_argument("--tags", default="", help="Comma-separated")
    a.add_argument("--license-notes", default="")

    s = subs.add_parser("search", help="Search stored evidence")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", type=int, default=10)

    ls = subs.add_parser("list", help="List every stored artifact")
    ls.add_argument("--source-type", default=None, choices=_source_type_choices())

    e = subs.add_parser("export", help="Export the vault as markdown or audit cards")
    e.add_argument("--audit-cards", action="store_true")


def research_command(args: argparse.Namespace) -> int:
    action = getattr(args, "research_action", None)
    if not action:
        return _usage("research", "add|search|list|export")

    from plugins.prime.research_vault import (
        EvidenceStrength,
        ResearchVault,
        SourceType,
    )

    vault = ResearchVault.load()
    _report_diagnostics("research vault", vault.load_diagnostics)

    if action == "add":
        art = vault.add(
            args.title,
            args.source_uri,
            source_type=SourceType(args.source_type),
            evidence_strength=EvidenceStrength(args.strength),
            excerpt=args.excerpt,
            summary=args.summary,
            tags=[t.strip() for t in args.tags.split(",") if t.strip()],
            license_notes=args.license_notes,
        )
        return _emit(
            args,
            art.to_dict(),
            f"filed {art.id}: {art.title} "
            f"({art.evidence_strength.value}) — {art.source_uri}",
        )

    if action == "search":
        arts = vault.search(" ".join(args.query), limit=args.limit)
    elif action == "list":
        st = SourceType(args.source_type) if args.source_type else None
        arts = vault.entries(source_type=st)
    else:
        if args.audit_cards:
            cards = vault.export_audit_cards()
            return _emit(args, cards, json.dumps(cards, indent=2, default=str))
        text = vault.export_markdown()
        return _emit(args, {"markdown": text}, text)

    payload = [a.to_dict() for a in arts]
    text = "\n".join(
        f"{a.id}  [{a.evidence_strength.value:<15}] {a.title}  — {a.source_uri}"
        for a in arts
    ) or "(vault is empty)"
    return _emit(args, payload, text)
