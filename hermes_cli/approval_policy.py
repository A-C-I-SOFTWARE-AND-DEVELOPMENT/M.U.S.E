"""Approval policy for autonomous Hermes operations.

Hermes can run at very high autonomy — chained orchestrator jobs,
unattended Termux sessions, scheduled cron runs, etc. The approval
policy decides, for a given proposed action, whether the agent may
proceed unattended, must pause and ask the operator, or must refuse
outright.

The model is deliberately small. Each action belongs to one
:class:`Action` category and is evaluated against an
:class:`AutonomyLevel`. The result is a :class:`Decision` —
``ALLOW``, ``CONFIRM``, or ``DENY`` — accompanied by a human-readable
reason that the gateway / TUI can render verbatim.

Categories
----------

==============================  =================================================
Action                          Examples
==============================  =================================================
``SAFE_READ``                   reading a tracked source file, listing a directory
``SAFE_LOCAL_WRITE``            writing inside the project worktree
``LOCAL_COMMAND``               running tests, type-checkers, formatters
``DESTRUCTIVE_COMMAND``         ``rm -rf``, ``git reset --hard``, dropping a table
``REMOTE_COMMAND``              SSH to a non-loopback host, modal/daytona runs
``SECRET_ACCESS``               reading a credential by name
``REMOTE_SECRET_TRANSFER``      sending a secret to a remote worker
``GITHUB_PUSH``                 ``git push`` to any remote
``GITHUB_FORCE_PUSH``           ``git push --force`` / ``--force-with-lease``
``SUPABASE_CHANGE``             ``apply_migration``, ``execute_sql`` with DDL
``VERCEL_DEPLOY``               ``deploy_to_vercel``, ``promote``
``PUBLIC_TUNNEL``               cloudflared, ngrok, tailscale-funnel
``CONTINUOUS_LISTEN``           subscribe-and-react loops (PR webhooks, cron)
==============================  =================================================

Autonomy levels
---------------

==================  ============================================================
Level               Behavior
==================  ============================================================
``READ_ONLY``       Only ``SAFE_READ`` is allowed. Everything else returns DENY.
``ASSISTED``        Default. Safe categories run unattended; everything else
                    requires a confirmation prompt.
``AUTONOMOUS``      Safe + local-command + safe writes run unattended.
                    Destructive / remote / publishing actions still confirm.
``YOLO``            All categories except the always-deny set run unattended.
                    Always-deny: ``GITHUB_FORCE_PUSH`` to a protected branch,
                    ``REMOTE_SECRET_TRANSFER`` without a named target,
                    ``PUBLIC_TUNNEL`` without an explicit allowlist.
==================  ============================================================

Even at ``YOLO`` the always-deny set is non-negotiable — there is no
flag to disable it. The point of a policy is to be a policy.

The module records every decision via :func:`record_decision` so that
``hermes orchestrator status`` and the kanban-style audit trail have a
faithful, redacted record of what the agent was allowed to do.
"""

from __future__ import annotations

import enum
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .secrets_policy import redact


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Action(str, enum.Enum):
    SAFE_READ = "safe_read"
    SAFE_LOCAL_WRITE = "safe_local_write"
    LOCAL_COMMAND = "local_command"
    DESTRUCTIVE_COMMAND = "destructive_command"
    REMOTE_COMMAND = "remote_command"
    SECRET_ACCESS = "secret_access"
    REMOTE_SECRET_TRANSFER = "remote_secret_transfer"
    GITHUB_PUSH = "github_push"
    GITHUB_FORCE_PUSH = "github_force_push"
    SUPABASE_CHANGE = "supabase_change"
    VERCEL_DEPLOY = "vercel_deploy"
    PUBLIC_TUNNEL = "public_tunnel"
    CONTINUOUS_LISTEN = "continuous_listen"
    OUTBOUND_MESSAGE = "outbound_message"  # send email/SMS/calendar via an integration


class AutonomyLevel(str, enum.Enum):
    READ_ONLY = "read_only"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"
    YOLO = "yolo"


