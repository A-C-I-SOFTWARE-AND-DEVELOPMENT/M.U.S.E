"""supabase plugin — native Supabase PostgREST access for Hermes.

Registers four tools under the ``supabase`` toolset:

  read    — supabase_query, supabase_list_tables
  write   — supabase_execute_sql, supabase_apply_migration

Three independently-toggled safety gates:

  * ``supabase.enabled``            — the master switch (default False)
  * ``supabase.allow_writes``       — write tools refuse without it (default False)
  * ``supabase.allow_service_role`` — read tools may use the RLS-bypassing
                                      service-role key only when this is True

Write tools are additionally gated by the unified decision engine (owner-gated
``ask`` + exact phrase; an embedded secret forces ``refuse``) and only author a
local migration file — they never mutate a live database. Keys live in env /
``~/.hermes/.env``; the service-role key is never returned to the model and
never sent to the Android cockpit.
"""

from __future__ import annotations

import logging

from plugins.supabase.tools import TOOL_REGISTRATIONS, check_supabase_requirements

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register every tool under the supabase toolset.

    Registered unconditionally so ``hermes tools list`` surfaces them even when
    disabled; ``check_fn`` hides them from the model until ``supabase.enabled``
    is True and the project is configured.
    """
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="supabase",
            schema=schema,
            handler=handler,
            check_fn=check_supabase_requirements,
            requires_env=["SUPABASE_URL", "SUPABASE_ANON_KEY"],
            emoji=emoji,
        )
    logger.debug("supabase registered %d tools", len(TOOL_REGISTRATIONS))
