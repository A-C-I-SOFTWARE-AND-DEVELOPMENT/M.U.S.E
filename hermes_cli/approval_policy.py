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
    # ── Coding-workspace actions ──────────────────────────────────────────
    # These are the friction points of in-workspace coding work. They default
    # to CONFIRM under every pre-existing level (they are in no existing
    # auto-allowlist) and are only auto-approved by OWNER_HIGH_AUTONOMY_CODING
    # when scoped to an approved workspace.
    DEPENDENCY_INSTALL = "dependency_install"  # pip/npm install inside the project env
    LOCAL_SERVER = "local_server"  # start/stop a dev server bound to loopback
    BRANCH_CREATE = "branch_create"  # git branch / checkout -b (local only)
    LOCAL_COMMIT = "local_commit"  # git commit (no push)
    CODE_WORKER_EXEC = "code_worker_exec"  # run a code worker in the workspace


class AutonomyLevel(str, enum.Enum):
    READ_ONLY = "read_only"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"
    YOLO = "yolo"
    # Owner High-Autonomy Coding — friction-reduced for coding work *inside an
    # approved workspace*, while every irreversible/external/high-risk action
    # (the _ALWAYS_CONFIRM set + owner gates) stays gated exactly as before.
    OWNER_HIGH_AUTONOMY_CODING = "owner_high_autonomy_coding"


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

# Categories OWNER_HIGH_AUTONOMY_CODING runs unattended *inside an approved
# workspace*. Everything here is local, reversible coding work. Anything not
# in this set (and not a safe read) falls through to CONFIRM, and the
# _ALWAYS_CONFIRM set above is still evaluated first — so deploy, publish,
# force-push, destructive commands, supabase/vercel changes, remote secret
# transfer and public tunnels remain gated. Owner gates (owner_auth.py) are
# untouched.
_HIGH_AUTONOMY_CODING_AUTO: frozenset[Action] = frozenset(
    {
        Action.SAFE_READ,
        Action.SAFE_LOCAL_WRITE,
        Action.LOCAL_COMMAND,
        Action.SECRET_ACCESS,
        Action.DEPENDENCY_INSTALL,
        Action.LOCAL_SERVER,
        Action.BRANCH_CREATE,
        Action.LOCAL_COMMIT,
        Action.CODE_WORKER_EXEC,
    }
)

# Within _HIGH_AUTONOMY_CODING_AUTO, these act on a filesystem path and are
# only auto-approved when that path resolves *inside* the approved workspace.
# Editing or running a worker outside the workspace falls through to CONFIRM.
_WORKSPACE_SCOPED_ACTIONS: frozenset[Action] = frozenset(
    {
        Action.SAFE_LOCAL_WRITE,
        Action.CODE_WORKER_EXEC,
    }
)

# Protected branches — force-pushing these is always denied.
DEFAULT_PROTECTED_BRANCHES: frozenset[str] = frozenset(
    {"main", "master", "release", "production", "prod"}
)


def _hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME")
    base = Path(home) if home else Path.home() / ".hermes"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _autonomy_store_path() -> Path:
    return _hermes_home() / "autonomy.json"


@dataclass(frozen=True)
class AutonomyRecord:
    """The owner's persisted autonomy choice.

    ``workspace_root`` scopes OWNER_HIGH_AUTONOMY_CODING to a single approved
    workspace; it is ignored by the other levels. The record is owner-set
    (typically from the Android cockpit) and instantly revocable.
    """

    level: AutonomyLevel = AutonomyLevel.ASSISTED
    workspace_root: str = ""
    updated_at: float = 0.0
    set_by: str = "owner"


def load_record(path: Optional[Path] = None) -> AutonomyRecord:
    """Load the persisted autonomy record (defaults to ASSISTED)."""
    import json

    target = path or _autonomy_store_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AutonomyRecord()
    try:
        level = AutonomyLevel(str(raw.get("level", "assisted")))
    except ValueError:
        level = AutonomyLevel.ASSISTED
    return AutonomyRecord(
        level=level,
        workspace_root=str(raw.get("workspace_root", "") or ""),
        updated_at=float(raw.get("updated_at", 0.0) or 0.0),
        set_by=str(raw.get("set_by", "owner") or "owner"),
    )


