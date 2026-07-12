from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class CommandResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: UniverseEvent
    entity: dict[str, Any]
    idempotent_replay: bool = False

    @property
    def event_id(self) -> str:
        return self.event.event_id

    @property
    def stream_version(self) -> int:
        return self.event.stream_version
