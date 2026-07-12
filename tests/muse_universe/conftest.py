from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from hermes_cli.approval_grants import ApprovalState, BoundApproval

from plugins.muse_universe.models import (
    AuthorizationDecision,
    ProvenanceRecord,
    UniverseCommand,
)
from plugins.muse_universe.store import UniverseStore

if TYPE_CHECKING:
    from plugins.muse_universe.service import UniverseService


class RecordingApprovalVerifier:
    def __init__(self) -> None:
        self.allowed: set[str] = set()
        self.calls: list[dict[str, object]] = []

    def allow(self, approval_id: str) -> None:
        self.allowed.add(approval_id)

    def validate_and_consume_approval(
        self,
        approval_id: str,
        actor_id: str,
        action: str,
        realm_id: str,
        correlation_id: str,
        subject: object,
        *,
        db_path: Path | str | None = None,
    ) -> BoundApproval:
        del db_path
        if approval_id not in self.allowed:
            raise RuntimeError("approval denied")
        self.calls.append(
            {
                "approval_id": approval_id,
                "actor_id": actor_id,
                "action": action,
                "realm_id": realm_id,
                "correlation_id": correlation_id,
                "subject": subject,
            }
        )
        return BoundApproval(
            approval_id=approval_id,
            actor_id=actor_id,
            action=action,
            realm_id=realm_id,
            correlation_id=correlation_id,
            subject_hash="test-subject-hash",
            state=ApprovalState.CONSUMED,
            issued_at=1.0,
            expires_at=3.0,
            decided_at=1.5,
            decided_by="test-owner",
            consumed_at=2.0,
        )


@pytest.fixture
def approval_verifier() -> RecordingApprovalVerifier:
    return RecordingApprovalVerifier()


@pytest.fixture
def service(
    tmp_path: Path, approval_verifier: RecordingApprovalVerifier
) -> UniverseService:
    from plugins.muse_universe.service import UniverseService

    return UniverseService(
        UniverseStore(tmp_path / "universe.db"),
        approval_verifier=approval_verifier,
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
