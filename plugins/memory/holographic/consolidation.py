"""Offline memory consolidation — the longevity write-path.

Recall makes memory *findable*; consolidation keeps it *durable and clean*.
This pass implements the AUDN-style write-path the 2026 agent-memory work
converges on (Add already happens on write; here we Update/merge, mark
contradictions, promote, and selectively forget):

* **Merge** near-duplicate facts (keep the higher-trust row, sum access
  counts, union tags) so the store doesn't accrete restatements.
* **Mark contradictions** (via the existing HRR ``contradict`` detector) by
  demoting the weaker side to the short tier so it fades — never a hard delete.
* **Promote** short-tier facts to the long tier when they prove important or
  are recalled often (mirrors the Memory Tree's ``promote_to_durable``).
* **Forget** only short-tier, low-importance, low-trust, stale facts — never a
  long-tier or high-trust fact. Dry-run by default; deletions need ``apply``.

Pure-stdlib and dependency-light: similarity uses the stored embeddings when
present, else falls back to token overlap, so it runs even without numpy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Defaults (days / thresholds). Conservative on the destructive side.
DEFAULTS = {
    "short_half_life_days": 7,
    "long_half_life_days": 180,
    "promote_access_threshold": 3,        # retrieval_count + helpful_count
    "promote_importance_threshold": 0.75,
    "forget_after_days": 90,              # stale window for short-tier facts
    "forget_trust_floor": 0.3,            # never forget trust >= this
    "forget_importance_ceiling": 0.3,     # never forget importance >= this
    "dedup_threshold": 0.92,              # similarity to treat as a duplicate
}


@dataclass
class ConsolidationReport:
    dry_run: bool = True
    total: int = 0
    merged: list[dict] = field(default_factory=list)        # {keep, drop, similarity}
    contradictions: list[dict] = field(default_factory=list)  # {fact_a, fact_b, score}
    promoted: list[dict] = field(default_factory=list)      # {fact_id, reason}
    forgotten: list[dict] = field(default_factory=list)     # {fact_id, content}

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "total": self.total,
            "merged": self.merged,
            "contradictions": self.contradictions,
            "promoted": self.promoted,
            "forgotten": self.forgotten,
            "summary": {
                "merged": len(self.merged),
                "contradictions": len(self.contradictions),
                "promoted": len(self.promoted),
                "forgotten": len(self.forgotten),
            },
        }


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for word in (text or "").lower().split():
        cleaned = word.strip(".,;:!?\"'()[]{}#@<>")
        if cleaned:
            out.add(cleaned)
    return out


def _similarity(a: dict, b: dict) -> float:
    """Similarity in [0,1]. Uses stored embeddings when both have them
    (same dim), else token Jaccard on content."""
    ea, eb = a.get("embedding"), b.get("embedding")
    if ea and eb and a.get("embedding_dim") == b.get("embedding_dim"):
        try:
            from .embeddings import bytes_to_vector, cosine

            return max(0.0, cosine(bytes_to_vector(ea), bytes_to_vector(eb)))
        except Exception:
            pass
    ta, tb = _tokens(a.get("content", "")), _tokens(b.get("content", ""))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _age_days(row: dict) -> float:
    ts = row.get("last_accessed") or row.get("updated_at") or row.get("created_at")
    if not ts:
        return 0.0
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
    except (ValueError, TypeError):
        return 0.0


def consolidate(store, *, dry_run: bool = True, config: Optional[dict] = None) -> ConsolidationReport:
    """Run a consolidation pass over ``store`` (a holographic ``MemoryStore``).

    Returns a :class:`ConsolidationReport`. With ``dry_run=True`` (default)
    nothing is mutated — the report describes what *would* change.
    """
    cfg = {**DEFAULTS, **(config or {})}
    facts = store.all_facts_for_consolidation()
    report = ConsolidationReport(dry_run=dry_run, total=len(facts))

    by_id = {f["fact_id"]: f for f in facts}
    removed: set[int] = set()

    # 1. Merge near-duplicates (compare within the same category only).
    cats: dict[str, list[dict]] = {}
    for f in facts:
        cats.setdefault(f.get("category") or "general", []).append(f)
    for group in cats.values():
        group = sorted(group, key=lambda r: (r.get("trust_score") or 0.0), reverse=True)
        for i in range(len(group)):
            keep = group[i]
            if keep["fact_id"] in removed:
                continue
            for j in range(i + 1, len(group)):
                drop = group[j]
                if drop["fact_id"] in removed:
                    continue
                sim = _similarity(keep, drop)
                if sim >= cfg["dedup_threshold"]:
                    report.merged.append(
                        {"keep": keep["fact_id"], "drop": drop["fact_id"], "similarity": round(sim, 4)}
                    )
                    removed.add(drop["fact_id"])
                    if not dry_run:
                        store.merge_facts(keep["fact_id"], drop["fact_id"])

    # 2. Mark contradictions — demote the weaker side to the short tier.
    try:
        from .retrieval import FactRetriever

        contradictions = FactRetriever(store).contradict(limit=50)
    except Exception:
        contradictions = []
    for pair in contradictions:
        fa, fb = pair.get("fact_a", {}), pair.get("fact_b", {})
        if fa.get("fact_id") in removed or fb.get("fact_id") in removed:
            continue
        weaker = fa if (fa.get("trust_score") or 0) <= (fb.get("trust_score") or 0) else fb
        report.contradictions.append(
            {
                "fact_a": fa.get("fact_id"),
                "fact_b": fb.get("fact_id"),
                "score": pair.get("contradiction_score"),
                "demoted": weaker.get("fact_id"),
            }
        )
        if not dry_run and weaker.get("fact_id") is not None:
            store.set_memory_tier(int(weaker["fact_id"]), "short")

    # 3. Promote short-tier facts that have proven important / frequently used.
    for f in facts:
        if f["fact_id"] in removed or (f.get("memory_tier") or "short") == "long":
            continue
        access = (f.get("retrieval_count") or 0) + (f.get("helpful_count") or 0)
        importance = f.get("importance")
        importance = 0.5 if importance is None else float(importance)
        if access >= cfg["promote_access_threshold"] or importance >= cfg["promote_importance_threshold"]:
            reason = "access" if access >= cfg["promote_access_threshold"] else "importance"
            report.promoted.append({"fact_id": f["fact_id"], "reason": reason})
            if not dry_run:
                store.set_memory_tier(f["fact_id"], "long")

    # 4. Selectively forget — short tier, low importance, low trust, stale.
    #    Long-tier and high-trust facts are never eligible (safety floor).
    promoted_ids = {p["fact_id"] for p in report.promoted}
    for f in facts:
        fid = f["fact_id"]
        if fid in removed or fid in promoted_ids:
            continue
        if (f.get("memory_tier") or "short") == "long":
            continue
        trust = f.get("trust_score") or 0.0
        importance = f.get("importance")
        importance = 0.5 if importance is None else float(importance)
        if trust >= cfg["forget_trust_floor"] or importance >= cfg["forget_importance_ceiling"]:
            continue
        if _age_days(f) < cfg["forget_after_days"]:
            continue
        report.forgotten.append({"fact_id": fid, "content": (f.get("content") or "")[:120]})
        if not dry_run:
            store.remove_fact(fid)

    return report
