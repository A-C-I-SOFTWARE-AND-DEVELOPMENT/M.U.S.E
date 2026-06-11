"""Neural Observatory recommendation engine — honest by construction.

Implements master plan §3.4 (``docs/plans/2026-06-10-project-synapse-master-plan.md``)
and spec §6 (``docs/synapse/design/10-observatory-spec.md``): measured
baselines → rule-based hypotheses → counterfactual validation over recorded
events → verdict cards. Stdlib only (``statistics`` + ``random`` for the
seeded bootstrap); no third-party deps.

Pipeline
--------
1. **Baselines** (:func:`baselines`) — per task-class rolling baselines
   (latency p50/p95, success rate, gate-pass rate, token cost) consumed from
   :meth:`gateway.cockpit.observatory_metrics.ObservatoryCollector.rollup`.
   This module never re-aggregates the JSONL ring itself.
2. **Hypotheses** (:func:`generate_candidates`) — a documented rule table
   keyed on the hottest measured heat entries (see ``RULE_TABLE`` below),
   plus an inert seam for model-suggested candidates: callers may pass
   ``model_suggestions`` (each marked ``source: "model"``); suggestions are
   sanitized to *structure only* — a model may propose a ``PolicyDelta``,
   it may NEVER contribute a number to a card.
3. **Validation** (:func:`validate_delta`) — counterfactual re-scoring over
   recorded events. For a ``route_pin`` delta the two arms are the measured
   latency distributions of the two tiers on the same task class; the card
   gets the median delta plus a 95% CI from a deterministic seeded bootstrap
   (``random.Random`` seeded from the card id). **Hard rule (test-enforced):
   no percentage or CI appears on a card unless n >= MIN_EVIDENCE_N (50)
   for BOTH arms.** Below that the card is ``state: "insufficient_evidence"``
   with the explicit collecting text and zero projected numbers.
4. **Cards** (:func:`build_cards`) — stable, versioned schema (``v: 1``)::

       {
         "v": 1,
         "id": "rec-<sha1(delta)[:12]>",        # deterministic hash of delta
         "title": str,                           # numbers only when validated
         "delta": {...},                         # machine-readable PolicyDelta
         "state": "insufficient_evidence" | "validated" | "staged",
         "validation": {
           "method": "recorded-events-counterfactual",
           "n_baseline": int, "n_candidate": int,
           "median_delta_pct": float | None,     # None until n >= 50 both arms
           "ci95": [lo, hi] | None,
           "metric": str
         },
         "evidence_refs": [...],                 # heat keys / ledger refs / window
         "created_at": iso8601,
         "note": str                             # the explicit collecting text
       }

5. **Staging** (:func:`stage_recommendation`) — appends a proposal into the
   EXISTING owner-gated proposals queue (``handlers._load_proposals`` /
   ``_save_proposals``), so Apply rides the existing owner-phrase
   ``POST /v1/cockpit/approvals/{id}`` flow and rollback rides the existing
   ledger rollback route. No new owner-gated surface is created here.

Validation-method honesty
-------------------------
Every card carries ``validation.method`` so nothing is overstated. The
method shipped today is ``"recorded-events-counterfactual"`` — re-scoring
distributions the collector already measured. The owner-gated upgrade is a
**live replay** through the repo-root ``batch_runner.py`` harness
(``python batch_runner.py --dataset_file=<rows>.jsonl``, master plan §3.4
step 3); :func:`replay_spec` emits the JSONL dataset rows such a replay
would consume — in memory only, nothing is written to disk by this module.
Deltas with no second measured arm in recorded events (gate / concurrency
changes) honestly stay ``insufficient_evidence`` until that replay harness
exists; they never borrow numbers from a different method.

Event access seam: distribution-level validation needs per-event samples,
which ``rollup()`` (aggregates) cannot provide. :func:`_window_events` takes
a read-only snapshot of the collector's own bounded in-memory event window
(the exact store ``rollup()`` reads) under its lock — it never re-reads or
re-aggregates the JSONL ring on disk.
"""

from __future__ import annotations

import hashlib
import json
import random
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from gateway.cockpit import observatory_metrics as om

CARD_VERSION = 1

