"""Provenance-bearing memory event (MEM-1).

A `MemoryEvent` is the raw unit recorded before anything is considered for
durable memory. It carries the provenance the curator/owner gate need to decide
whether content may be promoted: where it came from, how trusted it is, and
whether the owner approved it. Untrusted/injected content can be logged but must
never be auto-promoted (see `curator_bridge`).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# Trust ranking — higher is more trusted. Tool/external content is "untrusted"
# by default so prompt-injection in tool output cannot self-promote to memory.
TRUST_RANK: dict[str, int] = {
    "untrusted": 0,
    "tool": 1,
    "trusted": 2,
    "owner": 3,
}


@dataclass(frozen=True)
class MemoryEvent:
    content: str
    source: str  # e.g. "tool:web_search", "user", "session_summary"
    trust_level: str = "untrusted"
    originating_tool: Optional[str] = None
    permissions: tuple[str, ...] = ()
    user_approval_state: str = "unreviewed"  # unreviewed | approved | rejected
    timestamp: float = field(default_factory=time.time)
    metadata: tuple[tuple[str, Any], ...] = ()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8", "replace")).hexdigest()

    @property
    def trust_rank(self) -> int:
        return TRUST_RANK.get(self.trust_level, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "content": self.content,
            "source": self.source,
            "trust_level": self.trust_level,
            "originating_tool": self.originating_tool,
            "permissions": list(self.permissions),
            "user_approval_state": self.user_approval_state,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
