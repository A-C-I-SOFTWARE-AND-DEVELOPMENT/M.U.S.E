"""JARVIS Prime runtime package (Wave 0 foundation).

Wave 0 ships the data foundation only: the standard ``WorkPacket``
model and its validation findings type. Later waves add the runtime,
mode router, gates, owner auth, memory, research, epistemics, self-
update, awareness, and tick subsystems — see
``docs/jarvis-prime-wave-plan.md``.

This package intentionally has zero third-party imports at import
time, so it stays importable on minimal Termux environments.
"""

from hermes_cli.jarvis_prime.work_packet import (
    OWNER_AUTHORIZATION_PHRASE,
    RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)

__all__ = [
    "OWNER_AUTHORIZATION_PHRASE",
    "RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
