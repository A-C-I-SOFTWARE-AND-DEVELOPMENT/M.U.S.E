"""JARVIS Prime runtime package.

Wave 0 only exposes the standard ``WorkPacket`` model and its validation
helpers. Other runtime surfaces (modes, router, gates, owner_auth,
memory, research, epistemics, self_update, awareness, tick) are
intentionally not present yet — they belong to Wave 1 feature lanes.

Imports here must stay stdlib-only so that importing
``hermes_cli.jarvis_prime`` never pulls in heavy Hermes subsystems and
remains safe on Termux.
"""

from .work_packet import (
    RISK_CLASSES,
    REQUIRED_FIELDS,
    WorkPacket,
    WorkPacketValidationFinding,
)

__all__ = [
    "RISK_CLASSES",
    "REQUIRED_FIELDS",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