class Decision(str, enum.Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalRequest:
    """A proposed action, fully described.

    The fields are intentionally typed loosely (``Any``) so the same
    request shape works across CLI, gateway, MCP and orchestrator
    call sites. The policy reads only what it needs.
    """

    action: Action
    summary: str
    """One-line human-readable description (rendered to the operator)."""

    target: str = ""
    """The thing being acted on — repo path, URL, table name, etc."""

    details: dict[str, Any] = field(default_factory=dict)
    """Extra structured context. Values are redacted on log."""

    branch: str = ""
    """For git actions: the local branch involved."""

    remote_branch: str = ""
    """For git actions: the remote branch involved (e.g. ``main``)."""


@dataclass(frozen=True)
class ApprovalResult:
    decision: Decision
    reason: str
    needs_prompt: bool
    """``True`` if the caller must surface a confirmation UI before acting."""


# ---------------------------------------------------------------------------
# Policy logic
# ---------------------------------------------------------------------------


# Categories whose autonomy is unaffected by level — they always
# require a prompt OR are always denied. See module docstring.
_ALWAYS_CONFIRM: frozenset[Action] = frozenset(
    {
        Action.DESTRUCTIVE_COMMAND,
        Action.REMOTE_SECRET_TRANSFER,
        Action.GITHUB_PUSH,
        Action.GITHUB_FORCE_PUSH,
        Action.SUPABASE_CHANGE,
        Action.VERCEL_DEPLOY,
        Action.PUBLIC_TUNNEL,
    }
)

# Categories that READ_ONLY mode is allowed to perform.
_READ_ONLY_ALLOW: frozenset[Action] = frozenset({Action.SAFE_READ})

# Categories that ASSISTED mode runs unattended.
_ASSISTED_AUTO: frozenset[Action] = frozenset(
    {
        Action.SAFE_READ,
    }
)

# Categories that AUTONOMOUS mode runs unattended.
_AUTONOMOUS_AUTO: frozenset[Action] = frozenset(
    {
        Action.SAFE_READ,
        Action.SAFE_LOCAL_WRITE,
        Action.LOCAL_COMMAND,
        Action.SECRET_ACCESS,
        Action.CONTINUOUS_LISTEN,
        # Outbound messages (email/SMS/calendar) auto-send only under AUTONOMOUS
        # (or YOLO); ASSISTED/READ_ONLY still require operator confirmation.
        Action.OUTBOUND_MESSAGE,
    }
)

# YOLO runs everything unattended EXCEPT this set, which is always
# either prompted or denied regardless of autonomy.
_YOLO_HARD_LIMITS: frozenset[Action] = frozenset(
    {
        Action.REMOTE_SECRET_TRANSFER,
        Action.PUBLIC_TUNNEL,
    }
)

# Protected branches — force-pushing these is always denied.
DEFAULT_PROTECTED_BRANCHES: frozenset[str] = frozenset(
    {"main", "master", "release", "production", "prod"}
)


def _autonomy_from_env(default: AutonomyLevel = AutonomyLevel.ASSISTED) -> AutonomyLevel:
    raw = os.environ.get("HERMES_AUTONOMY", "").strip().lower()
    if not raw:
        return default
    try:
        return AutonomyLevel(raw)
    except ValueError:
        logger.warning("Unknown HERMES_AUTONOMY=%r; defaulting to %s", raw, default.value)
        return default


def evaluate(
    request: ApprovalRequest,
    *,
    autonomy: Optional[AutonomyLevel] = None,
    protected_branches: Optional[frozenset[str]] = None,
) -> ApprovalResult:
    """Decide whether the agent may proceed with ``request``."""
    level = autonomy if autonomy is not None else _autonomy_from_env()
    protected = protected_branches or DEFAULT_PROTECTED_BRANCHES

    # Always-deny rules — independent of autonomy.
    if request.action is Action.GITHUB_FORCE_PUSH and (
        request.remote_branch in protected or request.branch in protected
    ):
        return ApprovalResult(
            Decision.DENY,
            f"force-push to protected branch {request.remote_branch or request.branch!r} is not permitted",
            needs_prompt=False,
        )

    if request.action is Action.REMOTE_SECRET_TRANSFER and not request.target:
        return ApprovalResult(
            Decision.DENY,
            "remote secret transfer requires an explicit target",
            needs_prompt=False,
        )

    if request.action is Action.PUBLIC_TUNNEL and not request.details.get(
        "allowlisted"
    ):
        return ApprovalResult(
            Decision.DENY,
            "public tunnel requires an explicit allowlist entry",
            needs_prompt=False,
        )

    # Read-only mode: only safe reads.
    if level is AutonomyLevel.READ_ONLY:
        if request.action in _READ_ONLY_ALLOW:
            return ApprovalResult(Decision.ALLOW, "read-only allows safe reads", False)
        return ApprovalResult(
            Decision.DENY,
            f"{request.action.value} blocked in read-only mode",
            needs_prompt=False,
        )

    # Always-confirm categories: prompt unless YOLO.
    if request.action in _ALWAYS_CONFIRM:
        if level is AutonomyLevel.YOLO and request.action not in _YOLO_HARD_LIMITS:
            return ApprovalResult(
                Decision.ALLOW,
                f"yolo mode auto-approved {request.action.value}",
                needs_prompt=False,
            )
        return ApprovalResult(
            Decision.CONFIRM,
            f"{request.action.value} requires operator confirmation",
            needs_prompt=True,
        )

    # Level-specific auto-allowlist.
    if level is AutonomyLevel.ASSISTED and request.action in _ASSISTED_AUTO:
        return ApprovalResult(Decision.ALLOW, "assisted: safe read", False)
    if level is AutonomyLevel.AUTONOMOUS and request.action in _AUTONOMOUS_AUTO:
        return ApprovalResult(Decision.ALLOW, f"autonomous: {request.action.value}", False)
    if level is AutonomyLevel.YOLO and request.action not in _YOLO_HARD_LIMITS:
        return ApprovalResult(Decision.ALLOW, f"yolo: {request.action.value}", False)

    # Fall-through: confirm.
    return ApprovalResult(
        Decision.CONFIRM,
        f"{request.action.value} requires operator confirmation at {level.value}",
        needs_prompt=True,
    )


# ---------------------------------------------------------------------------
# Decision recording
# ---------------------------------------------------------------------------


def _audit_log_path() -> Path:
    home = os.environ.get("HERMES_HOME")
    if home:
        base = Path(home)
    else:
        base = Path.home() / ".hermes"
    base.mkdir(parents=True, exist_ok=True)
    return base / "approval.log"


def record_decision(
    request: ApprovalRequest,
    result: ApprovalResult,
    *,
    actor: str = "agent",
    log_path: Optional[Path] = None,
) -> None:
    """Append a redacted record of one decision to the audit log.

    The audit log is plain JSON-per-line so it is greppable. Values
    that look like secrets are replaced with sentinels before write.
    """
    import json

    target_path = log_path or _audit_log_path()
    redacted_details = {k: redact(str(v)) for k, v in request.details.items()}
    entry = {
        "ts": time.time(),
        "actor": actor,
        "action": request.action.value,
        "summary": redact(request.summary),
        "target": redact(request.target),
        "branch": request.branch,
        "remote_branch": request.remote_branch,
        "details": redacted_details,
        "decision": result.decision.value,
        "reason": result.reason,
        "needs_prompt": result.needs_prompt,
    }
    try:
        with target_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True))
            f.write("\n")
    except OSError as exc:
        logger.warning("approval audit write failed (%s): %s", target_path, exc)


__all__ = [
    "Action",
    "ApprovalRequest",
    "ApprovalResult",
    "AutonomyLevel",
    "DEFAULT_PROTECTED_BRANCHES",
    "Decision",
    "evaluate",
    "record_decision",
]
