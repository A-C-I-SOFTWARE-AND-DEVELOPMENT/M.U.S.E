"""Runtime learning — shadow capture, failure clustering, retrain proposals (§45/§61).

Shadow mode: a specialist observes traffic and its proposals are compared
against the production route/result WITHOUT controlling effects.
Failure clustering turns sanitized failures into prioritized retrain work.

Storage: JSONL append-only, privacy-scrubbed at ingestion (no secrets, no raw
user payloads — only structural metadata + hashes by default).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

FAILURE_CLASSES = (
    "false_positive", "false_negative", "wrong_tool", "wrong_argument",
    "optional_hallucination", "low_confidence", "retrieval_miss",
    "adjacent_domain_confusion", "schema_incompatibility", "verifier_rejection",
)

_SECRET_RX = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']+)", re.I)


def scrub(text: str) -> str:
    return _SECRET_RX.sub("[REDACTED]", text)


@dataclass
class ShadowEvent:
    specialist_id: str
    niche: str
    query_hash: str           # never the raw query by default
    specialist_calls: list[dict]
    production_route: str
    production_result_hash: str
    verifier_passed: Optional[bool]
    confidence: float
    latency_s: float
    failure_class: str = ""
    at: float = field(default_factory=time.time)


class ShadowMonitor:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, ev: ShadowEvent) -> None:
        data = asdict(ev)
        data["specialist_calls"] = json.loads(scrub(json.dumps(data["specialist_calls"])))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def compare(self, specialist_id: str) -> dict[str, Any]:
        """Live-domain performance estimate from shadow traffic (§45)."""
        events = [json.loads(l) for l in open(self.path, encoding="utf-8")
                  if l.strip()] if self.path.exists() else []
        mine = [e for e in events if e["specialist_id"] == specialist_id]
        if not mine:
            return {"specialist_id": specialist_id, "shadow_events": 0}
        agree = sum(1 for e in mine
                    if e["specialist_calls"] and e["verifier_passed"])
        return {
            "specialist_id": specialist_id,
            "shadow_events": len(mine),
            "verified_call_rate": agree / len(mine),
            "mean_confidence": sum(e["confidence"] for e in mine) / len(mine),
            "mean_latency_s": sum(e["latency_s"] for e in mine) / len(mine),
        }


def cluster_failures(events: list[dict]) -> list[dict[str, Any]]:
    """§61: cluster sanitized failure classes, ranked by frequency."""
    counts = Counter(e.get("failure_class") for e in events if e.get("failure_class"))
    return [{"failure_class": k, "count": v}
            for k, v in counts.most_common() if k in FAILURE_CLASSES]


def propose_retrain(events: list[dict], *, min_cluster: int = 5) -> Optional[dict[str, Any]]:
    """A retrain proposal is data, not authority: it names the dominant failure
    cluster and the number of targeted examples to synthesize. A human/policy
    gate decides whether the retrain runs."""
    clusters = cluster_failures(events)
    if not clusters or clusters[0]["count"] < min_cluster:
        return None
    top = clusters[0]
    return {
        "proposal": "targeted_retrain",
        "dominant_failure": top["failure_class"],
        "evidence_count": top["count"],
        "suggested_new_examples": min(500, top["count"] * 10),
        "requires": ["label_check", "full_regression_suite", "promotion_gates"],
        "at": time.time(),
    }
