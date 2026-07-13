"""Authenticated Supabase adapter for authoritative network realms.

The adapter forwards only command intent to the Edge boundary. Actor identity,
membership scopes, event metadata, and provenance are always resolved by the
remote authority from the caller's user JWT.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
import re
from types import TracebackType
from typing import Any, Protocol, Self
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError as PydanticValidationError

from .authorization import AuthorizationError
from .models import CommandResult, UniverseCommand, UniverseEvent
from .service import ValidationError
from .store import CommandIdConflictError, ConflictError


DEFAULT_TIMEOUT_SECONDS = 10.0
MIN_TIMEOUT_SECONDS = 0.1
MAX_TIMEOUT_SECONDS = 30.0
MAX_EVENT_PAGE_SIZE = 500
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
_HEADER_PATTERN = re.compile(r"(?i)(authorization|apikey)\s*:\s*\S+")
_COMMAND_FIELDS = (
    "command_id",
    "command_type",
    "realm_id",
    "stream_id",
    "expected_version",
    "payload",
    "causation_id",
    "correlation_id",
    "approval_id",
    "simulation",
)
_REJECTED_MAPPING_FIELDS = frozenset(
    {"owner_authorization", "owner_phrase", "roles", "scopes"}
)


class RemoteUniverseError(RuntimeError):
    """Raised for a valid remote response that has no local domain analogue."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "remote_error",
        status: int | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.code = code
        self.status = status
        self.correlation_id = correlation_id
        super().__init__(_safe_message(message))


class RemoteUnavailableError(RemoteUniverseError):
    """Raised when the selected network authority cannot be reached safely."""


class RemoteAuthorizationError(AuthorizationError):
    """Raised before transport when a project/service credential is supplied."""


class RemoteConflictError(RemoteUniverseError):
    """Raised for a conflict response that omits usable stream versions."""


class AuthoritySelectionError(ValueError):
    """Raised when a caller tries to use a local adapter for a network realm."""


@dataclass(frozen=True)
class RemoteEventPage:
    events: tuple[UniverseEvent, ...]
    cursor: int
    realm_version: int
    server_time: str


@dataclass(frozen=True)
class RemoteSnapshot:
    snapshot: dict[str, list[dict[str, Any]]]
    cursor: int
    realm_version: int
    server_time: str


class LocalUniverseFallback(Protocol):
    """Explicit adapter used only for its separately selected local realm."""

    def execute(self, command: UniverseCommand) -> CommandResult: ...

    def events_since(
        self, realm_id: str, cursor: int, *, limit: int = 200
    ) -> RemoteEventPage: ...

    def snapshot(self, realm_id: str) -> RemoteSnapshot: ...


