from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .validation import validate_finite_numbers


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _immutable(*args: object, **kwargs: object) -> None:
    raise TypeError("frozen mapping does not support mutation")


class FrozenDict(dict[str, Any]):
    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    setdefault = _immutable
    update = _immutable

    def __ior__(self, value: Any, /) -> Self:
        raise TypeError("frozen mapping does not support mutation")

    def popitem(self) -> tuple[str, Any]:
        raise TypeError("frozen mapping does not support mutation")


def deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenDict({key: deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(deep_freeze(item) for item in value)
    return value


class AuthorizationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: str
    scopes: tuple[str, ...] = ()
    owner_gate: str = "not_required"


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    evidence: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    signature: str | None = None

    @field_validator("evidence", mode="after")
    @classmethod
    def _freeze_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return deep_freeze(value)


class UniverseCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    command_id: str
    command_type: str
    realm_id: str
    actor_id: str
    stream_type: str
    stream_id: str
    expected_version: int = Field(ge=0)
    payload: dict[str, Any]
    authorization: AuthorizationDecision
    provenance: ProvenanceRecord
    causation_id: str
    correlation_id: str
    simulation: bool = False

    @field_validator("payload", mode="after")
    @classmethod
    def _freeze_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_finite_numbers(value, path="payload")
        return deep_freeze(value)


class UniverseEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    event_id: str
    schema_version: int = 1
    event_type: str
    realm_id: str
    actor_id: str
    stream_type: str
    stream_id: str
    stream_version: int
    authorization: AuthorizationDecision
    causation_id: str
    correlation_id: str
    occurred_at: str
    payload: dict[str, Any]
    provenance: ProvenanceRecord
    simulation: bool
    rollback: dict[str, Any]

    @field_validator("payload", "rollback", mode="after")
    @classmethod
    def _freeze_mappings(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_finite_numbers(value, path="event")
        return deep_freeze(value)


class CommandResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: UniverseEvent
    entity: dict[str, Any]
    idempotent_replay: bool = False

    @field_validator("entity", mode="after")
    @classmethod
    def _freeze_entity(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_finite_numbers(value, path="entity")
        return deep_freeze(value)

    @property
    def event_id(self) -> str:
        return self.event.event_id

    @property
    def stream_version(self) -> int:
        return self.event.stream_version
