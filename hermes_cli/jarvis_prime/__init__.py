"""JARVIS Prime runtime package.

Wave 0 surface: only the standard WorkPacket model is exported. Additional
runtime modules (router, modes, gates, memory, awareness, tick) are
deliberately deferred to later waves to keep this foundation lock minimal
and stdlib-only. See `docs/jarvis-prime-wave-plan.md` for the build plan.
"""

from .work_packet import (
    OWNER_AUTHORIZATION_PHRASE,
    REQUIRED_FIELDS,
    VALID_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)

__all__ = [
    "OWNER_AUTHORIZATION_PHRASE",
    "REQUIRED_FIELDS",
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
