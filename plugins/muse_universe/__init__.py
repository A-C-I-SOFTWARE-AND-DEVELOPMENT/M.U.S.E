"""Shared contracts and local event store for MUSE Universe."""

from .models import (
    AuthorizationDecision,
    CommandResult,
    ProvenanceRecord,
    UniverseCommand,
    UniverseEvent,
)
from .store import CommandIdConflictError, ConflictError, UniverseStore

__all__ = [
    "AuthorizationDecision",
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
