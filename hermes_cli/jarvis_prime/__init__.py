"""JARVIS Prime runtime package.

Wave 0 foundation. This package will, over later waves, host the JARVIS
Prime runtime, mode router, gates, owner-auth, memory bridge, research,
epistemics, self-update, awareness, and tick modules. The only thing
exported at Wave 0 is the standard :class:`WorkPacket` model so other
layers can already speak the canonical work-packet schema.

Import-time policy: this package must stay stdlib-only and must not
import heavy Hermes subsystems, perform network IO, or read the
filesystem at import time.
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
