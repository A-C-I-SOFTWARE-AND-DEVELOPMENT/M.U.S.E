"""github_assistant plugin — native GitHub REST access for Hermes.

Registers eight tools under the ``github`` toolset:

  read    — github_audit_repo, github_get_repo_file, github_list_branches,
            github_list_issues, github_list_pull_requests, github_get_pull_request
  write   — github_create_issue, github_comment_on_issue_or_pr

Three independently-toggled safety gates:

  * ``github.enabled``              — the master switch (default False)
  * ``github.allow_writes``         — write tools refuse without it (default False)
  * ``github.allowed_repositories`` — when non-empty, every owner/name
                                      must be on the list

The token lives in ``GITHUB_PERSONAL_ACCESS_TOKEN`` (env or
``~/.hermes/.env``); it is never returned to the model, never echoed
in tool output, and never logged in plain text.

This is the *native plugin* path. If you'd rather use Anthropic's
official ``@modelcontextprotocol/server-github``, wire it up under
``mcp_servers.github`` in ``~/.hermes/config.yaml`` — the two paths
coexist cleanly. See ``docs/github-integration.md`` for the diff.
"""

from __future__ import annotations

import logging

from plugins.github_assistant.tools import (
    TOOL_REGISTRATIONS,
    check_github_requirements,
)

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register every tool under the github toolset.

    We register unconditionally so ``hermes tools list`` still surfaces
    the tools when the plugin is disabled (the operator can then see
    what they'd get by flipping ``github.enabled``). The ``check_fn``
    guards actual visibility to the model — when ``github.enabled``
    is False or no token is configured, the registry hides the tools.
    """
    for name, schema, handler, emoji in TOOL_REGISTRATIONS:
        ctx.register_tool(
            name=name,
            toolset="github",
            schema=schema,
            handler=handler,
            check_fn=check_github_requirements,
            requires_env=["GITHUB_PERSONAL_ACCESS_TOKEN"],
            emoji=emoji,
        )
    logger.debug("github_assistant registered %d tools", len(TOOL_REGISTRATIONS))
