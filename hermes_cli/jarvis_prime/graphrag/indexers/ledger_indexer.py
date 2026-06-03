"""Job/ledger indexer — bring orchestration history into the graph.

Two authoritative ledgers feed this indexer:

* the **orchestrator job ledger** (``orchestrator.get_ledger()``) — TASK nodes
  per job, the WORKER/MODEL that ran them, and the FILE nodes a
  ``navigation_decision`` pointed the worker at (TASK ``depends_on`` FILE). This
  is what lets a coding query surface *"a prior task already touched this file"*
  so we avoid duplicate implementations.
* the **decision ledger** (``decision_ledger.list_ledgers()``) — DECISION nodes
  per recorded decision, CITES-linked to any repo files they reference.

Read-only and best-effort: a missing/empty ledger yields no nodes, never an
error (mirrors ``orchestrator.navigate_job``'s non-blocking contract).
"""

from __future__ import annotations

import re
from typing import Optional

from hermes_cli.jarvis_prime.graphrag.graph import EdgeType, KnowledgeGraph, NodeType, node_id

# Path-like token (shared shape with the docs indexer): a ``/`` plus extension.
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\-]*[A-Za-z0-9_\-]+/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+")


def _ref(job_id: str) -> dict:
    return {"uri": job_id, "kind": "job_ledger"}


def index_ledger(
    graph: KnowledgeGraph, *, ledger: Optional[dict] = None, repo_root=None
) -> KnowledgeGraph:
    _index_job_ledger(graph, ledger)
    _index_decision_ledger(graph)
    return graph


def _index_job_ledger(graph: KnowledgeGraph, ledger: Optional[dict]) -> None:
    if ledger is None:
        try:
            from hermes_cli import orchestrator as orch

            ledger = orch.get_ledger() or {}
        except Exception:
            return
        get_job = _safe_get_job()
    else:
        get_job = lambda _jid: None  # noqa: E731 - injected ledger, no job lookup

    for job_id, entries in (ledger or {}).items():
        if not isinstance(entries, list):
            continue
        job = get_job(job_id)
        title = (getattr(job, "prompt", "") or job_id)[:80] if job else job_id
        task = graph.add_node(
            NodeType.TASK,
            job_id,
            title=title,
            attrs={"status": getattr(job, "status", "") if job else ""},
            sources=[_ref(job_id)],
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("kind", "")
            worker_id = entry.get("worker_id")
            model = entry.get("model") or entry.get("model_id")
            if worker_id:
                worker = graph.add_node(
                    NodeType.WORKER, worker_id, title=worker_id, sources=[_ref(job_id)]
                )
                graph.add_edge(worker.id, task.id, EdgeType.OWNS, sources=[_ref(job_id)])
            if model:
                model_node = graph.add_node(
                    NodeType.MODEL, str(model), title=str(model), sources=[_ref(job_id)]
                )
                graph.add_edge(
                    task.id, model_node.id, EdgeType.DEPENDS_ON, sources=[_ref(job_id)]
                )
            if kind == "navigation_decision":
                _link_ranked_files(graph, task.id, entry, job_id)
            if kind in {"worker_blocked", "worker_error"}:
                task.attrs["blocked"] = True


def _link_ranked_files(graph: KnowledgeGraph, task_id: str, entry: dict, job_id: str) -> None:
    for rf in entry.get("ranked_files", []) or []:
        path = rf.get("path") if isinstance(rf, dict) else None
        if not path:
            continue
        file_id = node_id(NodeType.FILE, path)
        if file_id in graph.nodes:
            graph.add_edge(
                task_id, file_id, EdgeType.DEPENDS_ON,
                attrs={"rank": rf.get("rank")}, sources=[_ref(job_id)],
            )
    for test in entry.get("verify_with", []) or []:
        test_id = node_id(NodeType.FILE, test)
        if test_id in graph.nodes:
            graph.add_edge(
                task_id, test_id, EdgeType.VERIFIES, sources=[_ref(job_id)]
            )


def _index_decision_ledger(graph: KnowledgeGraph) -> None:
    try:
        from hermes_cli import decision_ledger as dl
    except Exception:
        return
    try:
        paths = dl.list_ledgers()
    except Exception:
        return
    # Known repo file/document keys for CITES matching (set membership, O(1)).
    known_keys = {
        n.key
        for n in graph.nodes.values()
        if n.type in (NodeType.FILE, NodeType.DOCUMENT) and len(n.key) >= 6
    }
    for path in paths:
        try:
            led = dl.read_ledger(path)
            text = led.to_markdown()
        except Exception:
            continue
        key = str(path)
        ref = {"uri": key, "kind": "decision_ledger"}
        title = _first_heading(text) or key
        # The cockpit audit screen identifies a record by ``ledger.slug`` (or
        # the path stem) — store that as ``audit_id`` so an evidence/audit id
        # resolves to this decision node (the graph key itself is the full
        # path, which the audit id never matches directly).
        from pathlib import Path as _Path

        audit_id = str(getattr(led, "slug", "") or "").strip() or _Path(key).stem
        dec = graph.add_node(
            NodeType.DECISION,
            f"ledger:{key}",
            title=title,
            attrs={"audit_id": audit_id, "path": key},
            sources=[ref],
        )
        cited = 0
        seen: set[str] = set()
        for token in _PATH_TOKEN_RE.findall(text):
            fk = token.lstrip("./")
            if fk in seen or fk not in known_keys:
                continue
            seen.add(fk)
            for nt in (NodeType.FILE, NodeType.DOCUMENT):
                fid = node_id(nt, fk)
                if fid in graph.nodes:
                    if graph.add_edge(dec.id, fid, EdgeType.CITES, sources=[ref]):
                        cited += 1
                    break
            if cited >= 25:
                break


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip()[:80]
    return ""


def _safe_get_job():
    try:
        from hermes_cli import orchestrator as orch

        return orch.get_job
    except Exception:
        return lambda _jid: None
