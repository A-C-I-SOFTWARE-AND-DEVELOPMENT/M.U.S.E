"""JARVIS Prime runtime package.

Wave 0 scope: foundation only. This package exposes the WorkPacket data
model and its validation finding type. Later waves will add modes, router,
gates, owner auth, memory, research, epistemics, self-update, awareness,
and tick.

Imports here must remain stdlib-only at import time to preserve Termux
compatibility and to avoid pulling heavy Hermes subsystems into the
foundation layer.
"""

from hermes_cli.jarvis_prime.work_packet import (
    RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)

__all__ = [
    "RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
