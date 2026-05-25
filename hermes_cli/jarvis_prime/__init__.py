"""JARVIS Prime runtime package (Wave 0 foundation).

This package will hold the JARVIS Prime runtime modules
(`runtime`, `router`, `modes`, `gates`, `owner_auth`, `memory`,
`research`, `epistemics`, `self_update`, `awareness`, `tick`).

Wave 0 only ships the standard `WorkPacket` data contract.
Everything else lands in later waves; see
`docs/jarvis-prime-wave-plan.md`.

Import rule (Wave 0): stdlib-only and no heavy Hermes subsystems at
import time. Code that violates this rule belongs in a later wave.
"""

from .work_packet import (
    VALID_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)

__all__ = [
    "VALID_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
]
