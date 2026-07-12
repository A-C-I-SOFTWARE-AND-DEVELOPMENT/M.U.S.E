from __future__ import annotations

from typing import Any

from .models import UniverseEvent


def reduce_entity(
    current: dict[str, Any] | None, event: UniverseEvent
) -> dict[str, Any]:
    entity = {
        **(current or {}),
        **event.payload,
        "id": event.stream_id,
        "entity_type": event.stream_type,
        "realm_id": event.realm_id,
        "version": event.stream_version,
        "updated_at": event.occurred_at,
        "simulation": event.simulation,
    }
    if event.event_type.endswith(".deleted"):
        entity["deleted"] = True
    return entity