class SupabaseUniverseAdapter:
    """Bounded user-token client for the M.U.S.E Supabase Edge contract."""

    def __init__(
        self,
        project_url: str,
        user_token: str,
        realm_id: str | None = None,
        *,
        anon_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
        client: httpx.Client | None = None,
        local_fallback: LocalUniverseFallback | None = None,
        local_adapter: Any | None = None,
        local_realm_id: str | None = None,
    ) -> None:
        self._project_url = _validated_project_url(project_url)
        self._edge_base = (
            self._project_url
            if self._project_url.endswith("/functions/v1/muse-universe")
            else f"{self._project_url}/functions/v1/muse-universe"
        )
        self._credential_error = _is_service_role_credential(user_token)
        self._user_token = (
            user_token
            if self._credential_error
            else _validated_client_token(user_token, "user token")
        )
        self._anon_key = (
            None
            if anon_key is None
            else _validated_client_token(anon_key, "anonymous key")
        )
        self._timeout = _validated_timeout(timeout)
        if http_client is not None and client is not None:
            raise ValueError("http_client and client are aliases; provide only one")
        if local_fallback is not None and local_adapter is not None:
            raise ValueError(
                "local_fallback and local_adapter are aliases; provide only one"
            )
        selected_local = local_fallback if local_fallback is not None else local_adapter
        if (selected_local is None) != (local_realm_id is None):
            raise ValueError(
                "a local adapter and local_realm_id must be configured together"
            )
        self._local_fallback = local_fallback
        self._legacy_local_adapter = local_adapter
        self._local_realm_id = local_realm_id
        self._fixed_realm_id = (
            None if realm_id is None else _opaque_id(realm_id, "realm_id")
        )
        supplied_client = http_client if http_client is not None else client
        self._client = supplied_client or httpx.Client(timeout=self._timeout)
        self._owns_client = supplied_client is None
        self._closed = False

    def __enter__(self) -> Self:
        if self._closed:
            raise RuntimeError("adapter is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def close(self) -> None:
        if not self._closed and self._owns_client:
            self._client.close()
        self._closed = True

    def execute(
        self,
        command: UniverseCommand | Mapping[str, Any] | str,
        payload: Mapping[str, Any] | None = None,
        expected_version: int | None = None,
        command_id: str | None = None,
        *,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        approval_id: str | None = None,
        simulation: bool = False,
    ) -> CommandResult | Mapping[str, Any]:
        if isinstance(command, str):
            if self._fixed_realm_id is None:
                raise TypeError(
                    "the command-type form requires a realm_id selected at construction"
                )
            if payload is None or expected_version is None or command_id is None:
                raise ValidationError(
                    "payload, expected_version, and command_id are required"
                )
            legacy_body: dict[str, Any] = {
                "command_id": _opaque_id(command_id, "command_id"),
                "command_type": _opaque_id(command, "command_type"),
                "realm_id": self._fixed_realm_id,
                "expected_version": _bounded_integer(
                    expected_version, "expected_version", minimum=0
                ),
                "payload": dict(payload),
                "simulation": simulation,
            }
            for field, value in (
                ("correlation_id", correlation_id),
                ("causation_id", causation_id),
                ("approval_id", approval_id),
            ):
                if value is not None:
                    legacy_body[field] = _opaque_id(value, field)
            return self._request(
                "POST",
                "/commands",
                json_body=legacy_body,
                expected_version=expected_version,
                command_id=command_id,
            )
        if any(
            value is not None
            for value in (payload, expected_version, command_id, correlation_id,
                          causation_id, approval_id)
        ) or simulation:
            raise TypeError(
                "extra command arguments are supported only by the command-type form"
            )
        body = _command_intent(command)
        realm_id = str(body["realm_id"])
        try:
            payload = self._request(
                "POST",
                "/commands",
                json_body=body,
                expected_version=int(body["expected_version"]),
                command_id=str(body["command_id"]),
            )
        except RemoteUnavailableError:
            if self._may_fallback(realm_id) and isinstance(command, UniverseCommand):
                return self._local_fallback.execute(command)  # type: ignore[union-attr]
            raise
        try:
            return CommandResult.model_validate(payload)
        except PydanticValidationError as exc:
            raise RemoteUniverseError(
                "remote universe authority returned an invalid command result",
                code="invalid_remote_response",
            ) from exc

    def events_since(
        self,
        realm_id: str | int,
        cursor: int | None = None,
        *,
        limit: int = 200,
    ) -> RemoteEventPage | tuple[list[dict[str, Any]], int]:
        if cursor is None:
            if self._fixed_realm_id is None:
                raise TypeError("realm_id and cursor are required")
            legacy_cursor = _bounded_integer(realm_id, "cursor", minimum=0)
            bounded_limit = _bounded_integer(
                limit, "limit", minimum=1, maximum=MAX_EVENT_PAGE_SIZE
            )
            payload = self._request(
                "GET",
                "/events",
                params={
                    "realm_id": self._fixed_realm_id,
                    "cursor": legacy_cursor,
                    "limit": bounded_limit,
                },
            )
            body = _object(payload, "event page")
            events = body.get("events")
            returned_cursor = _response_integer(body.get("cursor"), "cursor")
            if not isinstance(events, list) or not all(
                isinstance(event, Mapping) for event in events
            ):
                raise RemoteUniverseError(
                    "remote universe authority returned an invalid event page",
                    code="invalid_remote_response",
                )
            return [dict(event) for event in events], returned_cursor
        realm_id = _opaque_id(realm_id, "realm_id")
        cursor = _bounded_integer(cursor, "cursor", minimum=0)
        limit = _bounded_integer(
            limit,
            "limit",
            minimum=1,
            maximum=MAX_EVENT_PAGE_SIZE,
        )
        try:
            payload = self._request(
                "GET",
                "/events",
                params={"realm_id": realm_id, "since": cursor, "limit": limit},
            )
        except RemoteUnavailableError:
            if self._may_fallback(realm_id):
                return self._local_fallback.events_since(  # type: ignore[union-attr]
                    realm_id, cursor, limit=limit
                )
            raise
        return _event_page(payload, minimum_cursor=cursor)

    def snapshot(
        self, realm_id: str | None = None
    ) -> RemoteSnapshot | Mapping[str, Any]:
        if realm_id is None:
            if self._fixed_realm_id is None:
                raise TypeError("realm_id is required")
            payload = self._request(
                "GET",
                "/snapshot",
                params={"realm_id": self._fixed_realm_id},
            )
            return _object(payload, "snapshot")
        realm_id = _opaque_id(realm_id, "realm_id")
        try:
            payload = self._request(
                "GET",
                "/snapshot",
                params={"realm_id": realm_id},
            )
        except RemoteUnavailableError:
            if self._may_fallback(realm_id):
                return self._local_fallback.snapshot(realm_id)  # type: ignore[union-attr]
            raise
        return _snapshot(payload)

    def local_snapshot(
        self, actor_id: str | None, realm_id: str
    ) -> Mapping[str, Any]:
        realm_id = _opaque_id(realm_id, "realm_id")
        if (
            self._legacy_local_adapter is None
            or self._local_realm_id is None
            or realm_id != self._local_realm_id
        ):
            raise AuthoritySelectionError(
                "local authority is available only for the explicitly selected local realm"
            )
        result = self._legacy_local_adapter.snapshot(actor_id, realm_id)
        if not isinstance(result, Mapping):
            raise RemoteUniverseError(
                "local universe adapter returned an invalid snapshot",
                code="invalid_local_response",
            )
        return result

    def _may_fallback(self, realm_id: str) -> bool:
        return (
            self._local_fallback is not None
            and self._local_realm_id is not None
            and realm_id == self._local_realm_id
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        expected_version: int | None = None,
        command_id: str | None = None,
    ) -> Any:
        if self._closed:
            raise RuntimeError("adapter is closed")
        if self._credential_error:
            raise RemoteAuthorizationError(
                "a caller user token is required; project/service credentials are refused"
            )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._user_token}",
            "Content-Type": "application/json",
            "User-Agent": "hermes-agent/muse-universe",
        }
        if self._anon_key is not None:
            headers["apikey"] = self._anon_key
        try:
            response = self._client.request(
                method,
                f"{self._edge_base}{path}",
                headers=headers,
                params=dict(params or {}),
                json=dict(json_body) if json_body is not None else None,
                timeout=self._timeout,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise RemoteUnavailableError(
                "remote universe authority is unavailable",
                code="remote_unavailable",
            ) from exc

        if len(response.content) > MAX_RESPONSE_BYTES:
            raise RemoteUniverseError(
                "remote universe authority returned an oversized response",
                code="response_too_large",
                status=response.status_code,
            )
        try:
            payload = response.json() if response.content else None
        except ValueError as exc:
            raise RemoteUniverseError(
                "remote universe authority returned invalid JSON",
                code="invalid_remote_response",
                status=response.status_code,
            ) from exc
        if response.status_code >= 400:
            _raise_remote_error(
                response.status_code,
                payload,
                expected_version=expected_version,
                command_id=command_id,
            )
        return payload


def _command_intent(
    command: UniverseCommand | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(command, UniverseCommand):
        source = command.model_dump(mode="json")
    elif isinstance(command, Mapping):
        source = dict(command)
        rejected = sorted(_REJECTED_MAPPING_FIELDS.intersection(source))
        if rejected:
            raise ValidationError(
                f"server-authoritative command fields are not accepted: {', '.join(rejected)}"
            )
    else:
        raise TypeError("command must be a UniverseCommand or mapping")
    missing = [field for field in _COMMAND_FIELDS[:6] if field not in source]
    if missing:
        raise ValidationError(f"missing command fields: {', '.join(missing)}")
    intent = {field: source[field] for field in _COMMAND_FIELDS if field in source}
    for field in ("command_id", "command_type", "realm_id", "stream_id"):
        intent[field] = _opaque_id(intent[field], field)
    intent["expected_version"] = _bounded_integer(
        intent["expected_version"], "expected_version", minimum=0
    )
    if not isinstance(intent["payload"], Mapping):
        raise ValidationError("payload must be a mapping")
    for field in ("causation_id", "correlation_id", "approval_id"):
        if field in intent and intent[field] is not None:
            intent[field] = _opaque_id(intent[field], field)
    if "simulation" in intent and type(intent["simulation"]) is not bool:
        raise ValidationError("simulation must be a boolean")
    try:
        return json.loads(
            json.dumps(
                intent,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("command intent must contain finite JSON values") from exc


def _event_page(payload: Any, *, minimum_cursor: int) -> RemoteEventPage:
    body = _object(payload, "event page")
    raw_events = body.get("events")
    if not isinstance(raw_events, list):
        raise RemoteUniverseError(
            "remote universe authority returned an invalid event page",
            code="invalid_remote_response",
        )
    try:
        events = tuple(UniverseEvent.model_validate(event) for event in raw_events)
    except PydanticValidationError as exc:
        raise RemoteUniverseError(
            "remote universe authority returned invalid events",
            code="invalid_remote_response",
        ) from exc
    cursor = _response_integer(body.get("cursor"), "cursor")
    realm_version = _response_integer(body.get("realm_version"), "realm_version")
    server_time = body.get("server_time")
    if cursor < minimum_cursor or not isinstance(server_time, str) or not server_time:
        raise RemoteUniverseError(
            "remote universe authority returned invalid cursor metadata",
            code="invalid_remote_response",
        )
    if events and (events[-1].sequence > cursor or events[0].sequence <= minimum_cursor):
        raise RemoteUniverseError(
            "remote universe authority returned inconsistent event cursors",
            code="invalid_remote_response",
        )
    return RemoteEventPage(events, cursor, realm_version, server_time)


def _snapshot(payload: Any) -> RemoteSnapshot:
    body = _object(payload, "snapshot")
    raw_snapshot = body.get("snapshot")
    if not isinstance(raw_snapshot, Mapping):
        raise RemoteUniverseError(
            "remote universe authority returned an invalid snapshot",
            code="invalid_remote_response",
        )
    snapshot: dict[str, list[dict[str, Any]]] = {}
    for group, entities in raw_snapshot.items():
        if not isinstance(group, str) or not isinstance(entities, list):
            raise RemoteUniverseError(
                "remote universe authority returned invalid projection groups",
                code="invalid_remote_response",
            )
        if not all(isinstance(entity, Mapping) for entity in entities):
            raise RemoteUniverseError(
                "remote universe authority returned invalid projections",
                code="invalid_remote_response",
            )
        snapshot[group] = [dict(entity) for entity in entities]
    cursor = _response_integer(body.get("cursor"), "cursor")
    realm_version = _response_integer(body.get("realm_version"), "realm_version")
    server_time = body.get("server_time")
    if not isinstance(server_time, str) or not server_time:
        raise RemoteUniverseError(
            "remote universe authority returned invalid snapshot metadata",
            code="invalid_remote_response",
        )
    return RemoteSnapshot(snapshot, cursor, realm_version, server_time)


def _raise_remote_error(
    status: int,
    payload: Any,
    *,
    expected_version: int | None,
    command_id: str | None,
) -> None:
    body = payload if isinstance(payload, Mapping) else {}
    raw_error = body.get("error")
    if isinstance(raw_error, Mapping):
        error = raw_error
        code = str(error.get("code", "remote_error"))
        message = _safe_message(str(error.get("message", "request rejected")))
    elif isinstance(raw_error, str):
        error = {}
        code = raw_error
        message = "request rejected"
    else:
        error = body
        code = str(error.get("code", "remote_error"))
        message = _safe_message(str(error.get("message", "request rejected")))
    correlation_id = body.get("correlation_id")
    correlation = correlation_id if isinstance(correlation_id, str) else None
    if status == 409 and code in {
        "command_id_conflict",
        "MUSE_COMMAND_ID_CONFLICT",
    } and command_id:
        raise CommandIdConflictError(command_id)
    if status == 409:
        current = error.get("current_version")
        expected = error.get("expected_version", expected_version)
        if _is_exact_non_negative_integer(current) and _is_exact_non_negative_integer(
            expected
        ):
            raise ConflictError(int(expected), int(current))
        raise RemoteConflictError(
            message,
            code=code,
            status=status,
            correlation_id=correlation,
        )
    if status in {401, 403}:
        raise RemoteAuthorizationError(message)
    if status in {400, 413, 415, 422}:
        raise ValidationError(message)
    if status >= 500:
        raise RemoteUnavailableError(
            "remote universe authority is unavailable",
            code=code,
            status=status,
            correlation_id=correlation,
        )
    raise RemoteUniverseError(
        message,
        code=code,
        status=status,
        correlation_id=correlation,
    )


def _validated_project_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("project_url is required")
    parsed = urlparse(value.strip())
    is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise ValueError("project_url must use HTTPS except for loopback development")
    if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("project_url must be an origin without credentials or query data")
    return value.strip().rstrip("/")


def _validated_client_token(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 16384:
        raise ValueError(f"{field} is required and must be bounded")
    if any(character.isspace() for character in value):
        raise ValueError(f"{field} must not contain whitespace")
    if _is_service_role_credential(value):
        raise ValueError(f"{field} must not be a service-role credential")
    return value


def _is_service_role_credential(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    if lowered.startswith("sb_secret_") or lowered.startswith("service_role"):
        return True
    return _unverified_jwt_claims(value).get("role") == "service_role"


def _unverified_jwt_claims(value: str) -> Mapping[str, Any]:
    parts = value.split(".")
    if len(parts) != 3:
        return {}
    try:
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _validated_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout must be a finite number of seconds")
    timeout = float(value)
    if (
        not math.isfinite(timeout)
        or timeout < MIN_TIMEOUT_SECONDS
        or timeout > MAX_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"timeout must be between {MIN_TIMEOUT_SECONDS} and "
            f"{MAX_TIMEOUT_SECONDS} seconds"
        )
    return timeout


def _opaque_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value
    ):
        raise ValidationError(f"{field} must be an opaque identifier")
    return value


def _bounded_integer(
    value: object,
    field: str,
    *,
    minimum: int,
    maximum: int = 2**53 - 1,
) -> int:
    if not _is_exact_non_negative_integer(value):
        raise ValidationError(f"{field} must be an exact integer")
    result = int(value)
    if result < minimum or result > maximum:
        raise ValidationError(f"{field} is outside the supported range")
    return result


def _response_integer(value: object, field: str) -> int:
    if not _is_exact_non_negative_integer(value):
        raise RemoteUniverseError(
            f"remote universe authority returned an invalid {field}",
            code="invalid_remote_response",
        )
    return int(value)


def _is_exact_non_negative_integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= 2**53 - 1


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RemoteUniverseError(
            f"remote universe authority returned an invalid {label}",
            code="invalid_remote_response",
        )
    return value


def _safe_message(value: str) -> str:
    scrubbed = _HEADER_PATTERN.sub("***REDACTED***", value)
    scrubbed = _JWT_PATTERN.sub("***REDACTED***", scrubbed)
    return scrubbed[:300] or "request rejected"
