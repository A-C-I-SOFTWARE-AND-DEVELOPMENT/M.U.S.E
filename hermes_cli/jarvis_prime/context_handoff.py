"""muse — local-first context handoff packet.

Assembles the *structured* context a coding model needs — an architecture
summary, the relevant files, their tests, the GraphRAG nodes, prior
decisions / ledger entries, the recommended model lane, and a verification
plan — instead of dumping the whole repo into the prompt. This is what lets a
coding worker reuse existing implementations and stay inside the verification
gates rather than re-discovering the codebase every turn.

Design contract:

* **Local-first / network-free.** It reads the local GraphRAG cache, the
  task-class router, and the work-packet builder. No provider calls, no
  network, no paid APIs.
* **Degrades gracefully.** If the graph cache isn't built it does NOT walk the
  repo or hit the network unless ``build_if_missing=True`` is passed
  explicitly; it returns honest-empty sections with ``graph_built=False``.
* **Never raises.** Every subsystem call is defensive; a failure becomes a
  note, not an exception.
* **Bounded.** Lists are capped by ``limit`` and the rendered block is clamped
  to ``max(256, token_budget*4)`` chars (~``token_budget`` tokens, with a small
  floor) — the whole point is to *avoid* whole-repo context stuffing.
* **Secret-screened (defence in depth).** The echoed *request* is passed
  through ``secrets_policy.redact`` (best-effort), so a pasted key in the
  prompt never lands in the packet. Graph-derived strings (node titles/refs,
  citation URIs/kinds, the architecture summary) come from already-indexed
  repo/docs content, but they are *also* screened on the way into the packet —
  the index is an assumption, not a guarantee, and this module advertises
  secret-screening. Screening uses the same never-raises ``_redact`` wrapper,
  so it cannot turn a graph hiccup into an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Node-type buckets (compared as ``NodeType.value`` strings so this module
# stays import-light and doesn't pull the graphrag package at import time).
_CODE_TYPES = frozenset(
    {"file", "function", "class", "screen", "module", "route", "api"}
)
_DECISION_TYPES = frozenset({"decision", "task", "worker", "model"})


def _redact(text: str) -> str:
    """Best-effort secret screen on free text (never raises)."""
    try:
        from hermes_cli.secrets_policy import redact

        return redact(text)
    except Exception:  # pragma: no cover - defensive (stripped install)
        return text


def _redact_citation(citation: Any) -> dict[str, Any]:
    """Secret-screen the string fields of a graph citation (never raises).

    Citations are graph-derived dicts (``kind``, ``uri``, …) copied verbatim
    into the packet and rendered by :meth:`ContextHandoff.render`. We screen
    every string value — preserving the dict shape and any non-string fields —
    so a key that somehow reached the index can't ride out via a citation. Non
    dict inputs are returned unchanged so the never-raises contract holds.
    """
    if not isinstance(citation, dict):
        return citation
    return {
        k: (_redact(v) if isinstance(v, str) else v) for k, v in citation.items()
    }


def _is_test(key: str, title: str) -> bool:
    """Path-aware test detection (avoids false positives like ``latest.py``,
    ``attestation``, ``contest``). Matches a ``tests/`` path segment or a
    ``test_``/``_test`` filename boundary."""
    k = (key or "").lower().replace("\\", "/")
    base = k.rsplit("/", 1)[-1]
    return (
        "/tests/" in k
        or k.startswith("tests/")
        or base.startswith("test_")
        or base.endswith("_test.py")
        or base in ("conftest.py",)
    )


def _node_view(node: Any) -> dict[str, Any]:
    """A compact, source-aware view of a graph Node (no whole-node dump).

    Title/ref are graph-derived free text, so they are secret-screened on the
    way out (``_redact`` never raises and is idempotent).
    """
    return {
        "type": node.type.value,
        "title": _redact(node.title),
        "ref": _redact(node.key),
        "source_backed": bool(node.sources),
    }


@dataclass
class ContextHandoff:
    """The structured context packet for a coding handoff."""

    request: str
    repo_root: str
    task_class: str
    architecture_summary: list[str] = field(default_factory=list)
    relevant_files: list[dict] = field(default_factory=list)
    related_tests: list[dict] = field(default_factory=list)
    graph_nodes: list[dict] = field(default_factory=list)
    prior_decisions: list[dict] = field(default_factory=list)
    model_lane: dict = field(default_factory=dict)
    verification_plan: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    second_brain: list[str] = field(default_factory=list)
    graph_built: bool = False
    owner_gated: bool = False
    notes: list[str] = field(default_factory=list)
    token_budget: int = 1024

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "repo_root": self.repo_root,
            "task_class": self.task_class,
            "architecture_summary": list(self.architecture_summary),
            "relevant_files": list(self.relevant_files),
            "related_tests": list(self.related_tests),
            "graph_nodes": list(self.graph_nodes),
            "prior_decisions": list(self.prior_decisions),
            "model_lane": dict(self.model_lane),
            "verification_plan": list(self.verification_plan),
            "citations": list(self.citations),
            "second_brain": list(self.second_brain),
            "graph_built": self.graph_built,
            "owner_gated": self.owner_gated,
            "notes": list(self.notes),
        }

    def render(self) -> str:
        lines: list[str] = [f"# Context handoff — {self.request}", ""]
        lane = self.model_lane or {}
        chosen = lane.get("chosen") or "(no route)"
        lines.append(
            f"**Model lane:** {self.task_class} → {chosen} "
            f"[{lane.get('route_tier', '?')}] · risk {lane.get('risk_class', '?')}"
        )
        if lane.get("fallback_chain"):
            lines.append(
                "  fallbacks: " + ", ".join(str(m) for m in lane["fallback_chain"][1:6])
            )
        if self.owner_gated:
            lines.append("  ⚠ owner-gated: this task needs owner approval to execute.")
        lines.append(f"  graph: {'built' if self.graph_built else 'not built (degraded)'}")
        lines.append("")

        if self.architecture_summary:
            lines.append("## architecture")
            lines.extend(f"  - {s}" for s in self.architecture_summary)
            lines.append("")
        if self.relevant_files:
            lines.append("## relevant files")
            lines.extend(
                f"  - {f['ref']}{'' if f['source_backed'] else ' (unsourced)'}"
                for f in self.relevant_files
            )
            lines.append("")
        if self.related_tests:
            lines.append("## related tests")
            lines.extend(f"  - {t['ref']}" for t in self.related_tests)
            lines.append("")
        if self.prior_decisions:
            lines.append("## prior decisions / ledger")
            lines.extend(
                f"  - [{d['type']}] {d['title']}" for d in self.prior_decisions
            )
            lines.append("")
        if self.verification_plan:
            lines.append("## verification plan")
            lines.extend(f"  - {c}" for c in self.verification_plan)
            lines.append("")
        if self.citations:
            lines.append("## sources")
            lines.extend(
                f"  - {c.get('kind', '?')}: {c.get('uri', '')}"
                for c in self.citations[:20]
            )
        if self.second_brain:
            lines.append("")
            lines.append("## second brain")
            lines.extend(f"  - {s}" for s in self.second_brain)
        if self.notes:
            lines.append("")
            lines.append("## notes")
            lines.extend(f"  - {n}" for n in self.notes)

        text = "\n".join(lines)
        # Final clamp: ~4 chars/token — keep the packet small by construction.
        max_chars = max(256, self.token_budget * 4)
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n… (truncated to token budget)"
        return text


def build_context_handoff(
    request: str,
    *,
    repo_root: str = ".",
    task_class: str = "coding_build",
    store: Optional[Any] = None,
    build_if_missing: bool = False,
    limit: int = 8,
    token_budget: int = 1024,
) -> ContextHandoff:
    """Build a :class:`ContextHandoff` for ``request``.

    Reuses the local GraphRAG (``coding_query`` / ``global_query`` /
    ``related_items``), the task-class router (``route_for_task`` — which
    enforces owner gates and paid opt-in), and the work-packet builder
    (acceptance + verification). Network-free and non-raising.
    """
    handoff = ContextHandoff(
        request=_redact((request or "").strip()),
        repo_root=repo_root,
        task_class=task_class,
        token_budget=token_budget,
    )

    # --- model lane recommendation (respects owner gates / paid opt-in) -----
    try:
        from hermes_cli.jarvis_prime import task_router as tr

        decision = tr.route_for_task(task_class)
        handoff.model_lane = decision.to_dict()
        if decision.output_constraints:
            # Surface the per-task-class output gates so the caller enforces them
            # (deterministically) via output_validator.enforce / the
            # llama_client.completion_with_constraints seam before returning text.
            handoff.notes.append(
                "output constraints — enforce post-generation: "
                + "; ".join(f"[{c.kind}] {c.detail}" for c in decision.output_constraints)
            )
    except ValueError:
        handoff.notes.append(f"unknown task class {task_class!r}; lane recommendation skipped")
    except Exception as exc:  # pragma: no cover - defensive
        handoff.notes.append(f"lane recommendation unavailable: {exc}")

    # --- verification plan + owner-gate flag (work-packet builder) ----------
    try:
        from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet

        packet = build_work_packet(request, repo_root=repo_root)
        handoff.verification_plan = list(packet.verification_plan)
        handoff.owner_gated = bool(packet.owner_gates) or bool(packet.blocked)
    except Exception as exc:  # pragma: no cover - defensive
        handoff.notes.append(f"verification plan unavailable: {exc}")

    # --- GraphRAG context (local-first; degrade if not built) ---------------
    try:
        from hermes_cli.jarvis_prime.graphrag import (
            GraphStore,
            coding_query,
            global_query,
            related_items,
        )

        graph_store = store if store is not None else GraphStore()
        graph = graph_store.load()
        if not graph.nodes and build_if_missing:
            from hermes_cli.jarvis_prime.graphrag import build_and_save

            graph, _ = build_and_save(repo_root, store=graph_store)
        handoff.graph_built = bool(graph.nodes)

        if handoff.graph_built:
            answer = coding_query(graph, request)
            code_nodes = [n for n in answer.nodes if n.type.value in _CODE_TYPES]
            handoff.relevant_files = [
                _node_view(n) for n in code_nodes if not _is_test(n.key, n.title)
            ][:limit]
            handoff.related_tests = [
                _node_view(n) for n in code_nodes if _is_test(n.key, n.title)
            ][:limit]
            handoff.graph_nodes = [_node_view(n) for n in answer.nodes[:limit]]
            handoff.citations = [_redact_citation(c) for c in answer.citations[:20]]

            # Prior decisions: decision/task nodes in the coding answer, plus
            # the decisions linked to the top seed node.
            decisions: list[dict] = [
                _node_view(n)
                for n in answer.nodes
                if n.type.value in _DECISION_TYPES
            ]
            if answer.nodes:
                for item in related_items(graph, answer.nodes[0].id):
                    if item.get("kind") == "decision":
                        decisions.append(
                            {
                                "type": item.get("node_type", "decision"),
                                "title": _redact(item.get("title", "")),
                                "ref": _redact(item.get("ref", "")),
                                "source_backed": bool(item.get("source_backed")),
                            }
                        )
            seen: set[str] = set()
            deduped: list[dict] = []
            for d in decisions:
                if d["ref"] in seen:
                    continue
                seen.add(d["ref"])
                deduped.append(d)
            handoff.prior_decisions = deduped[:limit]

            arch = global_query(graph, request)
            # Community labels + top node titles are graph-derived free text;
            # screen each composed line before it enters the packet.
            handoff.architecture_summary = [
                _redact(
                    f"{c.get('label', '?')[:8]} ({c.get('size', 0)} nodes): "
                    + ", ".join(c.get("top_titles", [])[:4])
                )
                for c in arch.communities[:5]
            ]
        else:
            handoff.notes.append(
                "graph not built — pass --build (or build_if_missing=True) to "
                "index the repo; lane + verification plan are still available."
            )
    except Exception as exc:  # pragma: no cover - defensive
        handoff.notes.append(f"graph context unavailable: {exc}")

    # --- Second Brain (opt-in; augments GraphRAG, never replaces) ------------
    # Only consulted when MUSE_SECOND_BRAIN is set; degrades to a note (never an
    # exception) when the module/backend is absent. Lines are secret-screened on
    # the way in, like every other graph-derived string in this packet.
    try:
        from hermes_cli.jarvis_prime import second_brain_bridge as sbb

        if sbb.enabled():
            if not sbb.is_available():
                handoff.notes.append(
                    "second brain enabled but module not importable; "
                    "using native retrieval"
                )
            else:
                ctx = sbb.retrieve_optional(request, top_k=limit)
                if ctx is not None and (ctx.text or "").strip():
                    handoff.second_brain = [
                        _redact(line)
                        for line in ctx.text.strip().splitlines()
                        if line.strip()
                    ][:limit]
                else:
                    handoff.notes.append(
                        "second brain enabled but returned no context "
                        "(backend unavailable or empty)"
                    )
    except Exception as exc:  # pragma: no cover - defensive
        handoff.notes.append(f"second brain context unavailable: {exc}")

    return handoff
