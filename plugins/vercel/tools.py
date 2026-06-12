"""Agent-facing Vercel tools registered by the vercel plugin.

Four read tools (projects, deployments, preview URL, logs) and three
owner-gated write tools (env var, deploy, cancel). Every tool returns the
uniform ``{"success": bool, ...}`` JSON envelope used across Hermes plugins.

Safety model (defence in depth — all three must hold before a write runs):

  1. ``vercel.enabled`` is True and ``VERCEL_TOKEN`` is set (``check_fn``).
  2. ``vercel.allow_writes`` is True and the project passes the allowlist.
  3. A unified :class:`DecisionVerdict` is computed for the action; writes are
     owner-gated, so the verdict is ``ask`` and the caller must echo the exact
     ``required_owner_phrase``. Without it the tool returns the verdict and
     does **not** call the API (``executed: false``). A ``refuse`` verdict
     always blocks.

The token is never logged or returned. Env-var *values* are never echoed back
in a response (only the key + targets are surfaced).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from plugins.vercel import config as vercel_config
from plugins.vercel.client import DEFAULT_LIST_CAP, HARD_LIST_CAP, VercelClient

logger = logging.getLogger("vercel.tools")


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json(body)


def _ok(**payload: Any) -> str:
    return _json({"success": True, **payload})


def check_vercel_requirements() -> bool:
    """True when ``vercel.enabled`` and a token is configured."""
    cfg = vercel_config.load_config()
    if not cfg.enabled:
        return False
    return VercelClient().has_token()


class _GateFailure(Exception):
    def __init__(self, payload_json: str) -> None:
        self.payload_json = payload_json
        super().__init__(payload_json)


def _require_enabled() -> vercel_config.VercelConfig:
    cfg = vercel_config.load_config()
    if not cfg.enabled:
        raise _GateFailure(_err("plugin_disabled", "vercel.enabled is false"))
    return cfg


def _require_project(cfg: vercel_config.VercelConfig, args: Dict[str, Any]) -> str:
    project = args.get("project") or args.get("project_id")
    if not isinstance(project, str) or not project:
        raise _GateFailure(_err("bad_args", "project is required"))
    try:
        vercel_config.validate_project(project)
    except vercel_config.ConfigError as exc:
        raise _GateFailure(_err("bad_args", str(exc))) from exc
    if not cfg.is_project_allowed(project):
        raise _GateFailure(
            _err("project_not_allowed", f"{project} is not in vercel.allowed_projects")
        )
    return project


def _require_client() -> VercelClient:
    client = VercelClient()
    if not client.has_token():
        raise _GateFailure(
            _err(
                "no_token", "VERCEL_TOKEN is not configured. Set it in ~/.hermes/.env."
            )
        )
    return client


def _propose_write(
    cfg: vercel_config.VercelConfig,
    action_type: str,
    *,
    summary: str,
    proposed: Optional[Dict[str, Any]] = None,
) -> str:
    """Owner-gated *proposal* for a write — never the mutation itself.

    A tool cannot enforce an owner gate from inside the model-visible tool loop:
    the model controls its own arguments and the owner phrase is a public
    constant, so any "supply the phrase to proceed" check is self-authorizable.
    Therefore write tools never perform the API mutation here. They compute the
    :class:`DecisionVerdict` and return it with ``executed: false``; the actual
    change must be carried out by the out-of-band owner-approval path (the
    cockpit), which is outside the model's control.
    """
    from muse_cli.decision_engine import merge_decision_inputs, owner_gate_input

    verdict = merge_decision_inputs(
        action_type=action_type,
        inputs=[owner_gate_input(True, action=summary)],
    )
    redacted = verdict.to_redacted_dict()

    if verdict.is_refuse:
        return _err("refused", verdict.rationale, verdict=redacted, executed=False)
    if not cfg.allow_writes:
        return _err(
            "writes_disabled",
            "vercel.allow_writes is false; set it true in ~/.hermes/config.yaml "
            "to let this tool propose a write.",
            verdict=redacted,
            executed=False,
        )
    body: Dict[str, Any] = {
        "success": True,
        "executed": False,
        "approval_required": True,
        "verdict": redacted,
        "message": (
            "Write proposed and owner-gated. The mutation is NOT performed from "
            "the tool loop — approve and execute it through the cockpit "
            "owner-approval path."
        ),
    }
    if proposed:
        body["proposed"] = proposed
    return _json(body)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_PROJECT_PROP = {
    "type": "string",
    "description": "Vercel project name or id (e.g. 'my-app' or 'prj_…').",
}
LIST_PROJECTS_SCHEMA: Dict[str, Any] = {
    "name": "vercel_list_projects",
    "description": "List Vercel projects the token can access (read-only).",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": f"Max projects (≤{HARD_LIST_CAP}).",
            }
        },
        "additionalProperties": False,
    },
}

GET_DEPLOYMENT_SCHEMA: Dict[str, Any] = {
    "name": "vercel_get_deployment",
    "description": "Get a single Vercel deployment's status and metadata (read-only).",
    "parameters": {
        "type": "object",
        "properties": {
            "deployment_id": {"type": "string", "description": "Deployment id or url."}
        },
        "required": ["deployment_id"],
        "additionalProperties": False,
    },
}

GET_PREVIEW_URL_SCHEMA: Dict[str, Any] = {
    "name": "vercel_get_preview_url",
    "description": (
        "Return the URL + state of a project's most recent deployment "
        "(read-only). Use after a PR job to surface the preview link."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": _PROJECT_PROP,
            "target": {
                "type": "string",
                "description": "Optional: 'production' or 'preview'.",
                "enum": ["production", "preview"],
            },
        },
        "required": ["project"],
        "additionalProperties": False,
    },
}

TAIL_LOGS_SCHEMA: Dict[str, Any] = {
    "name": "vercel_tail_logs",
    "description": "Fetch recent build/runtime log events for a deployment (read-only, redacted).",
    "parameters": {
        "type": "object",
        "properties": {
            "deployment_id": {"type": "string", "description": "Deployment id or url."},
            "limit": {
                "type": "integer",
                "description": f"Max events (≤{HARD_LIST_CAP}).",
            },
        },
        "required": ["deployment_id"],
        "additionalProperties": False,
    },
}

SET_ENV_SCHEMA: Dict[str, Any] = {
    "name": "vercel_set_env",
    "description": (
        "Propose setting a project environment variable. OWNER-GATED and "
        "PROPOSE-ONLY: returns a decision verdict with executed=false; the "
        "change is applied out-of-band via the cockpit owner-approval path, "
        "never from this tool. The value is never echoed back."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": _PROJECT_PROP,
            "key": {"type": "string", "description": "Env var name."},
            "value": {
                "type": "string",
                "description": "Env var value (never logged/returned).",
            },
            "target": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["production", "preview", "development"],
                },
                "description": "Environments to apply to (default ['preview']).",
            },
        },
        "required": ["project", "key", "value"],
        "additionalProperties": False,
    },
}

DEPLOY_SCHEMA: Dict[str, Any] = {
    "name": "vercel_deploy",
    "description": (
        "Propose triggering a deployment via a project Deploy Hook URL. "
        "OWNER-GATED and PROPOSE-ONLY: returns a decision verdict with "
        "executed=false; the deploy is triggered out-of-band via the cockpit "
        "owner-approval path, never from this tool."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": _PROJECT_PROP,
            "deploy_hook_url": {
                "type": "string",
                "description": "Vercel Deploy Hook URL (https://api.vercel.com/v1/integrations/deploy/…).",
            },
        },
        "required": ["project", "deploy_hook_url"],
        "additionalProperties": False,
    },
}

CANCEL_DEPLOYMENT_SCHEMA: Dict[str, Any] = {
    "name": "vercel_cancel_deployment",
    "description": (
        "Propose cancelling an in-progress deployment. OWNER-GATED and "
        "PROPOSE-ONLY: returns a decision verdict with executed=false; the "
        "cancel is performed out-of-band via the cockpit owner-approval path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": _PROJECT_PROP,
            "deployment_id": {
                "type": "string",
                "description": "Deployment id to cancel.",
            },
        },
        "required": ["project", "deployment_id"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _slim_project(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "framework": p.get("framework"),
        "updated_at": p.get("updatedAt"),
    }


def _slim_deployment(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "uid": d.get("uid") or d.get("id"),
        "url": d.get("url"),
        "state": d.get("state") or d.get("readyState"),
        "target": d.get("target"),
        "created_at": d.get("created") or d.get("createdAt"),
    }


def handle_list_projects(args: Dict[str, Any], **_kw) -> str:
    try:
        _require_enabled()
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    limit = int(args.get("limit") or DEFAULT_LIST_CAP)
    res = client.list_projects(limit=limit)
    if not res.get("success"):
        return _json(res)
    payload = res.get("payload") or {}
    projects = payload.get("projects") if isinstance(payload, dict) else None
    return _ok(
        projects=[_slim_project(p) for p in (projects or []) if isinstance(p, dict)]
    )


def handle_get_deployment(args: Dict[str, Any], **_kw) -> str:
    try:
        _require_enabled()
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    deployment_id = args.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id:
        return _err("bad_args", "deployment_id is required")
    res = client.get_deployment(deployment_id)
    if not res.get("success"):
        return _json(res)
    return _ok(deployment=_slim_deployment(res.get("payload") or {}))


def handle_get_preview_url(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        project = _require_project(cfg, args)
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    target = args.get("target")
    res = client.list_deployments(project_id=project, limit=1, target=target)
    if not res.get("success"):
        return _json(res)
    payload = res.get("payload") or {}
    deployments = payload.get("deployments") if isinstance(payload, dict) else None
    if not deployments:
        return _ok(deployment=None, message="no deployments found for project")
    return _ok(deployment=_slim_deployment(deployments[0]))


def handle_tail_logs(args: Dict[str, Any], **_kw) -> str:
    try:
        _require_enabled()
        client = _require_client()
    except _GateFailure as exc:
        return exc.payload_json
    deployment_id = args.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id:
        return _err("bad_args", "deployment_id is required")
    limit = int(args.get("limit") or DEFAULT_LIST_CAP)
    res = client.get_deployment_events(deployment_id, limit=limit)
    if not res.get("success"):
        return _json(res)
    events = res.get("payload") or []
    slim = []
    for e in events if isinstance(events, list) else []:
        if not isinstance(e, dict):
            continue
        text = e.get("text") or (e.get("payload") or {}).get("text")
        slim.append({"type": e.get("type"), "created": e.get("created"), "text": text})
    return _ok(events=slim[:limit])


# ---------------------------------------------------------------------------
# Write handlers (owner-gated, propose-only — never mutate from the tool loop)
# ---------------------------------------------------------------------------


def handle_set_env(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        project = _require_project(cfg, args)
    except _GateFailure as exc:
        return exc.payload_json
    key = args.get("key")
    value = args.get("value")
    if not isinstance(key, str) or not key:
        return _err("bad_args", "key is required")
    if not isinstance(value, str):
        return _err("bad_args", "value must be a string")
    target = args.get("target") or ["preview"]
    if not isinstance(target, list) or not all(isinstance(t, str) for t in target):
        return _err("bad_args", "target must be a list of strings")
    # The value is intentionally omitted from the proposal echo.
    return _propose_write(
        cfg,
        "vercel.set_env",
        summary=f"set env {key} on {project} {target}",
        proposed={"project": project, "key": key, "target": target},
    )


def handle_deploy(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        project = _require_project(cfg, args)
    except _GateFailure as exc:
        return exc.payload_json
    hook = args.get("deploy_hook_url")
    if not isinstance(hook, str) or not hook.startswith("https://api.vercel.com/"):
        return _err("bad_args", "deploy_hook_url must be a https://api.vercel.com/ URL")
    # The hook URL is a capability token — describe the action, don't echo it.
    return _propose_write(
        cfg,
        "vercel.deploy",
        summary=f"trigger a deploy hook for {project}",
        proposed={"project": project, "via": "deploy_hook"},
    )


def handle_cancel_deployment(args: Dict[str, Any], **_kw) -> str:
    try:
        cfg = _require_enabled()
        project = _require_project(cfg, args)
    except _GateFailure as exc:
        return exc.payload_json
    deployment_id = args.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id:
        return _err("bad_args", "deployment_id is required")
    # Cancellation by id is owner-approved out-of-band, where the approver can
    # confirm the deployment actually belongs to ``project`` before it runs.
    return _propose_write(
        cfg,
        "vercel.cancel_deployment",
        summary=f"cancel deployment {deployment_id} on {project}",
        proposed={"project": project, "deployment_id": deployment_id},
    )


TOOL_REGISTRATIONS = (
    ("vercel_list_projects", LIST_PROJECTS_SCHEMA, handle_list_projects, "▲"),
    ("vercel_get_deployment", GET_DEPLOYMENT_SCHEMA, handle_get_deployment, "🚀"),
    ("vercel_get_preview_url", GET_PREVIEW_URL_SCHEMA, handle_get_preview_url, "🔗"),
    ("vercel_tail_logs", TAIL_LOGS_SCHEMA, handle_tail_logs, "📜"),
    ("vercel_set_env", SET_ENV_SCHEMA, handle_set_env, "🔧"),
    ("vercel_deploy", DEPLOY_SCHEMA, handle_deploy, "📦"),
    (
        "vercel_cancel_deployment",
        CANCEL_DEPLOYMENT_SCHEMA,
        handle_cancel_deployment,
        "🛑",
    ),
)
