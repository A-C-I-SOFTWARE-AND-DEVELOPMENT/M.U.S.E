"""IR backend compilers + a small registry keyed by ``BackendTarget``."""

from __future__ import annotations

from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.ir_compilers.automation_flow import AutomationFlowCompiler
from hermes_cli.jarvis_prime.ir_compilers.base import CompileResult, IRCompiler
from hermes_cli.jarvis_prime.ir_compilers.python_module import PythonModuleCompiler
from hermes_cli.jarvis_prime.ir_compilers.repo_work_packet import RepoWorkPacketCompiler
from hermes_cli.jarvis_prime.ir_compilers.rust_module import RustModuleCompiler
from hermes_cli.jarvis_prime.ir_compilers.sql_query import SqlQueryCompiler

COMPILERS: dict[BackendTarget, IRCompiler] = {
    BackendTarget.REPO_WORK_PACKET: RepoWorkPacketCompiler(),
    BackendTarget.AUTOMATION_FLOW: AutomationFlowCompiler(),
    BackendTarget.PYTHON: PythonModuleCompiler(),
    BackendTarget.SQL: SqlQueryCompiler(),
    BackendTarget.RUST: RustModuleCompiler(),
}


def get_compiler(target: BackendTarget) -> IRCompiler:
    try:
        return COMPILERS[target]
    except KeyError:  # pragma: no cover - guarded by selector
        raise ValueError(f"no compiler registered for backend target {target!r}")


__all__ = [
    "COMPILERS",
    "get_compiler",
    "CompileResult",
    "IRCompiler",
    "RepoWorkPacketCompiler",
    "AutomationFlowCompiler",
    "PythonModuleCompiler",
    "SqlQueryCompiler",
    "RustModuleCompiler",
]
