"""Four agent-facing Apify tools registered by the apify plugin.

  apify_list_actors      — read  · list your Actors, or search the Apify
                            Store when ``search`` is given.
  apify_get_dataset_items — read · fetch items from a dataset id.
  apify_get_run          — read  · status/metadata of an Actor run.
  apify_run_actor        — RUN   · start an Actor, wait, return its dataset
                            items. Hidden + refused unless apify.allow_runs.

Every tool returns the same JSON envelope::

    {"success": bool, ...payload}

so the agent's structured-output parsing is uniform across success and
every failure case (no token, runs disabled, Actor not allowed, malformed
input, network/HTTP error).

Two safety gates live here:

  * ``check_apify_runs``  — visibility gate; ``apify_run_actor`` is hidden
                            until apify.enabled + APIFY_TOKEN + allow_runs.
  * ``_runs_enabled`` / ``allowed_actors`` — re-read on every call so an
                            operator can flip the gate without a restart.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from plugins.apify import config as apify_config
from plugins.apify.client import DEFAULT_LIST_CAP, HARD_LIST_CAP, ApifyClient

logger = logging.getLogger("apify.tools")

# Serialized-size budget for returned items. Datasets can be enormous;
# beyond this we drop trailing items and flag the result truncated so we
# never blow up the model context.
_ITEMS_BYTE_BUDGET = 200 * 1024


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------


def _json_str(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json_str(body)


def _ok(**payload: Any) -> str:
    return _json_str({"success": True, **payload})


def _from_client(result: Dict[str, Any]) -> str | None:
    """Map a non-success client result dict to our error envelope, else None."""
    if result.get("success"):
        return None
    return _err(
        str(result.get("error") or "error"),
        str(result.get("message") or ""),
        **({"status": result["status"]} if result.get("status") is not None else {}),
    )


def _cap_items(items: list[Any]) -> tuple[list[Any], bool]:
    """Trim ``items`` to fit the serialized-size budget. Returns (items, truncated)."""
    kept: list[Any] = []
    size = 0
    for item in items:
        try:
            size += len(json.dumps(item, ensure_ascii=False, default=str))
        except Exception:
            size += 1024
        if size > _ITEMS_BYTE_BUDGET and kept:
            return kept, True
        kept.append(item)
    return kept, False


# ---------------------------------------------------------------------------
# Runtime gates (check_fns for the registry)
# ---------------------------------------------------------------------------


def check_apify_read() -> bool:
    """Read tools: visible when the plugin is enabled AND a token is set."""
    cfg = apify_config.load_config()
    if not cfg.enabled:
        return False
    return ApifyClient().has_token()


def check_apify_runs() -> bool:
    """Run tool: also requires apify.allow_runs (Actor runs cost compute)."""
    cfg = apify_config.load_config()
    if not cfg.enabled or not cfg.allow_runs:
        return False
    return ApifyClient().has_token()


def _enabled_or_error() -> str | None:
    if not apify_config.load_config().enabled:
        return _err("plugin_disabled", "apify.enabled is false")
    return None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

LIST_ACTORS_SCHEMA: Dict[str, Any] = {
    "name": "apify_list_actors",
    "description": (
        "List Actors (Apify's reusable scrapers/automations). With no "
        "arguments, returns your own Actors. With `search`, searches the "
        "public Apify Store for matching Actors (e.g. 'instagram', "
        "'google maps', 'website content crawler'). Use this to discover an "
        "Actor's id/slug before running it. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Search the public Apify Store instead of your own Actors.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": HARD_LIST_CAP},
        },
        "additionalProperties": False,
    },
}

GET_DATASET_ITEMS_SCHEMA: Dict[str, Any] = {
    "name": "apify_get_dataset_items",
    "description": (
        "Fetch items from an Apify dataset by its id — typically the output "
        "of a previous Actor run (its `defaultDatasetId`). Read-only; "
        "returns up to `limit` cleaned items."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "The dataset id, e.g. from a run's defaultDatasetId.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": HARD_LIST_CAP},
            "offset": {"type": "integer", "minimum": 0},
        },
        "required": ["dataset_id"],
        "additionalProperties": False,
    },
}

GET_RUN_SCHEMA: Dict[str, Any] = {
    "name": "apify_get_run",
    "description": (
        "Get the status and metadata of an Actor run by its run id: status "
        "(READY/RUNNING/SUCCEEDED/FAILED/…), timestamps, the "
        "defaultDatasetId to fetch results from, and usage stats. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "The Actor run id."},
        },
        "required": ["run_id"],
        "additionalProperties": False,
    },
}

RUN_ACTOR_SCHEMA: Dict[str, Any] = {
    "name": "apify_run_actor",
    "description": (
        "Run an Apify Actor and wait for it to finish, returning its dataset "
        "items. `actor_id` is an Actor id or 'username/name' slug (e.g. "
        "'apify/website-content-crawler'); `input` is the Actor's input "
        "object (see the Actor's docs/README for its schema). "
        "NOTE: this starts a BILLABLE Actor run that consumes Apify compute "
        "units — it only works when apify.allow_runs is enabled, and an "
        "optional allowed_actors allowlist may restrict which Actors can run."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "actor_id": {
                "type": "string",
                "description": "Actor id or 'username/name' slug.",
            },
            "input": {
                "type": "object",
                "description": "The Actor's input object (passed through as-is).",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": HARD_LIST_CAP,
                "description": "Max dataset items to return (default 25).",
            },
            "timeout_secs": {
                "type": "integer",
                "minimum": 1,
                "maximum": apify_config.MAX_RUN_TIMEOUT_SECS,
                "description": "Actor run timeout in seconds (default 60, max 300).",
            },
        },
        "required": ["actor_id"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# Slimming
# ---------------------------------------------------------------------------


def _slim_actor(a: Dict[str, Any]) -> Dict[str, Any]:
    username = a.get("username")
    name = a.get("name")
    slug = f"{username}/{name}" if username and name else name
    stats = a.get("stats") or {}
    return {
        "id": a.get("id"),
        "name": name,
        "username": username,
        "slug": slug,
        "title": a.get("title"),
        "description": a.get("description"),
        "total_runs": stats.get("totalRuns"),
    }


def _slim_run(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r.get("id"),
        "actor_id": r.get("actId"),
        "status": r.get("status"),
        "started_at": r.get("startedAt"),
        "finished_at": r.get("finishedAt"),
        "default_dataset_id": r.get("defaultDatasetId"),
        "stats": r.get("stats"),
        "exit_code": r.get("exitCode"),
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_list_actors(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = ApifyClient()
    if not client.has_token():
        return _err("no_token", "APIFY_TOKEN is not configured. Set it in ~/.hermes/.env.")
    limit = max(1, min(int(args.get("limit") or DEFAULT_LIST_CAP), HARD_LIST_CAP))
    search = args.get("search")
    if isinstance(search, str) and search.strip():
        result = client.search_store(search=search.strip(), limit=limit)
        source = "store"
    else:
        result = client.list_actors(limit=limit)
        source = "user"
    if (err := _from_client(result)) is not None:
        return err
    data = (result.get("payload") or {}).get("data") or {}
    items = data.get("items") or []
    actors = [_slim_actor(a) for a in items if isinstance(a, dict)]
    return _ok(source=source, count=len(actors), total=data.get("total"), actors=actors)


def handle_get_dataset_items(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = ApifyClient()
    if not client.has_token():
        return _err("no_token", "APIFY_TOKEN is not configured. Set it in ~/.hermes/.env.")
    try:
        dataset_id = apify_config.validate_store_id(
            args.get("dataset_id"), label="dataset_id"
        )
    except apify_config.ConfigError as exc:
        return _err("bad_request", str(exc))
    limit = max(1, min(int(args.get("limit") or DEFAULT_LIST_CAP), HARD_LIST_CAP))
    offset = max(0, int(args.get("offset") or 0))
    result = client.dataset_items(dataset_id, limit=limit, offset=offset)
    if (err := _from_client(result)) is not None:
        return err
    payload = result.get("payload")
    items = payload if isinstance(payload, list) else []
    items, truncated = _cap_items(items)
    return _ok(
        dataset_id=dataset_id,
        count=len(items),
        truncated=truncated,
        items=items,
    )


def handle_get_run(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    client = ApifyClient()
    if not client.has_token():
        return _err("no_token", "APIFY_TOKEN is not configured. Set it in ~/.hermes/.env.")
    try:
        run_id = apify_config.validate_store_id(args.get("run_id"), label="run_id")
    except apify_config.ConfigError as exc:
        return _err("bad_request", str(exc))
    result = client.run(run_id)
    if (err := _from_client(result)) is not None:
        return err
    data = (result.get("payload") or {}).get("data") or {}
    return _ok(run=_slim_run(data))


def handle_run_actor(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    cfg = apify_config.load_config()
    if not cfg.allow_runs:
        return _err(
            "runs_disabled",
            "apify.allow_runs is false. Running an Actor consumes paid Apify "
            "compute units; set apify.allow_runs: true in ~/.hermes/config.yaml "
            "to permit it.",
        )
    client = ApifyClient()
    if not client.has_token():
        return _err("no_token", "APIFY_TOKEN is not configured. Set it in ~/.hermes/.env.")
    try:
        actor_id = apify_config.validate_actor_id(args.get("actor_id"))
    except apify_config.ConfigError as exc:
        return _err("bad_request", str(exc))
    if not cfg.is_actor_allowed(actor_id):
        return _err(
            "actor_not_allowed",
            f"Actor {actor_id!r} is not in apify.allowed_actors.",
        )
    run_input = args.get("input")
    if run_input is not None and not isinstance(run_input, dict):
        return _err("bad_request", "input must be an object")
    limit = max(1, min(int(args.get("limit") or DEFAULT_LIST_CAP), HARD_LIST_CAP))
    timeout_secs = int(args.get("timeout_secs") or apify_config.DEFAULT_RUN_TIMEOUT_SECS)
    timeout_secs = max(1, min(timeout_secs, apify_config.MAX_RUN_TIMEOUT_SECS))
    result = client.run_actor_sync(
        actor_id,
        run_input=run_input,
        limit=limit,
        timeout_secs=timeout_secs,
    )
    if (err := _from_client(result)) is not None:
        return err
    payload = result.get("payload")
    items = payload if isinstance(payload, list) else []
    items, truncated = _cap_items(items)
    return _ok(
        actor_id=actor_id,
        count=len(items),
        truncated=truncated,
        items=items,
    )


# (name, schema, handler, emoji, check_fn, requires_env)
TOOL_REGISTRATIONS = (
    (
        "apify_list_actors",
        LIST_ACTORS_SCHEMA,
        handle_list_actors,
        "🕷️",
        check_apify_read,
        ["APIFY_TOKEN"],
    ),
    (
        "apify_get_dataset_items",
        GET_DATASET_ITEMS_SCHEMA,
        handle_get_dataset_items,
        "📦",
        check_apify_read,
        ["APIFY_TOKEN"],
    ),
    (
        "apify_get_run",
        GET_RUN_SCHEMA,
        handle_get_run,
        "📊",
        check_apify_read,
        ["APIFY_TOKEN"],
    ),
    (
        "apify_run_actor",
        RUN_ACTOR_SCHEMA,
        handle_run_actor,
        "🚀",
        check_apify_runs,
        ["APIFY_TOKEN"],
    ),
)
