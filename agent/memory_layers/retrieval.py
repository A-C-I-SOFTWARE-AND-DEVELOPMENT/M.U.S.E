"""Selective retrieval filter (MEM-1).

Wraps whatever the configured `MemoryProvider.recall` returns with a
trust/confidence filter so low-trust or low-confidence entries are not injected
into the prompt. Pure functions — no provider coupling, no new vector store.
"""

from __future__ import annotations

from typing import Any, Iterable

from .provenance import TRUST_RANK


def _entry_trust_rank(entry: Any) -> int:
    """Best-effort trust rank for a recalled entry (dict or object)."""
    level = None
    if isinstance(entry, dict):
        level = entry.get("trust_level") or (entry.get("metadata") or {}).get("trust_level")
    else:
        level = getattr(entry, "trust_level", None)
    return TRUST_RANK.get(level or "untrusted", 0)


def _entry_confidence(entry: Any) -> float:
    if isinstance(entry, dict):
        val = entry.get("confidence", entry.get("score", 1.0))
    else:
        val = getattr(entry, "confidence", getattr(entry, "score", 1.0))
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def filter_entries(
    entries: Iterable[Any],
    *,
    min_trust: str = "tool",
    min_confidence: float = 0.0,
) -> list[Any]:
    """Keep only entries meeting the trust floor and confidence threshold.

    Defaults are permissive (``tool``/``0.0``) so this is opt-in stricter. Set
    ``min_trust="trusted"`` to exclude raw tool/untrusted content from prompts.
    """
    floor = TRUST_RANK.get(min_trust, 1)
    kept: list[Any] = []
    for e in entries:
        if _entry_trust_rank(e) < floor:
            continue
        if _entry_confidence(e) < min_confidence:
            continue
        kept.append(e)
    return kept
