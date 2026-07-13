"""Shared authenticated API operations for the M.U.S.E Universe plugin.

Cockpit routes, dashboard routes, slash commands, and model tools all delegate
to this module so they observe one home-scoped :class:`UniverseService` and one
cursor contract. Authentication remains the responsibility of the host route
surfaces: cockpit plugin routes are always bearer-gated and dashboard plugin
routes live below the dashboard's session-token middleware.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from uuid import uuid4

from pydantic import ValidationError as PydanticValidationError

from gateway.cockpit.handlers import JsonResponse, Request
from hermes_constants import get_hermes_home

from .authorization import AuthorizationError
from .models import utc_now
from .service import UniverseService, ValidationError
from .store import (
    AmbiguousEntityError,
    CommandIdConflictError,
    ConflictError,
    UniverseStore,
)


logger = logging.getLogger(__name__)

PLUGIN_ID = "muse-universe"
API_PREFIX = f"/v1/plugins/{PLUGIN_ID}"

_SHARED_STATE_MODULE = "_muse_universe_api_shared_state"
_state_candidate = ModuleType(_SHARED_STATE_MODULE)
setattr(_state_candidate, "services", {})
setattr(_state_candidate, "lock", threading.RLock())
_shared_state = sys.modules.setdefault(_SHARED_STATE_MODULE, _state_candidate)
_services = cast(dict[Path, UniverseService], getattr(_shared_state, "services"))
_services_lock = getattr(_shared_state, "lock")

_COMMAND_FIELDS = frozenset(
    {
        "command_id",
        "command_type",
        "realm_id",
        "actor_id",
        "expected_version",
        "payload",
        "approval_id",
        "simulation",
    }
)
_QUERY_FIELDS = frozenset(
    {
        "query",
        "realm_id",
        "actor_id",
        "since",
        "entity_type",
        "entity_id",
    }
)
_RECONCILE_FIELDS = frozenset({"realm_id"})


class NotFoundError(LookupError):
    """Raised when an authenticated read targets no authoritative entity."""


def service_for_home(home: str | Path | None = None) -> UniverseService:
    """Return the shared universe service for one resolved Hermes home."""
    root = Path(get_hermes_home() if home is None else home).expanduser().resolve()
    with _services_lock:
        service = _services.get(root)
        if service is None:
            service = UniverseService(
                UniverseStore(root / "universe" / "universe.db")
            )
            _services[root] = service
        return service


def reset_services_for_tests() -> None:
    """Drop cached service objects without deleting their persistent stores."""
    with _services_lock:
        _services.clear()


def status_data(
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    """Summarize realm and event-log health without exposing store paths."""
    universe = service or service_for_home(home)
    realms = universe.store.entities(None, "realm")
    realm_summaries: list[dict[str, Any]] = []
    event_count = 0
    cursor = 0
    for realm in realms:
        realm_id = str(realm.get("id", ""))
        events = universe.store.events_since(realm_id, 0) if realm_id else []
        realm_cursor = max((event.sequence for event in events), default=0)
        event_count += len(events)
        cursor = max(cursor, realm_cursor)
        realm_summaries.append(
            {
                "id": realm_id,
                "name": realm.get("name", realm_id),
                "mode": realm.get("mode"),
                "visibility": realm.get("visibility"),
                "version": realm.get("version", 0),
                "event_count": len(events),
                "cursor": realm_cursor,
            }
        )
    return {
        "ok": True,
        "service": PLUGIN_ID,
        "status": "ready",
        "realm_count": len(realm_summaries),
        "event_count": event_count,
        "cursor": cursor,
        "realms": realm_summaries,
        "server_time": utc_now(),
    }


def catalog_data(
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    universe = service or service_for_home(home)
    return universe.catalog()


def snapshot_data(
    realm_id: object,
    actor_id: object,
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    universe = service or service_for_home(home)
    return universe.snapshot(
        _required_text(actor_id, "actor_id"),
        _required_text(realm_id, "realm_id"),
    )


def events_data(
    realm_id: object,
    since: object = 0,
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    """Return all events after ``since`` and a non-regressing resume cursor."""
    universe = service or service_for_home(home)
    clean_realm_id = _required_text(realm_id, "realm_id")
    clean_since = _non_negative_integer(since, "since", default=0)
    all_events = universe.store.events_since(clean_realm_id, 0)
    events = [event for event in all_events if event.sequence > clean_since]
    latest_sequence = max(
        (event.sequence for event in all_events),
        default=0,
    )
    return {
        "events": [event.model_dump(mode="json") for event in events],
        "cursor": max(clean_since, latest_sequence),
        "realm_version": len(all_events),
        "server_time": utc_now(),
    }


def entity_data(
    entity_type: object,
    entity_id: object,
    actor_id: object,
    realm_id: object | None = None,
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    universe = service or service_for_home(home)
    clean_realm_id = _optional_text(realm_id, "realm_id")
    entity = universe.entity(
        _required_text(actor_id, "actor_id"),
        _required_text(entity_type, "entity_type"),
        _required_text(entity_id, "entity_id"),
        clean_realm_id,
    )
    if entity is None:
        raise NotFoundError("entity was not found")
    return entity


def command_data(
    body: object,
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    """Validate an untrusted command envelope and execute it authoritatively."""
    command = _mapping(body, "command")
    _reject_unknown_fields(command, _COMMAND_FIELDS, "command")
    universe = service or service_for_home(home)
    result = universe.execute(
        _required_text(command.get("command_type"), "command_type"),
        _required_text(command.get("actor_id"), "actor_id"),
        _required_text(command.get("realm_id"), "realm_id"),
        _mapping(command.get("payload"), "payload"),
        _non_negative_integer(
            command.get("expected_version"),
            "expected_version",
        ),
        _required_text(command.get("command_id"), "command_id"),
        approval_id=_optional_text(command.get("approval_id"), "approval_id"),
        simulation=_boolean(command.get("simulation", False), "simulation"),
    )
    return result.model_dump(mode="json")


def reconcile_data(
    body: object | None = None,
    *,
    service: UniverseService | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    """Reconcile real Hermes agents through the Task 4 adapter."""
    request_body = {} if body is None else _mapping(body, "reconcile request")
    _reject_unknown_fields(request_body, _RECONCILE_FIELDS, "reconcile request")
    realm_id = _optional_text(request_body.get("realm_id"), "realm_id")
    universe = service or service_for_home(home)
    from .reconcile import reconcile_agents

    report = _jsonable(
        reconcile_agents(universe, realm_id=realm_id or "rlm_local")
    )
    if isinstance(report, dict):
        return report
    return {"report": report}


def query_response(
    arguments: object,
    *,
    home: str | Path | None = None,
) -> JsonResponse:
    """Dispatch one model-tool read through the same HTTP error contract."""

    def operation() -> dict[str, Any]:
        query = _mapping(arguments, "query")
        _reject_unknown_fields(query, _QUERY_FIELDS, "query")
        query_name = _required_text(query.get("query"), "query")
        if query_name == "status":
            return status_data(home=home)
        if query_name == "catalog":
            return catalog_data(home=home)
        if query_name == "snapshot":
            return snapshot_data(
                query.get("realm_id"),
                query.get("actor_id"),
                home=home,
            )
        if query_name == "events":
            return events_data(
                query.get("realm_id"),
                query.get("since", 0),
                home=home,
            )
        if query_name == "entity":
            return entity_data(
                query.get("entity_type"),
                query.get("entity_id"),
                query.get("actor_id"),
                query.get("realm_id"),
                home=home,
            )
        raise ValidationError("query is unsupported")

    return _respond(operation)


def command_response(
    arguments: object,
    *,
    home: str | Path | None = None,
) -> JsonResponse:
    """Dispatch one model-tool command through the same HTTP error contract."""
    return _respond(lambda: command_data(arguments, home=home))


def response_json(response: JsonResponse) -> str:
    """Serialize a route response deterministically for model tools/slash output."""
    import json

    return json.dumps(
        response.payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def handle_status(_request: Request) -> JsonResponse:
    return _respond(status_data)


def handle_catalog(_request: Request) -> JsonResponse:
    return _respond(catalog_data)


def handle_snapshot(request: Request) -> JsonResponse:
    return _respond(
        lambda: snapshot_data(
            request.query.get("realm_id"),
            request.query.get("actor_id"),
        )
    )


def handle_events(request: Request) -> JsonResponse:
    return _respond(
        lambda: events_data(
            request.query.get("realm_id"),
            request.query.get("since", 0),
        )
    )


def handle_entity(request: Request) -> JsonResponse:
    return _respond(
        lambda: entity_data(
            request.path_params.get("entity_type"),
            request.path_params.get("entity_id"),
            request.query.get("actor_id"),
            request.query.get("realm_id"),
        )
    )


def handle_commands(request: Request) -> JsonResponse:
    return _respond(lambda: command_data(request.body))


def handle_reconcile(request: Request) -> JsonResponse:
    return _respond(lambda: reconcile_data(request.body))


def cockpit_routes() -> tuple[tuple[str, str, Callable[[Request], JsonResponse]], ...]:
    """Return all authenticated routes owned by this plugin namespace."""
    return (
        ("GET", f"{API_PREFIX}/status", handle_status),
        ("GET", f"{API_PREFIX}/catalog", handle_catalog),
        ("GET", f"{API_PREFIX}/snapshot", handle_snapshot),
        ("GET", f"{API_PREFIX}/events", handle_events),
        (
            "GET",
            f"{API_PREFIX}/entities/{{entity_type}}/{{entity_id}}",
            handle_entity,
        ),
        ("POST", f"{API_PREFIX}/commands", handle_commands),
        ("POST", f"{API_PREFIX}/reconcile", handle_reconcile),
    )


def _respond(operation: Callable[[], dict[str, Any]]) -> JsonResponse:
    try:
        return JsonResponse(200, operation())
    except ConflictError as exc:
        return JsonResponse(
            409,
            {
                "error": {
                    "code": "version_conflict",
                    "message": "the expected stream version is stale",
                    "expected_version": exc.expected_version,
                    "current_version": exc.current_version,
                }
            },
        )
    except CommandIdConflictError:
        return _error(409, "command_id_conflict", "command_id was reused")
    except AuthorizationError as exc:
        return _error(403, "authorization_error", str(exc))
    except NotFoundError as exc:
        return _error(404, "not_found", str(exc))
    except AmbiguousEntityError:
        return _error(
            400,
            "validation_error",
            "realm_id is required for an ambiguous entity",
        )
    except ValidationError as exc:
        return _error(400, "validation_error", str(exc))
    except PydanticValidationError:
        return _error(400, "validation_error", "request validation failed")
    except ValueError:
        return _error(400, "validation_error", "request validation failed")
    except Exception as exc:  # pragma: no cover - last-resort secret-safe boundary
        correlation_id = uuid4().hex
        logger.error(
            "M.U.S.E Universe API failure correlation_id=%s exception_type=%s",
            correlation_id,
            type(exc).__name__,
        )
        return JsonResponse(
            500,
            {
                "error": {
                    "code": "internal_error",
                    "message": "an internal error occurred",
                    "correlation_id": correlation_id,
                }
            },
        )


def _error(status: int, code: str, message: str) -> JsonResponse:
    return JsonResponse(
        status,
        {"error": {"code": code, "message": message}},
    )


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ValidationError(f"{field} keys must be strings")
    return dict(value)


def _reject_unknown_fields(
    value: Mapping[str, Any],
    allowed: frozenset[str],
    field: str,
) -> None:
    if not set(value).issubset(allowed):
        raise ValidationError(f"{field} contains unsupported fields")


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value.strip()


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _non_negative_integer(
    value: object,
    field: str,
    *,
    default: int | None = None,
) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.isdecimal():
            raise ValidationError(f"{field} must be a non-negative integer")
        value = int(stripped)
    if type(value) is not int or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{field} must be a boolean")
    return value


def _jsonable(value: object) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value
