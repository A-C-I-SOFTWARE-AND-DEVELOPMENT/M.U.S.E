"""Thin orchestration façade for the NL programming compiler.

``compile_request`` is the single entry point the CLI calls. It wires the
pure modules together — parse -> select -> compile -> optional gate/validate —
and owns the *only* side effects (optional ledger + memory writes). The
frontend, selector and compilers stay IO-free and deterministic; this module
is where disk is allowed.

Mirrors how ``proposal_executor`` wraps ``build_work_packet``: keep the CLI
handler thin and the policy here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from hermes_cli.jarvis_prime import semantic_frontend as sf
from hermes_cli.jarvis_prime.backend_selector import (
    BackendContext,
    BackendDecision,
    BackendTarget,
    HINT_ALIASES,
    select_backend,
)
from hermes_cli.jarvis_prime.gates import GateSummary, run_gate_summary
from hermes_cli.jarvis_prime.intent_graph import IntentNodeKind
from hermes_cli.jarvis_prime.ir_compilers import get_compiler
from hermes_cli.jarvis_prime.ir_compilers.base import CompileResult


@dataclass(frozen=True)
class CompileRequestResult:
    parse: sf.ParseResult
    backend: Optional[BackendDecision]
    compile_result: Optional[CompileResult]
    gate_summary: Optional[GateSummary]
    needs_clarification: bool

    def clarifying_questions(self) -> tuple[str, ...]:
        return self.parse.clarifying_questions()

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse": self.parse.to_dict(),
            "backend": self.backend.to_dict() if self.backend else None,
            "compile": self.compile_result.to_dict() if self.compile_result else None,
            "gates": self.gate_summary.to_dict() if self.gate_summary else None,
            "needs_clarification": self.needs_clarification,
        }


def _resolve_hint(backend: str) -> Optional[BackendTarget]:
    if not backend or backend == "auto":
        return None
    return HINT_ALIASES.get(backend)


def compile_request(
    prompt: str,
    *,
    backend: str = "auto",
    branch_prefix: str = "jarvis",
    repo_root: str = ".",
    gate_check: bool = False,
    job_id: Optional[str] = None,
    learn: bool = False,
    context: Optional[dict] = None,
) -> CompileRequestResult:
    parse = sf.parse(prompt, context)

    # Ambiguity is terminal: never compile a guess.
    if parse.needs_clarification:
        return CompileRequestResult(
            parse=parse, backend=None, compile_result=None,
            gate_summary=None, needs_clarification=True,
        )

    hint = _resolve_hint(backend)
    decision = select_backend(
        parse.graph, BackendContext(forced_target=hint, repo_root=repo_root)
    )

    if decision.selected is None:  # blocked
        _maybe_append_ledger(job_id, parse, decision, None)
        return CompileRequestResult(
            parse=parse, backend=decision, compile_result=None,
            gate_summary=None, needs_clarification=False,
        )

    compiler = get_compiler(decision.selected)
    result = compiler.compile(
        parse.graph,
        BackendContext(repo_root=repo_root, branch_prefix=branch_prefix),
    )

    gate_summary: Optional[GateSummary] = None
    if gate_check and result.gate_packet is not None:
        gate_summary = run_gate_summary(result.gate_packet)

    _maybe_append_ledger(job_id, parse, decision, result)
    if learn:
        _capture_vocabulary(parse, decision)

    return CompileRequestResult(
        parse=parse, backend=decision, compile_result=result,
        gate_summary=gate_summary, needs_clarification=False,
    )


# ---------------------------------------------------------------------------
# Side effects (the only ones in the pipeline)
# ---------------------------------------------------------------------------


def ledger_entry(
    parse: sf.ParseResult,
    decision: BackendDecision,
    result: Optional[CompileResult],
) -> dict[str, Any]:
    """Build the audit record for a compile (caller decides when to append)."""

    artifact_id = None
    if result is not None:
        d = result.artifact_dict
        artifact_id = d.get("packet_id") or d.get("flow_id")
    return {
        "kind": "nl-compile",
        "graph_id": parse.graph.graph_id,
        "selected_backend": decision.selected.value if decision.selected else None,
        "backend_decision": decision.ledger_entry,
        "confidence": parse.confidence,
        "ambiguities": len(parse.ambiguities),
        "blocked": decision.blocked,
        "artifact_id": artifact_id,
    }


def _maybe_append_ledger(
    job_id: Optional[str],
    parse: sf.ParseResult,
    decision: BackendDecision,
    result: Optional[CompileResult],
) -> None:
    if not job_id:
        return  # default compile is side-effect-free
    from hermes_cli import orchestrator_ledger

    orchestrator_ledger.append(job_id, ledger_entry(parse, decision, result))


def _capture_vocabulary(parse: sf.ParseResult, decision: BackendDecision) -> None:
    """Offer parsed vocabulary to the Memory Tree as a PROPOSED node only.

    Never durable, never silent — surfaced via the existing owner-review path.
    ``write`` never raises; rejections are inspected via ``result.ok``.
    """

    try:
        from hermes_cli.jarvis_prime.memory_tree import (
            ApprovalState,
            MemoryLayer,
            MemoryNamespace,
            MemoryTreeStore,
            SourceTrust,
        )
    except Exception:  # pragma: no cover - defensive
        return

    g = parse.graph
    entities = sorted({n.label for n in g.nodes_of(IntentNodeKind.ENTITY)})
    operations = sorted({n.label for n in g.nodes_of(IntentNodeKind.OPERATION)})
    if not entities and not operations:
        return

    text = (
        f"NL-compile vocabulary (graph {g.graph_id[:10]}): "
        f"entities={entities}; operations={operations}; "
        f"backend={decision.selected.value if decision.selected else None}"
    )
    store = MemoryTreeStore.load()
    store.write(
        text,
        namespace=MemoryNamespace.CODE_PRACTICE.value,
        title=f"nl-compile vocab {g.graph_id[:10]}",
        layer=MemoryLayer.SESSION,
        source_uri=f"nl-compile:{g.graph_id}",
        source_trust=SourceTrust.UNVERIFIED,
        approval_state=ApprovalState.PROPOSED,
        tags=("nl-compile", "vocabulary"),
        persist=True,
    )


__all__ = ["CompileRequestResult", "compile_request", "ledger_entry"]
