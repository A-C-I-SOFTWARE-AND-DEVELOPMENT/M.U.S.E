from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from plugins.muse_universe.models import (
    AuthorizationDecision,
    ProvenanceRecord,
    UniverseCommand,
)


@pytest.fixture
def command_factory() -> Callable[..., UniverseCommand]:
    def command(**overrides: object) -> UniverseCommand:
        data: dict[str, Any] = {
            "command_id": "cmd_1",
            "command_type": "realm.create",
            "realm_id": "rlm_local",
            "actor_id": "ply_owner",
            "stream_type": "realm",
            "stream_id": "rlm_local",
            "expected_version": 0,
            "payload": {"name": "Local Realm", "mode": "local"},
            "authorization": AuthorizationDecision(
                allowed=True,
                reason="local owner",
                scopes=("realm:write",),
            ),
            "provenance": ProvenanceRecord(source="owner", confidence=1.0),
            "causation_id": "cause_1",
            "correlation_id": "corr_1",
        }
        data.update(overrides)
        return UniverseCommand(**data)

    return command