#: Hard rule (spec §6): minimum events in BOTH arms before any percentage/CI
#: may appear on a card.
MIN_EVIDENCE_N = 50

VALIDATION_METHOD = "recorded-events-counterfactual"

#: Proposal ``kind`` used in the existing owner-gated proposals queue.
PROPOSAL_KIND = "observatory_recommendation"

#: How many of the hottest measured heat entries the rule table considers.
MAX_HOT_KEYS = 8

#: Bootstrap resamples for the 95% CI (deterministic, seeded per card).
_BOOTSTRAP_ITERATIONS = 600

#: R3 fires when measured queue wait dominates stage latency by this share.
_QUEUE_WAIT_DOMINANCE = 0.5

#: The rule table (documentation + the keys :func:`generate_candidates`
#: implements). Each rule maps a hot measured heat key to a bounded
#: ``PolicyDelta``; rules generate *hypotheses* only — numbers come solely
#: from :func:`validate_delta`.
RULE_TABLE: tuple[dict[str, str], ...] = (
    {
        "rule": "R1",
        "trigger": "stage:worker:<class> hot AND local-tier p95 < hosted-tier "
        "p95 on the same task class (measured model calls)",
        "delta": "route_pin: pin <class> tasks to the local tier/model",
    },
    {
        "rule": "R2",
        "trigger": "gate:<gate>:<class> failure-rate hot",
        "delta": "gate_adjust: add a retry / raise strictness on that gate",
    },
    {
        "rule": "R3",
        "trigger": "stage:<stage>:<class> hot AND measured p95 queue wait "
        ">= 50% of stage p95 latency",
        "delta": "concurrency: raise worker concurrency for that stage/class",
    },
    {
        "rule": "model-seam",
        "trigger": "caller-supplied model_suggestions (inert unless a "
        "generator is wired)",
        "delta": "sanitized structure-only PolicyDelta, source: 'model' — "
        "model suggestions NEVER carry numbers",
    },
)

#: Fields a model-suggested delta may carry (structure only — never numbers).
_MODEL_DELTA_FIELDS = (
    "kind",
    "task_class",
    "target_tier",
    "target_model",
    "baseline_tier",
    "gate",
    "stage",
    "change",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collecting_note(n: int) -> str:
    return f"insufficient evidence (n={n}) — collecting"


def _delta_id(delta: dict[str, Any]) -> str:
    """Deterministic card id: hash of the canonical machine-readable delta."""
    canonical = json.dumps(delta, sort_keys=True, default=str)
    return "rec-" + hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


def _window_events(collector: Any, window: str) -> list[dict[str, Any]]:
    """Read-only snapshot of the collector's in-memory event window.

    Same store, same cutoff semantics as ``rollup()``; never touches the
    JSONL ring on disk (see module docstring — documented seam).
    """
    seconds = om.WINDOWS.get(window, om.WINDOWS["1h"])
    cutoff = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - seconds, tz=timezone.utc
    ).isoformat()
    with collector._lock:
        return [dict(e) for e in collector._events if str(e.get("ts", "")) >= cutoff]


# ---------------------------------------------------------------------------
# 1. Baselines — consumed from the collector's rollup, never re-aggregated
# ---------------------------------------------------------------------------


