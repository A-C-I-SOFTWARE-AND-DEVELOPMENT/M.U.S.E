"""vercel plugin — native Vercel REST access for Hermes.

Registers seven tools under the ``vercel`` toolset:

  read    — vercel_list_projects, vercel_get_deployment,
            vercel_get_preview_url, vercel_tail_logs
  write   — vercel_set_env, vercel_deploy, vercel_cancel_deployment

Three independently-toggled safety gates:

  * ``vercel.enabled``         — the master switch (default False)
  * ``vercel.allow_writes``    — write tools refuse without it (default False)
  * ``vercel.allowed_projects``— when non-empty, the project must be on the list

Writes are additionally gated by the unified decision engine: each is
owner-gated, so the verdict is ``ask`` and the caller must echo the exact
``required_owner_phrase`` to proceed. The ``VERCEL_TOKEN`` lives in env /
``~/.hermes/.env``; it is never returned to the model, never echoed in tool
output, and never sent to the Android cockpit.
"""

from __future__ import annotations

import logging

from plugins.vercel.tools import TOOL_REGISTRATIONS, check_vercel_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register every tool under the vercel toolset.

    Registered unconditionally so ``hermes tools list`` surfaces them even
    when disabled; ``check_fn`` hides them from the model until
    ``vercel.enabled`` is True and ``VERCEL_TOKEN`` is configured.
    """
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="vercel",
            schema=schema,
            handler=handler,
            check_fn=check_vercel_requirements,
            requires_env=["VERCEL_TOKEN"],
            emoji=emoji,
        )
    # Register the out-of-band write executors (cockpit owner-approval / CLI
    # call these on approval; the model-facing tools never do).
    try:
        from plugins.vercel.executor import register_executors

        register_executors()
    except Exception:  # pragma: no cover — out-of-band executors are optional
        logger.debug("vercel executors not registered", exc_info=True)
    logger.debug("vercel registered %d tools", len(TOOL_REGISTRATIONS))
