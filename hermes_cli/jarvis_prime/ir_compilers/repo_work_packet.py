"""Repo-work-packet backend.

Compiles an :class:`IntentGraph` into a ``CodingWorkPacket`` by **reusing**
``natural_language_coder.build_work_packet`` as the spine — so intent, risk,
gates, workers, rollback and evidence stay identical to the established path.
The graph only *enriches* file scope; it never re-derives risk/gate logic.

``CodingWorkPacket`` is frozen and ``build_work_packet`` auto-derives fields,
so enrichment is done only through the builder's existing ``allowed_files`` /
``forbidden_files`` parameters (unioned with the safe default so we never
*narrow* below it). Extra graph-derived criteria surface as diagnostics.
"""

from __future__ import annotations

from typing import Optional

from hermes_cli.jarvis_prime.backend_selector import BackendContext, BackendTarget
from hermes_cli.jarvis_prime.intent_graph import IntentGraph, IntentNodeKind
from hermes_cli.jarvis_prime.ir_compilers.base import CompileResult
from hermes_cli.jarvis_prime.natural_language_coder import (
    _allowed_files_for,
    build_work_packet,
)
from hermes_cli.jarvis_prime.nlp_retrieval import ground_objective


def _repo_path_like(label: str) -> bool:
    return "/" in label or label.endswith(".py") or "**" in label


class RepoWorkPacketCompiler:
    target = BackendTarget.REPO_WORK_PACKET

    def compile(
        self, graph: IntentGraph, context: Optional[BackendContext] = None
    ) -> CompileResult:
        context = context or BackendContext()

        # Graph-derived file scope: any node whose label looks like a repo path.
        extra_files = sorted({
            n.label for n in graph.nodes
            if _repo_path_like(n.label)
        })

        # W4 retrieval grounding: deterministically enrich file scope with
        # candidate files from the Navigator. Degrades gracefully (ok=False)
        # and never narrows below the safe default.
        grounding = ground_objective(graph.raw_text, context.repo_root)
        ground_files = (
            tuple(grounding.candidate_files)
            if grounding.ok and grounding.candidate_files
            else ()
        )

        # Union with the safe per-intent default so we never narrow below it.
        if extra_files or ground_files:
            allowed = tuple(dict.fromkeys(
                (*_allowed_files_for(graph.intent), *extra_files, *ground_files)
            ))
        else:
            allowed = None  # let build_work_packet use its default

        packet = build_work_packet(
            graph.raw_text,
            repo_root=context.repo_root,
            branch_prefix=context.branch_prefix,
            allowed_files=allowed,
        )

        # Graph-derived constraints/quality targets have no builder parameter;
        # surface them as diagnostics rather than mutating the frozen packet.
        notes: list[str] = []
        for c in graph.nodes_of(IntentNodeKind.CONSTRAINT):
            notes.append(f"constraint: {c.label}")
        for q in graph.nodes_of(IntentNodeKind.QUALITY_TARGET):
            notes.append(f"quality target: {q.label}")
        if extra_files:
            notes.append("allowed_files enriched from graph: " + ", ".join(extra_files))
        for v in grounding.verify_with:
            notes.append(f"verify: {v}")
        notes.extend(grounding.notes)

        return CompileResult(
            target=self.target,
            artifact=packet,
            artifact_dict=packet.to_dict(),
            gate_packet=packet.to_gate_packet(),
            notes=tuple(notes),
        )


__all__ = ["RepoWorkPacketCompiler"]
