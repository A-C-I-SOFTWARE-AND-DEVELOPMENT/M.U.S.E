"""Layered memory (MEM-1) — provenance + owner-gated promotion.

Adds layers AROUND the existing `agent/memory_provider.py` MemoryProvider system
and `agent/curator.py`; it does not replace any backend. Layers:

* raw event log (`raw_event_log`) — append-only, provenance-bearing, gitignored.
* curator bridge (`curator_bridge`) — owner-gated promotion via the existing
  `ProposalBook` (`ProposalKind.MEMORY_PROMOTION`); untrusted content never
  auto-promotes.
* selective retrieval (`retrieval`) — trust/confidence filter over recalled
  entries so low-trust content isn't dumped into the prompt.
"""

from __future__ import annotations

from .curator_bridge import consider, propose_promotion, should_auto_promote
from .provenance import TRUST_RANK, MemoryEvent
from .raw_event_log import read_all, record
from .retrieval import filter_entries

__all__ = [
    "MemoryEvent",
    "TRUST_RANK",
    "record",
    "read_all",
    "filter_entries",
    "should_auto_promote",
    "propose_promotion",
    "consider",
]
