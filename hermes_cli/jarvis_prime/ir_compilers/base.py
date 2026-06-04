"""Common contract for IR backend compilers.

A compiler turns an :class:`IntentGraph` into a concrete artifact. The repo
backend produces a ``CodingWorkPacket`` (and a gate packet); the automation
backend produces an ``AutomationFlow``. Compilers are pure and IO-free — any
ledger / memory writes happen in ``nl_compile``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from hermes_cli.jarvis_prime.backend_selector import BackendContext, BackendTarget
from hermes_cli.jarvis_prime.intent_graph import IntentGraph


@dataclass(frozen=True)
class CompileResult:
    target: BackendTarget
    artifact: object              # CodingWorkPacket | AutomationFlow
    artifact_dict: dict[str, Any]
    gate_packet: Optional[dict[str, Any]] = None  # repo backend fills this
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.value,
            "artifact": self.artifact_dict,
            "gate_packet": self.gate_packet,
            "notes": list(self.notes),
        }


@runtime_checkable
class IRCompiler(Protocol):
    target: BackendTarget

    def compile(
        self, graph: IntentGraph, context: Optional[BackendContext] = None
    ) -> CompileResult: ...


__all__ = ["CompileResult", "IRCompiler"]
