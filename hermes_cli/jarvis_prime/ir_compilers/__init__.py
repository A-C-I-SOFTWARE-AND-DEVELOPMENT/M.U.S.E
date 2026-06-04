"""IR backend compilers + a small registry keyed by ``BackendTarget``."""

from __future__ import annotations

from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.ir_compilers.automation_flow import AutomationFlowCompiler
from hermes_cli.jarvis_prime.ir_compilers.base import CompileResult, IRCompiler
from hermes_cli.jarvis_prime.ir_compilers.repo_work_packet import RepoWorkPacketCompiler

COMPILERS: dict[BackendTarget, IRCompiler] = {
    BackendTarget.REPO_WORK_PACKET: RepoWorkPacketCompiler(),
    BackendTarget.AUTOMATION_FLOW: AutomationFlowCompiler(),
}


def get_compiler(target: BackendTarget) -> IRCompiler:
    try:
        return COMPILERS[target]
    except KeyError:  # pragma: no cover - guarded by selector
        raise ValueError(f"no Phase-1 compiler for backend target {target!r}")


__all__ = [
    "COMPILERS",
    "get_compiler",
    "CompileResult",
    "IRCompiler",
    "RepoWorkPacketCompiler",
    "AutomationFlowCompiler",
]
