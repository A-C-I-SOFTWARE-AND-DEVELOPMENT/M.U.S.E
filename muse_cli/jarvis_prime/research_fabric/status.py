"""Observability — a single status view over the research fabric.

Aggregates the hash-chained ledger (event counts), the current champion, the
active charter, the diversity-archive size, and chain integrity into one dict for
the CLI / cockpit. Read-only; never mutates state.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .archive.store import ArchiveStore
from .pipeline import FabricContext


def fabric_status(ctx: FabricContext, archive: ArchiveStore) -> dict[str, Any]:
    records = ctx.ledger.read_all()
    kinds = Counter(r.kind for r in records)
    champ = ctx.champions.current()
    active = ctx.charters.active()
    chain = ctx.ledger.verify_chain()
    store_chain = ctx.store.verify_chain()
    return {
        "ledger_length": len(records),
        "ledger_events": dict(sorted(kinds.items())),
        "ledger_chain_ok": chain.ok,
        "store_chain_ok": store_chain.ok,
        "champion": champ.to_dict() if champ else None,
        "active_charter": active.to_dict() if active else None,
        "charter_count": len(ctx.charters.charters),
        "archive_members": len(archive.members()),
        "autonomy_active": active is not None,
    }


__all__ = ["fabric_status"]
