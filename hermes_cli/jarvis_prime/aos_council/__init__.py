"""AOS Enterprise Council — executable runtime.

The council shipped as a *catalog* (markdown agents + a machine-readable
``operating-registry/registry.json``) but had no runtime that actually routed a
request to council members. This package is that runtime: it loads the real
registry and dispatches a request to the always-on ``active_council`` plus the
``domain_specialists`` whose ``when_to_use`` matches — producing a structured,
owner-gate-aware council session.

It is deterministic and offline (registry-driven routing, no model calls); the
per-member persona files (``path``) let a caller optionally run each engaged
member through the model layer afterwards. It does **not** invent a sixth
orchestration primitive — it is a router over the registry, like the task router
over worker profiles.
"""

from __future__ import annotations

from .dispatcher import (
    CouncilMember,
    CouncilSession,
    DispatchPlan,
    Task,
    TaskQueue,
    dispatch,
    load_registry,
    registry_path,
    roster,
    unified_dispatch,
)
from .executor import (
    CouncilDeliberation,
    MemberResult,
    default_runner,
    execute,
)

__all__ = [
    "CouncilDeliberation",
    "CouncilMember",
    "CouncilSession",
    "DispatchPlan",
    "MemberResult",
    "Task",
    "TaskQueue",
    "default_runner",
    "dispatch",
    "execute",
    "load_registry",
    "registry_path",
    "roster",
    "unified_dispatch",
]
