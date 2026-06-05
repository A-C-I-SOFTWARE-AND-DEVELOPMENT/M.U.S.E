"""Out-of-band executors for Vercel write actions.

Invoked only by the owner-approval path (cockpit decide after device auth, or
an owner-run CLI) via :mod:`hermes_cli.action_executors` — never by the model's
tool loop. Each executor performs the real mutation through :class:`VercelClient`
and returns the uniform ``{"success": bool, ...}`` envelope, never echoing the
env-var value or the deploy-hook URL back.
"""

from __future__ import annotations

from typing import Any, Dict

from plugins.vercel.client import VercelClient


def _client() -> VercelClient:
    return VercelClient()


def apply_set_env(params: Dict[str, Any]) -> Dict[str, Any]:
    client = _client()
    if not client.has_token():
        return {"success": False, "error": "no_token", "executed": False}
    project = params.get("project")
    key = params.get("key")
    value = params.get("value")
    target = params.get("target") or ["preview"]
    if not (
        isinstance(project, str) and isinstance(key, str) and isinstance(value, str)
    ):
        return {"success": False, "error": "bad_params", "executed": False}
    res = client.create_env(project_id=project, key=key, value=value, target=target)
    if not res.get("success"):
        return {**res, "executed": False}
    # Never echo the value back.
    return {"success": True, "executed": True, "env": {"key": key, "target": target}}


def apply_deploy(params: Dict[str, Any]) -> Dict[str, Any]:
    client = _client()
    if not client.has_token():
        return {"success": False, "error": "no_token", "executed": False}
    hook = params.get("deploy_hook_url")
    if not isinstance(hook, str) or not hook.startswith("https://api.vercel.com/"):
        return {"success": False, "error": "bad_params", "executed": False}
    res = client.trigger_deploy_hook(hook)
    if not res.get("success"):
        return {**res, "executed": False}
    return {"success": True, "executed": True, "project": params.get("project")}


def apply_cancel(params: Dict[str, Any]) -> Dict[str, Any]:
    client = _client()
    if not client.has_token():
        return {"success": False, "error": "no_token", "executed": False}
    deployment_id = params.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id:
        return {"success": False, "error": "bad_params", "executed": False}
    res = client.cancel_deployment(deployment_id)
    if not res.get("success"):
        return {**res, "executed": False}
    return {"success": True, "executed": True, "deployment_id": deployment_id}


def register_executors() -> None:
    """Register the Vercel executors. Safe to call repeatedly (idempotent)."""
    from hermes_cli.action_executors import register

    register("vercel.set_env", apply_set_env)
    register("vercel.deploy", apply_deploy)
    register("vercel.cancel_deployment", apply_cancel)