def baselines(collector: Any, window: str = "24h") -> dict[str, Any]:
    """Per task-class rolling baselines from the collector's ``rollup()``.

    Measured-only: classes appear only when events were recorded; every
    missing measurement is an honest ``None``.
    """
    rollup = collector.rollup(window)

    def _entry() -> dict[str, Any]:
        return {
            "latency_p50_ms": None,
            "latency_p95_ms": None,
            "stage_n": 0,
            "success_rate": None,
            "success_n": 0,
            "gate_pass_rate": None,
            "gate_n": 0,
            "cost_usd_per_task": None,
            "cost_n": 0,
        }

    out: dict[str, dict[str, Any]] = {}
    for s in rollup["stages"]:
        klass = s["task_class"] or "*"
        entry = out.setdefault(klass, _entry())
        if s["stage"] == "worker":
            entry["latency_p50_ms"] = s["p50_ms"]
            entry["latency_p95_ms"] = s["p95_ms"]
            entry["stage_n"] = s["count"]
        if s["stage"] in ("done", "failed"):
            entry["success_n"] += s["count"]
            if s["stage"] == "done":
                entry["_done"] = entry.get("_done", 0) + s["count"]
    gate_totals: dict[str, list[int]] = {}
    for g in rollup["gates"]:
        klass = g["task_class"] or "*"
        out.setdefault(klass, _entry())
        passes, fails, overrides = g["passes"], g["fails"], g["overrides"]
        tot = gate_totals.setdefault(klass, [0, 0])
        tot[0] += passes
        tot[1] += passes + fails + overrides
    for klass, (passed, total) in gate_totals.items():
        if total:
            out[klass]["gate_pass_rate"] = round(passed / total, 4)
            out[klass]["gate_n"] = total
    for c in rollup["cost_per_task_class"]:
        entry = out.setdefault(str(c["task_class"]), _entry())
        if c["n"]:
            entry["cost_usd_per_task"] = round(c["usd"] / c["n"], 6)
            entry["cost_n"] = c["n"]
    for entry in out.values():
        done = entry.pop("_done", 0)
        if entry["success_n"]:
            entry["success_rate"] = round(done / entry["success_n"], 4)
    return {"window": rollup["window"], "task_classes": out}


# ---------------------------------------------------------------------------
# 2. Hypotheses — the rule table over the hottest measured heat entries
# ---------------------------------------------------------------------------


def hot_heat(rollup: dict[str, Any]) -> list[dict[str, Any]]:
    """The hottest measured heat entries (score non-null and > 0), hottest
    first, capped at :data:`MAX_HOT_KEYS`. Sub-threshold (``score: null``)
    keys never generate hypotheses — no guessed glow, no guessed levers."""
    scored = [h for h in rollup.get("heat", []) if h.get("score")]
    scored.sort(key=lambda h: (-h["score"], h["key"]))
    return scored[:MAX_HOT_KEYS]


def _tier_latencies(
    events: list[dict[str, Any]], task_class: str
) -> dict[str, list[float]]:
    """Measured per-tier latency samples for one task class (model calls)."""
    out: dict[str, list[float]] = {}
    for e in events:
        if e.get("kind") not in ("model.call", "route.decision"):
            continue
        if e.get("task_class") != task_class or e.get("latency_ms") is None:
            continue
        out.setdefault(str(e.get("tier", "")), []).append(float(e["latency_ms"]))
    return out


def _dominant_model(
    events: list[dict[str, Any]], task_class: str, tier: str
) -> Optional[str]:
    names = Counter(
        str(e.get("model", ""))
        for e in events
        if e.get("kind") in ("model.call", "route.decision")
        and e.get("task_class") == task_class
        and str(e.get("tier", "")) == tier
        and e.get("model")
    )
    return names.most_common(1)[0][0] if names else None