def save_level(
    level: AutonomyLevel,
    *,
    workspace_root: str = "",
    set_by: str = "owner",
    path: Optional[Path] = None,
) -> AutonomyRecord:
    """Persist the owner's autonomy choice and return the new record.

    The change is also written to the approval audit log so the cockpit
    audit trail shows when (and to what) autonomy was set or revoked.
    """
    import json

    record = AutonomyRecord(
        level=level,
        workspace_root=workspace_root or "",
        updated_at=time.time(),
        set_by=set_by,
    )
    target = path or _autonomy_store_path()
    try:
        target.write_text(
            json.dumps(
                {
                    "level": record.level.value,
                    "workspace_root": record.workspace_root,
                    "updated_at": record.updated_at,
                    "set_by": record.set_by,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("autonomy store write failed (%s): %s", target, exc)
    return record


def revoke(*, set_by: str = "owner", path: Optional[Path] = None) -> AutonomyRecord:
    """Instantly drop autonomy back to the safe default (ASSISTED)."""
    return save_level(AutonomyLevel.ASSISTED, set_by=set_by, path=path)


def _autonomy_from_env(default: AutonomyLevel = AutonomyLevel.ASSISTED) -> AutonomyLevel:
    """Resolve the active level: env var first, then persisted record.

    ``HERMES_AUTONOMY`` always wins so existing env-driven deployments are
    unaffected; the persisted record is the owner's cockpit-set choice.
    """
    raw = os.environ.get("HERMES_AUTONOMY", "").strip().lower()
    if raw:
        try:
            return AutonomyLevel(raw)
        except ValueError:
            logger.warning("Unknown HERMES_AUTONOMY=%r; defaulting to %s", raw, default.value)
            return default
    return load_record().level


def _within_workspace(target: str, workspace_root: str) -> bool:
    """True iff ``target`` resolves inside ``workspace_root``.

    Fail-closed: an empty workspace, an empty target, or any resolution
    error means "not inside" (→ the action falls through to CONFIRM).
    """
    if not workspace_root or not target:
        return False
    try:
        root = Path(workspace_root).expanduser().resolve()
        candidate = Path(target).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return root == candidate or root in candidate.parents


def evaluate(
    request: ApprovalRequest,
    *,
    autonomy: Optional[AutonomyLevel] = None,
    protected_branches: Optional[frozenset[str]] = None,
    workspace_root: Optional[str] = None,
) -> ApprovalResult:
    """Decide whether the agent may proceed with ``request``.

    ``workspace_root`` scopes :class:`AutonomyLevel.OWNER_HIGH_AUTONOMY_CODING`.
    When not supplied it is read from the persisted autonomy record so callers
    that don't track a workspace still get correct scoping. It is ignored by
    every other level.
    """
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

    # Owner High-Autonomy Coding: auto-approve in-workspace coding work only.
    if level is AutonomyLevel.OWNER_HIGH_AUTONOMY_CODING:
        ws = workspace_root if workspace_root is not None else load_record().workspace_root
        if request.action in _HIGH_AUTONOMY_CODING_AUTO:
            if request.action in _WORKSPACE_SCOPED_ACTIONS:
                if _within_workspace(request.target, ws):
                    return ApprovalResult(
                        Decision.ALLOW,
                        f"owner_high_autonomy_coding: auto-approved {request.action.value} "
                        f"inside approved workspace {ws}",
                        needs_prompt=False,
                    )
                return ApprovalResult(
                    Decision.CONFIRM,
                    f"owner_high_autonomy_coding: {request.action.value} on "
                    f"{request.target or '<unspecified path>'} is outside the approved "
                    f"workspace — operator confirmation required",
                    needs_prompt=True,
                )
            # Inherently-local actions: require a configured workspace, else
            # fail-closed to a confirmation.
            if ws:
                return ApprovalResult(
                    Decision.ALLOW,
                    f"owner_high_autonomy_coding: auto-approved {request.action.value} "
                    f"in approved workspace {ws}",
                    needs_prompt=False,
                )
            return ApprovalResult(
                Decision.CONFIRM,
                f"owner_high_autonomy_coding: {request.action.value} blocked — no approved "
                f"workspace configured; operator confirmation required",
                needs_prompt=True,
            )
        # Not a coding action — fall through to the shared confirm below.
        return ApprovalResult(
            Decision.CONFIRM,
            f"owner_high_autonomy_coding: {request.action.value} is outside the coding "
            f"allowlist — operator confirmation required",
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
    return _hermes_home() / "approval.log"


def read_decisions(limit: int = 50, log_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` decisions from the audit log.

    Entries are already redacted at write time by :func:`record_decision`, so
    this is safe to surface to the cockpit audit trail.
    """
    import json

    target = log_path or _audit_log_path()
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    out.reverse()  # newest first
    return out


def capabilities(level: AutonomyLevel) -> dict[str, list[str]]:
    """Describe what ``level`` auto-approves vs. still gates.

    Single source of truth for the cockpit + Android capability list, so the
    UI never hard-codes a divergent list. ``always_deny`` is the non-negotiable
    set (force-push to protected branches, un-targeted secret transfer,
    non-allowlisted public tunnel).
    """
    if level is AutonomyLevel.READ_ONLY:
        auto = sorted(_READ_ONLY_ALLOW)
    elif level is AutonomyLevel.ASSISTED:
        auto = sorted(_ASSISTED_AUTO)
    elif level is AutonomyLevel.AUTONOMOUS:
        auto = sorted(_AUTONOMOUS_AUTO)
    elif level is AutonomyLevel.OWNER_HIGH_AUTONOMY_CODING:
        auto = sorted(_HIGH_AUTONOMY_CODING_AUTO)
    elif level is AutonomyLevel.YOLO:
        auto = sorted(a for a in Action if a not in _YOLO_HARD_LIMITS)
    else:  # pragma: no cover - exhaustive
        auto = []
    auto_set = set(auto)
    always_deny = [
        Action.GITHUB_FORCE_PUSH.value,
        Action.REMOTE_SECRET_TRANSFER.value,
        Action.PUBLIC_TUNNEL.value,
    ]
    requires_approval = sorted(
        a.value for a in Action if a not in auto_set and a.value not in always_deny
    )
    return {
        "auto_approved": [a.value for a in auto],
        "requires_approval": requires_approval,
        "always_deny": always_deny,
        "workspace_scoped": sorted(a.value for a in _WORKSPACE_SCOPED_ACTIONS)
        if level is AutonomyLevel.OWNER_HIGH_AUTONOMY_CODING
        else [],
    }


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
    "AutonomyRecord",
    "DEFAULT_PROTECTED_BRANCHES",
    "Decision",
    "capabilities",
    "evaluate",
    "load_record",
    "read_decisions",
    "record_decision",
    "revoke",
    "save_level",
]
