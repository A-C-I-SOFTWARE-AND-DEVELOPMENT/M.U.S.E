"""codeintel plugin — code-review intelligence for Hermes.

Registers three tools under the ``codeintel`` toolset:

  dependency_audit  — OSV.dev known-vulnerability scan (read-only, no key)
  dependency_info   — deps.dev licenses/versions/advisories (read-only, no key)
  run_code          — Piston sandboxed execution; its ``check_fn`` keeps it
                      hidden unless BOTH codeintel.enabled and
                      codeintel.allow_code_execution are true

Per-tool ``check_fn``/``requires_env`` so the execution tool only surfaces
when explicitly allowed. Hosts are pinned and the OSV/Piston POST calls go
through the shared :mod:`tools.http_client` helper.
"""

from __future__ import annotations

import logging

from plugins.codeintel.tools import TOOL_REGISTRATIONS

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    for name, schema, handler, emoji, check_fn, requires_env in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="codeintel",
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            emoji=emoji,
        )
    logger.debug("codeintel plugin registered %d tools", len(TOOL_REGISTRATIONS))
