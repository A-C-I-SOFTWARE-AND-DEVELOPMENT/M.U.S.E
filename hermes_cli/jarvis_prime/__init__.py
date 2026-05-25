"""JARVIS Prime runtime package.

Wave 0 only exposes the standard :class:`WorkPacket` model and its
validation finding type. Later waves add the runtime modules
(``modes``, ``router``, ``gates``, ``owner_auth``, ``memory``,
``research``, ``epistemics``, ``self_update``, ``awareness``,
``tick``, ``runtime``) on dedicated feature branches as defined in
``docs/jarvis-prime-wave-plan.md``.

Import-time rule: this package is stdlib-only. Do not import heavy
Hermes subsystems here.
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
