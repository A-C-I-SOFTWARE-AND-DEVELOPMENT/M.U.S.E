"""Shared contracts and local event store for MUSE Universe."""

from .models import (
    AuthorizationDecision,
    CommandResult,
    ProvenanceRecord,
    UniverseCommand,
    UniverseEvent,
)
from .store import (
    AmbiguousEntityError,
    CommandIdConflictError,
    ConflictError,
    UniverseStore,
)

__all__ = [
    "AuthorizationDecision",
    "AmbiguousEntityError",
    "CommandIdConflictError",
    "CommandResult",
    "ConflictError",
    "ProvenanceRecord",
    "UniverseCommand",
    "UniverseEvent",
    "UniverseStore",
]


def register(ctx: object) -> None:
    """Expose a plugin entry point without registering later-task features."""