def _sanitize_model_delta(suggestion: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Structure-only projection of a model-suggested delta.

    Keeps only the allowlisted string fields and forces ``source: "model"``.
    Any numeric claim a model attaches (projected improvements, counts,
    percentages) is dropped here — numbers come only from measurement.
    """
    if not isinstance(suggestion, dict) or not suggestion.get("kind"):
        return None
    delta: dict[str, Any] = {}
    for field in _MODEL_DELTA_FIELDS:
        value = suggestion.get(field)
        if isinstance(value, str) and value:
            delta[field] = value
    if "kind" not in delta:
        return None
    delta["source"] = "model"
    return delta


def generate_candidates(
    collector: Any,
    window: str = "24h",
    *,
    model_suggestions: Optional[Iterable[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Rule-table hypotheses (R1–R3) over the hottest measured heat entries,
    plus sanitized model-suggested candidates (the inert seam — nothing is
    generated unless the caller wires a generator and passes suggestions)."""
    rollup = collector.rollup(window)
    events = _window_events(collector, window)
    stage_rows = {
        (s["stage"], s["task_class"] or "*"): s for s in rollup["stages"]
    }
    deltas: list[dict[str, Any]] = []
    for entry in hot_heat(rollup):
        parts = str(entry["key"]).split(":")
        if len(parts) != 3:
            continue
        kind, name, klass = parts
        if kind == "stage" and klass != "*":
            # R1 — route pin: local tier measurably faster on this class.
            if name == "worker":
                tiers = _tier_latencies(events, klass)
                local_p95 = om._percentile(tiers.get("local", []), 95)
                hosted_p95 = om._percentile(tiers.get("hosted", []), 95)
                if (
                    local_p95 is not None
                    and hosted_p95 is not None
                    and local_p95 < hosted_p95
                ):
                    deltas.append(
                        {
                            "kind": "route_pin",
                            "task_class": klass,
                            "target_tier": "local",
                            "target_model": _dominant_model(events, klass, "local"),
                            "baseline_tier": "hosted",
                            "heat_key": entry["key"],
                            "source": "rule:R1",
                        }
                    )
            # R3 — concurrency: measured queue wait dominates stage latency.
            row = stage_rows.get((name, klass))
            if row and row.get("queue_wait_p95_ms"):
                p95 = row.get("p95_ms")
                if p95 is None or row["queue_wait_p95_ms"] >= _QUEUE_WAIT_DOMINANCE * p95:
                    deltas.append(
                        {
                            "kind": "concurrency",
                            "task_class": klass,
                            "stage": name,
                            "change": "increase_worker_concurrency",
                            "heat_key": entry["key"],
                            "source": "rule:R3",
                        }
                    )
        elif kind == "gate":
            # R2 — gate failure-rate hot: retry / strictness delta.
            deltas.append(
                {
                    "kind": "gate_adjust",
                    "gate": name,
                    "task_class": klass,
                    "change": "add_retry",
                    "heat_key": entry["key"],
                    "source": "rule:R2",
                }
            )
    for suggestion in model_suggestions or ():
        sanitized = _sanitize_model_delta(suggestion)
        if sanitized is not None:
            deltas.append(sanitized)
    # De-duplicate on the deterministic id (stable order preserved).
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for delta in deltas:
        did = _delta_id(delta)
        if did not in seen:
            seen.add(did)
            unique.append(delta)
    return unique


# ---------------------------------------------------------------------------
# 3. Validation — counterfactual re-scoring over recorded events
# ---------------------------------------------------------------------------


def _bootstrap_ci95(
    baseline: list[float], candidate: list[float], seed: int
) -> Optional[list[float]]:
    """Deterministic seeded bootstrap 95% CI of the median delta percent."""
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(_BOOTSTRAP_ITERATIONS):
        b = statistics.median(rng.choices(baseline, k=len(baseline)))
        c = statistics.median(rng.choices(candidate, k=len(candidate)))
        if b > 0:
            deltas.append((c - b) / b * 100.0)
    if not deltas:
        return None
    lo = om._percentile(deltas, 2.5)
    hi = om._percentile(deltas, 97.5)
    if lo is None or hi is None:
        return None
    return [round(lo, 1), round(hi, 1)]


def _empty_validation(metric: str, n_baseline: int, n_candidate: int) -> dict[str, Any]:
    return {
        "method": VALIDATION_METHOD,
        "n_baseline": n_baseline,
        "n_candidate": n_candidate,
        "median_delta_pct": None,
        "ci95": None,
        "metric": metric,
    }


def validate_delta(
    collector: Any, delta: dict[str, Any], window: str = "24h"
) -> tuple[str, dict[str, Any], str]:
    """``(state, validation, note)`` for one delta — measured numbers only.

    ``route_pin`` deltas have two recorded arms (the two tiers' measured
    latency distributions on the same class) and can be counterfactually
    scored once **both** arms reach :data:`MIN_EVIDENCE_N`. Gate /
    concurrency / model-structural deltas have no second recorded arm, so
    they stay ``insufficient_evidence`` until the owner-gated
    ``batch_runner.py`` live replay exists (see module docstring).
    """
    if delta.get("kind") == "route_pin":
        events = _window_events(collector, window)
        tiers = _tier_latencies(events, str(delta.get("task_class", "")))
        baseline_arm = tiers.get(str(delta.get("baseline_tier", "hosted")), [])
        candidate_arm = tiers.get(str(delta.get("target_tier", "local")), [])
        n_b, n_c = len(baseline_arm), len(candidate_arm)
        if n_b < MIN_EVIDENCE_N or n_c < MIN_EVIDENCE_N:
            note = _collecting_note(min(n_b, n_c))
            return "insufficient_evidence", _empty_validation("latency_ms", n_b, n_c), note
        median_b = statistics.median(baseline_arm)
        if median_b <= 0:
            note = "baseline median is zero — not scorable from recorded events"
            return "insufficient_evidence", _empty_validation("latency_ms", n_b, n_c), note
        median_c = statistics.median(candidate_arm)
        seed = int.from_bytes(
            hashlib.sha1(_delta_id(delta).encode("utf-8")).digest()[:8], "big"
        )
        ci95 = _bootstrap_ci95(baseline_arm, candidate_arm, seed)
        if ci95 is None:
            note = "bootstrap not scorable from recorded events"
            return "insufficient_evidence", _empty_validation("latency_ms", n_b, n_c), note
        validation = {
            "method": VALIDATION_METHOD,
            "n_baseline": n_b,
            "n_candidate": n_c,
            "median_delta_pct": round((median_c - median_b) / median_b * 100.0, 1),
            "ci95": ci95,
            "metric": "latency_ms",
        }
        return "validated", validation, ""

    # No counterfactual arm exists in recorded events for these delta kinds.
    rollup = collector.rollup(window)
    metric = "gate_fail_rate" if delta.get("kind") == "gate_adjust" else "queue_wait_ms"
    n = 0
    for entry in rollup.get("heat", []):
        if entry.get("key") == delta.get("heat_key"):
            n = int(entry.get("n") or 0)
            break
    note = (
        _collecting_note(n)
        + " — no counterfactual arm in recorded events; awaiting the "
        "owner-gated batch_runner.py live replay"
    )
    return "insufficient_evidence", _empty_validation(metric, n, 0), note


# ---------------------------------------------------------------------------
# 4. Cards
# ---------------------------------------------------------------------------


def _title(delta: dict[str, Any], state: str, validation: dict[str, Any]) -> str:
    """Card title — carries numbers ONLY when the card is validated."""
    kind = delta.get("kind")
    if kind == "route_pin":
        base = (
            f"Pin {delta.get('task_class')} tasks to the "
            f"{delta.get('target_tier')} tier"
        )
        if delta.get("target_model"):
            base += f" ({delta['target_model']})"
        if state == "validated":
            lo, hi = validation["ci95"]
            return (
                f"{base}: median latency {validation['median_delta_pct']:+.1f}% "
                f"(n={validation['n_candidate']} candidate / "
                f"{validation['n_baseline']} baseline, 95% CI {lo}%…{hi}%)"
            )
        n = min(validation["n_baseline"], validation["n_candidate"])
        return f"{base} — {_collecting_note(n)}"
    if kind == "gate_adjust":
        base = (
            f"Adjust the {delta.get('gate')} gate on "
            f"{delta.get('task_class')} tasks ({delta.get('change')})"
        )
    elif kind == "concurrency":
        base = (
            f"Raise {delta.get('stage')} concurrency for "
            f"{delta.get('task_class')} tasks"
        )
    else:
        base = f"Policy change: {kind}"
    return f"{base} — {_collecting_note(validation['n_baseline'])}"


def build_cards(
    collector: Any,
    window: str = "24h",
    *,
    model_suggestions: Optional[Iterable[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Generate + validate recommendation cards (schema in module docstring).

    Honest by construction: cards exist only for measured hot keys (or
    explicit model suggestions); numbers exist only past the evidence
    threshold; every card names its validation method and evidence.
    """
    rollup = collector.rollup(window)
    heat_refs = {
        h["key"]: h.get("evidence_ref") for h in rollup.get("heat", [])
    }
    cards: list[dict[str, Any]] = []
    for delta in generate_candidates(
        collector, window, model_suggestions=model_suggestions
    ):
        state, validation, note = validate_delta(collector, delta, window)
        evidence_refs: list[str] = []
        heat_key = delta.get("heat_key")
        if heat_key:
            evidence_refs.append(str(heat_key))
            if heat_refs.get(heat_key):
                evidence_refs.append(str(heat_refs[heat_key]))
        evidence_refs.append(f"window:{rollup['window']}")
        cards.append(
            {
                "v": CARD_VERSION,
                "id": _delta_id(delta),
                "title": _title(delta, state, validation),
                "delta": delta,
                "state": state,
                "validation": validation,
                "evidence_refs": evidence_refs,
                "created_at": _now_iso(),
                "note": note,
            }
        )
    return cards


def replay_spec(card: dict[str, Any], *, window: str = "24h") -> dict[str, Any]:
    """The JSONL dataset a future ``batch_runner.py`` live replay consumes.

    Emits (in memory — this function writes NOTHING to disk) the recorded
    events relevant to the card's delta as dataset rows, plus the harness
    invocation. Live replay through the repo-root ``batch_runner.py``
    (``python batch_runner.py --dataset_file=<file>.jsonl``) is the
    owner-gated upgrade from ``recorded-events-counterfactual`` validation.
    """
    delta = card.get("delta", {})
    klass = delta.get("task_class")
    collector = om.get_collector()
    rows = [
        e
        for e in _window_events(collector, window)
        if klass is None or e.get("task_class") in (klass, None)
    ]
    return {
        "v": CARD_VERSION,
        "card_id": card.get("id"),
        "policy_delta": delta,
        "harness": "batch_runner.py",
        "harness_invocation": (
            "python batch_runner.py --dataset_file=<write rows here>.jsonl "
            f"--run_name=replay-{card.get('id')}"
        ),
        "rows": rows,
        "row_count": len(rows),
        "note": (
            "in-memory only — caller writes rows to a .jsonl file when an "
            "owner-approved live replay is actually scheduled"
        ),
    }


# ---------------------------------------------------------------------------
# 5. Staging — into the EXISTING owner-gated proposals queue
# ---------------------------------------------------------------------------


def staged_proposal_ids() -> dict[str, str]:
    """Map of card id → proposal id for already-staged recommendations."""
    from . import handlers as h

    out: dict[str, str] = {}
    for p in h._load_proposals():
        if p.get("kind") == PROPOSAL_KIND and p.get("target_path"):
            out[str(p["target_path"])] = h._proposal_id(p)
    return out


def mark_staged(cards: list[dict[str, Any]]) -> None:
    """Annotate cards already sitting in the proposals queue as staged."""
    staged = staged_proposal_ids()
    for card in cards:
        pid = staged.get(str(card.get("id")))
        if pid:
            card["state"] = "staged"
            card["proposal_id"] = pid


def stage_recommendation(card: dict[str, Any]) -> tuple[str, bool]:
    """Stage a card into the existing proposals queue → ``(proposal_id, created)``.

    ``created`` is False when the card was already staged (idempotent guard).
    The proposal then rides the EXISTING owner-gated approval flow
    (``POST /v1/cockpit/approvals/{id}`` with the exact owner phrase) and the
    existing ledger rollback route — staging itself grants nothing.
    """
    from . import handlers as h

    items = h._load_proposals()
    card_id = str(card.get("id"))
    for p in items:
        if p.get("kind") == PROPOSAL_KIND and str(p.get("target_path")) == card_id:
            pid = h._proposal_id(p)
            card["state"] = "staged"
            card["proposal_id"] = pid
            return pid, False
    proposal = {
        "kind": PROPOSAL_KIND,
        "target_path": card_id,
        "rationale": str(card.get("title", "")),
        "risk_class": "RC3",
        "status": "proposed",
        "requires_owner_approval": True,
        "created_at": _now_iso(),
        "source": "observatory-recommendation-engine",
        "delta": card.get("delta"),
        "validation": card.get("validation"),
        "evidence_refs": card.get("evidence_refs"),
    }
    items.append(proposal)
    h._save_proposals(items)
    pid = h._proposal_id(proposal)
    card["state"] = "staged"
    card["proposal_id"] = pid
    return pid, True


__all__ = [
    "CARD_VERSION",
    "MIN_EVIDENCE_N",
    "PROPOSAL_KIND",
    "RULE_TABLE",
    "VALIDATION_METHOD",
    "baselines",
    "build_cards",
    "generate_candidates",
    "hot_heat",
    "mark_staged",
    "replay_spec",
    "stage_recommendation",
    "staged_proposal_ids",
    "validate_delta",
]
