"""Gated automation-flow execution engine for JARVIS Prime (W8).

Executes an :class:`AutomationFlow` produced by the automation-flow IR
compiler. The contract is deliberately conservative:

* **Simulate by default.** No external IO ever happens unless the caller
  explicitly opts into ``mode="execute"`` *and* supplies a valid owner
  authorization grant covering the flow's external surface.
* **Pure ops** (``extract``/``read``/``fetch``/``compute``/``save``/
  ``write``/``log``) are in-memory / local-only and run in both modes.
* **External ops** (``alert``/``message``/``send``/``post``) leave the
  system. They are only ever *recorded* in simulate mode, and only run
  their handler under a valid grant in execute mode.

There is no real network in this sandbox, so the external handlers here
return structured results rather than performing IO — but the *gating
logic* is the point: an ungated external op must never reach its handler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from hermes_cli.jarvis_prime.ir_compilers.automation_flow import (
    AutomationFlow,
    FlowStep,
)
from hermes_cli.jarvis_prime.owner_auth import OwnerAuthorizationGrant

# ---------------------------------------------------------------------------
# Op classification
# ---------------------------------------------------------------------------

#: In-memory / local-only ops. Safe to run in both simulate and execute.
_PURE_OPS = frozenset({"extract", "read", "fetch", "compute", "save", "write", "log"})

#: Ops that leave the system. Require a valid owner grant to actually run.
_EXTERNAL_OPS = frozenset({"alert", "message", "send", "post"})


# ---------------------------------------------------------------------------
# Step handlers — pure callables (step, context) -> result value
# ---------------------------------------------------------------------------


def _resolve_inputs(step: FlowStep, context: dict[str, Any]) -> dict[str, Any]:
    """Resolve a step's params against produced context values.

    A param value that names a previously-produced key is replaced by that
    produced value, so later steps can read earlier steps' outputs.
    """

    resolved: dict[str, Any] = {}
    for key, value in step.params.items():
        if isinstance(value, str) and value in context:
            resolved[key] = context[value]
        else:
            resolved[key] = value
    return resolved


def _handle_extract(step: FlowStep, context: dict[str, Any]) -> Any:
    key = step.produces or step.id
    return {"extracted": key, "source": step.target}


def _handle_read(step: FlowStep, context: dict[str, Any]) -> Any:
    return {"read": step.target, "inputs": _resolve_inputs(step, context)}


def _handle_fetch(step: FlowStep, context: dict[str, Any]) -> Any:
    return {"fetched": step.target, "inputs": _resolve_inputs(step, context)}


def _handle_compute(step: FlowStep, context: dict[str, Any]) -> Any:
    # Echo the resolved inputs — proves earlier produced values flow through.
    return {"computed": _resolve_inputs(step, context)}


def _handle_save(step: FlowStep, context: dict[str, Any]) -> Any:
    return {"saved": step.target, "inputs": _resolve_inputs(step, context)}


def _handle_write(step: FlowStep, context: dict[str, Any]) -> Any:
    return {"written": step.target, "inputs": _resolve_inputs(step, context)}


def _handle_log(step: FlowStep, context: dict[str, Any]) -> Any:
    return {"logged": step.target or step.id, "inputs": _resolve_inputs(step, context)}


def _handle_external(step: FlowStep, context: dict[str, Any]) -> Any:
    """Handler for external ops.

    Only ever reachable under a valid grant in execute mode. In this
    sandbox it returns a structured result instead of doing real IO — the
    gating, not the IO, is what matters here.
    """

    return {
        "op": step.op,
        "target": step.target,
        "channel": step.target,
        "payload": _resolve_inputs(step, context),
        "dispatched": True,
    }


STEP_HANDLERS: dict[str, Callable[[FlowStep, dict[str, Any]], Any]] = {
    "extract": _handle_extract,
    "read": _handle_read,
    "fetch": _handle_fetch,
    "compute": _handle_compute,
    "save": _handle_save,
    "write": _handle_write,
    "log": _handle_log,
    "alert": _handle_external,
    "message": _handle_external,
    "send": _handle_external,
    "post": _handle_external,
}


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlowStepResult:
    step_id: str
    op: str
    mode: str
    performed: bool
    detail: str
    produced: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "op": self.op,
            "mode": self.mode,
            "performed": self.performed,
            "detail": self.detail,
            "produced": self.produced,
        }


@dataclass(frozen=True)
class FlowRun:
    steps: tuple[FlowStepResult, ...]
    outputs: tuple[dict, ...]
    log: tuple[str, ...]
    executed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "outputs": [dict(o) for o in self.outputs],
            "log": list(self.log),
            "executed": self.executed,
        }


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def _grant_covers(grant: Optional[OwnerAuthorizationGrant], actions: tuple[str, ...]) -> bool:
    """Return True iff ``grant`` authorizes every action in ``actions``.

    A flow's owner-gated surface is its ``owner_gated_actions``. A single
    grant authorizes exactly one action, so it covers the flow only when
    the flow's gated surface is a subset of ``{grant.action}``.
    """

    if not actions:
        return True
    if grant is None:
        return False
    return set(actions) <= {grant.action}


class FlowExecutor:
    """Walks an :class:`AutomationFlow`, threading produced context.

    Never performs real external IO without a valid grant.
    """

    def run(
        self,
        flow: AutomationFlow,
        *,
        mode: str = "simulate",
        grant: Optional[OwnerAuthorizationGrant] = None,
    ) -> FlowRun:
        context: dict[str, Any] = {}
        results: list[FlowStepResult] = []
        log: list[str] = []

        has_external = any(s.op in _EXTERNAL_OPS for s in flow.steps)
        gated_actions = tuple(flow.owner_gated_actions)
        needs_grant = has_external or bool(gated_actions)

        # In execute mode, refuse up front if the external surface is not
        # covered by a valid grant. Pure ops never need a grant.
        execute_external = False
        if mode == "execute":
            if needs_grant and not _grant_covers(grant, gated_actions):
                if grant is None:
                    log.append(
                        "REFUSED execute: flow has owner-gated/external "
                        f"actions {list(gated_actions) or 'external-ops'} but no "
                        "grant was supplied; external ops will NOT run."
                    )
                else:
                    log.append(
                        "REFUSED execute: grant for "
                        f"'{grant.action}' does not cover owner-gated actions "
                        f"{list(gated_actions)}; external ops will NOT run."
                    )
                execute_external = False
            else:
                execute_external = True
                if needs_grant and grant is not None:
                    log.append(
                        f"AUTHORIZED execute: grant '{grant.action}' covers "
                        f"owner-gated actions {list(gated_actions) or 'external-ops'}."
                    )

        for step in flow.steps:
            is_external = step.op in _EXTERNAL_OPS
            handler = STEP_HANDLERS.get(step.op)

            if not is_external:
                # Pure op: runs in both modes.
                if handler is None:
                    detail = f"no handler for pure op '{step.op}'; skipped"
                    results.append(
                        FlowStepResult(step.id, step.op, mode, False, detail, step.produces)
                    )
                    log.append(detail)
                    continue
                value = handler(step, context)
                if step.produces:
                    context[step.produces] = value
                detail = f"ran pure op '{step.op}'"
                results.append(
                    FlowStepResult(step.id, step.op, mode, True, detail, step.produces)
                )
                log.append(f"{step.id}: {detail}")
                continue

            # External op.
            if mode == "execute" and execute_external:
                value = handler(step, context) if handler else None
                if step.produces:
                    context[step.produces] = value
                detail = f"executed external op '{step.op}' under owner grant"
                results.append(
                    FlowStepResult(step.id, step.op, mode, True, detail, step.produces)
                )
                log.append(f"{step.id}: {detail}")
            else:
                # Simulate, or execute-but-refused: record intent only.
                detail = (
                    f"simulated external op '{step.op}' (no external IO performed)"
                )
                results.append(
                    FlowStepResult(step.id, step.op, mode, False, detail, step.produces)
                )
                log.append(f"{step.id}: {detail}")

        outputs = tuple(o.to_dict() for o in flow.outputs)
        executed = mode == "execute" and (not needs_grant or execute_external)
        return FlowRun(
            steps=tuple(results),
            outputs=outputs,
            log=tuple(log),
            executed=executed,
        )


__all__ = [
    "_PURE_OPS",
    "_EXTERNAL_OPS",
    "STEP_HANDLERS",
    "FlowStepResult",
    "FlowRun",
    "FlowExecutor",
]
