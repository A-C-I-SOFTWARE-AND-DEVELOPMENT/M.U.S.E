"""Neural Observatory metrics collector — SYNAPSE Phase 3, gateway side.

The single data source for the additive, read-only ``/v1/observatory/*``
route family (``docs/synapse/design/10-observatory-spec.md`` §4). Stdlib
only, in-process, and **strictly passive**: nothing in the gateway calls it
unless something explicitly records an event, so when the Observatory is
unused the gateway behaves byte-for-byte as before (no files, no threads,
no timers).

What it records (via the public ``record_*`` API or the generic
:meth:`ObservatoryCollector.emit`):

* ``job.stage``     — job stage transitions (+ optional stage latency,
  queue wait, queue depth at the transition),
* ``gate.verdict``  — verification-gate verdicts with attempt numbers,
* ``queue.depth``   — queue depth samples at enqueue/dequeue,
* ``model.call``    — model latency, tier, model id, token spend, est. cost,
* ``retry``         — stage/gate retries,
* ``node.activate`` — GraphRAG touch events (cluster/node, kind, weight),
* ``route.decision``— per-turn brain-ladder routing decisions.

Storage is (a) an **append-only JSONL ring** at
``${HERMES_HOME:-~/.hermes}/observatory/events-<YYYY-MM-DD>.jsonl``, pruned
to the newest 7 day-files, and (b) **in-memory rollups** computed on demand
from a bounded event deque (re-seeded from the JSONL ring at startup). Reads
for ``/v1/observatory/metrics`` and ``/snapshot`` never re-scan the files.

Honesty rules (binding, spec §5/§6): every number returned is measured from
recorded events; a heat key with fewer than :data:`MIN_HEAT_N` observations
in the window reports ``heat: null`` plus its real ``n`` — never a guessed
score.

Wired vs pending seams
----------------------
**Wired today (opt-in, default OFF):** two seams record events, and only
when :func:`enabled` returns True (env ``MUSE_OBSERVATORY`` set to ``1`` /
``true`` / ``yes``, case-insensitive, or the marker file
``${HERMES_HOME:-~/.hermes}/observatory/.enabled`` exists):

* ``gateway.cockpit.agent`` — a ``route.decision`` around the chat reply
  generator (tier preference from the brain hint + which generator actually
  served, measured latency; the pluggable generator does not report a model
  name or token counts, so those are omitted, never guessed).
* ``hermes_cli.jarvis_prime.graphrag.query`` — ``node.activate`` for query
  result hits, via :func:`record_query_activations` (lazily imported there,
  so graphrag gains no hard gateway dependency).

When the flag is off, both module-level seam helpers return before touching
the collector — zero filesystem access — so the default gateway/graphrag
paths behave byte-for-byte as before. Still pending for a later,
owner-reviewed change: orchestrator ledger appends (``job.stage`` /
``gate.verdict``) and JobQueue add/claim (``queue.depth``).

Spec deviations (documented, not silent): writes are synchronous
best-effort appends under a lock rather than the spec's background
writer-thread + depth-10k drop-on-full queue, and rollups are computed from
the in-memory deque rather than a SQLite store. Both are honest
simplifications for the current event volumes; ``emit`` still never raises.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

# Windows accepted by /v1/observatory/metrics?window= (spec §3.3).
WINDOWS: dict[str, int] = {"15m": 900, "1h": 3600, "24h": 86400, "7d": 604800}

# Heat weights (spec §5) — measured-only bottleneck score components.
HEAT_WEIGHTS: dict[str, float] = {
    "latency": 0.30,
    "queue": 0.20,
    "fail": 0.25,
    "retry": 0.15,
    "cost": 0.10,
}

# Confidence gate: keys with fewer observations report heat = null.
MIN_HEAT_N = 5

# Event kinds that ride the SSE stream (spec §3.2); the rest feed rollups only.
STREAM_KINDS = ("job.stage", "gate.verdict", "node.activate", "route.decision")

_RING_DAYS = 7  # JSONL day-files kept on disk
_MAX_EVENTS = 50_000  # in-memory rollup window (bounded)
_STREAM_RING = 1_000  # Last-Event-ID replay ring (spec §3.2)

# node.activate coalescing (spec §3.2: batched ≤ 10/s). Overflow within a
# second is not dropped: its weight accumulates per (cluster, node, kind)
# key — bounded — and flushes as coalesced events when the second rolls over.
_ACTIVATE_MAX_PER_S = 10
_ACTIVATE_PENDING_CAP = 256


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _default_root() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "observatory"


def cluster_id(label: str) -> str:
    """Cluster id for a community label (label = a graph node id).

    Replicates ``handlers_observatory._cluster_id`` byte-for-byte — the seam
    callers (graphrag) must hash into the same id space as the snapshot's
    clusters, but importing the handlers module from here would be an import
    cycle, so the one-line hash lives in both places. Keep them identical.
    """
    return "c-" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]


def enabled() -> bool:
    """Whether the opt-in Observatory wiring seams are on (default OFF).

    True iff env ``MUSE_OBSERVATORY`` is ``1`` / ``true`` / ``yes``
    (case-insensitive) or the marker file
    ``${HERMES_HOME:-~/.hermes}/observatory/.enabled`` exists. Cheap enough
    to call per event: one env read plus one stat — the marker is re-statted
    every call (never cached) so flipping it takes effect without a restart.
    """
    flag = (os.environ.get("MUSE_OBSERVATORY") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    try:
        return (_default_root() / ".enabled").exists()
    except OSError:  # pragma: no cover - defensive
        return False


def _percentile(values: list[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile over measured values; ``None`` when empty."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1)))))
    return ordered[rank]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class ObservatoryCollector:
    """Passive, never-raising event recorder + on-demand rollups."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else _default_root()
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
        self._stream: deque[tuple[int, str, dict[str, Any]]] = deque(maxlen=_STREAM_RING)
        self._seq = 0
        self.io_errors = 0
        # node.activate coalescing state (spec §3.2: ≤ 10 emitted events/s).
        self._activate_second = -1
        self._activate_count = 0
        self._activate_pending: dict[tuple[str, Optional[str], str], float] = {}
        self._load_recent()

    # -- recording ----------------------------------------------------------

    def emit(self, kind: str, **fields: Any) -> None:
        """Record one event. Best-effort: never raises, never fabricates."""
        try:
            record = dict(fields)
            record["kind"] = str(kind)
            record.setdefault("ts", _iso(_now()))
            with self._lock:
                self._events.append(record)
                if record["kind"] in STREAM_KINDS:
                    self._seq += 1
                    payload = {k: v for k, v in record.items() if k != "kind"}
                    self._stream.append((self._seq, record["kind"], payload))
                self._append_jsonl(record)
        except Exception:  # pragma: no cover - recording must never break callers
            pass

    def record_job_stage(
        self,
        job_id: str,
        stage: str,
        *,
        task_class: Optional[str] = None,
        queue_depth: Optional[int] = None,
        stage_latency_ms: Optional[int] = None,
        queue_wait_ms: Optional[int] = None,
    ) -> None:
        self.emit(
            "job.stage",
            job_id=job_id,
            task_class=task_class,
            stage=stage,
            queue_depth=queue_depth,
            stage_latency_ms=stage_latency_ms,
            queue_wait_ms=queue_wait_ms,
        )

    def record_gate_verdict(
        self,
        job_id: str,
        gate: str,
        verdict: str,
        *,
        attempt: int = 1,
        task_class: Optional[str] = None,
        detail_ref: Optional[str] = None,
    ) -> None:
        self.emit(
            "gate.verdict",
            job_id=job_id,
            gate=gate,
            verdict=verdict,
            attempt=int(attempt),
            task_class=task_class,
            detail_ref=detail_ref or f"/v1/cockpit/jobs/{job_id}/validation",
        )

    def record_queue_depth(self, depth: int) -> None:
        self.emit("queue.depth", depth=int(depth))

    def record_model_call(
        self,
        tier: str,
        model: str,
        latency_ms: int,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        est_cost_usd: float = 0.0,
        task_class: Optional[str] = None,
    ) -> None:
        self.emit(
            "model.call",
            tier=tier,
            model=model,
            latency_ms=int(latency_ms),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            est_cost_usd=float(est_cost_usd),
            task_class=task_class,
        )

    def record_retry(
        self,
        job_id: str,
        stage: str,
        *,
        task_class: Optional[str] = None,
    ) -> None:
        self.emit("retry", job_id=job_id, stage=stage, task_class=task_class)

    def record_node_activate(
        self,
        cluster_id: str,
        *,
        node_id: Optional[str] = None,
        kind: str = "query",
        weight: float = 1.0,
    ) -> None:
        # Coalesce to ≤ _ACTIVATE_MAX_PER_S emitted events per second (spec
        # §3.2). Over-budget activations fold their weight into a pending
        # accumulator per (cluster, node, kind) key; pending keys flush as
        # coalesced events when the second rolls over. Bookkeeping happens
        # under the lock, emits after release (the lock is not reentrant).
        key = (str(cluster_id), node_id, str(kind))
        flush: list[tuple[tuple[str, Optional[str], str], float]] = []
        with self._lock:
            now_s = int(_now().timestamp())
            if now_s != self._activate_second:
                self._activate_second = now_s
                self._activate_count = 0
                while (
                    self._activate_pending
                    and self._activate_count < _ACTIVATE_MAX_PER_S - 1
                ):
                    flush.append(self._activate_pending.popitem())
                    self._activate_count += 1
            if self._activate_count >= _ACTIVATE_MAX_PER_S:
                if (
                    key in self._activate_pending
                    or len(self._activate_pending) < _ACTIVATE_PENDING_CAP
                ):
                    self._activate_pending[key] = (
                        self._activate_pending.get(key, 0.0) + float(weight)
                    )
                return
            self._activate_count += 1
        for (cid, nid, knd), pending_weight in flush:
            self.emit(
                "node.activate",
                cluster_id=cid,
                node_id=nid,
                activation=knd,
                weight=pending_weight,
            )
        self.emit(
            "node.activate",
            cluster_id=key[0],
            node_id=key[1],
            activation=key[2],
            weight=float(weight),
        )

    def record_route_decision(
        self,
        turn_id: str,
        tier: str,
        model: str,
        *,
        reason: str = "",
        latency_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        self.emit(
            "route.decision",
            turn_id=turn_id,
            tier=tier,
            model=model,
            reason=reason,
            latency_ms=int(latency_ms),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
        )

    # -- SSE stream support ---------------------------------------------------

    def latest_seq(self) -> int:
        with self._lock:
            return self._seq

    def events_since(
        self, seq: int
    ) -> tuple[list[tuple[int, str, dict[str, Any]]], int, bool]:
        """``(events, latest_seq, gap)`` for stream events after ``seq``.

        ``gap`` is True when ``seq`` predates the replay ring — the client
        missed events and should resync via the snapshot (spec §3.2).
        """
        with self._lock:
            oldest = self._stream[0][0] if self._stream else self._seq + 1
            gap = seq + 1 < oldest and self._seq > seq
            out = [item for item in self._stream if item[0] > seq]
            return out, self._seq, gap

    # -- rollups --------------------------------------------------------------

    def rollup(
        self, window: str = "1h", *, task_class: Optional[str] = None
    ) -> dict[str, Any]:
        """Measured-only aggregates over the window (spec §3.3 shape).

        Every list is honestly empty when nothing was recorded; heat keys
        with ``n < MIN_HEAT_N`` carry ``heat: null`` plus their real ``n``.
        """
        seconds = WINDOWS.get(window, WINDOWS["1h"])
        now = _now()
        cutoff = _iso(datetime.fromtimestamp(now.timestamp() - seconds, tz=timezone.utc))
        with self._lock:
            events = [e for e in self._events if str(e.get("ts", "")) >= cutoff]
            recorded_total = len(self._events)
            io_errors = self.io_errors
        if task_class:
            events = [
                e
                for e in events
                if e.get("task_class") in (task_class, None)
                or e.get("kind") in ("queue.depth",)
            ]

        stages = self._stage_rollup(events)
        gates = self._gate_rollup(events)
        models = self._model_rollup(events)
        costs = self._cost_rollup(events)
        heat = self._heat(stages, gates, costs)
        return {
            "window": window if window in WINDOWS else "1h",
            "from": cutoff,
            "to": _iso(now),
            "stages": stages,
            "gates": gates,
            "models": models,
            "cost_per_task_class": costs,
            "heat": heat,
            "heat_weights": dict(HEAT_WEIGHTS),
            "min_n": MIN_HEAT_N,
            "collector": {
                "events_in_window": len(events),
                "events_recorded": recorded_total,
                "io_errors": io_errors,
            },
        }

    def activation_weights(self, window: str = "1h") -> dict[str, float]:
        """Summed ``node.activate`` weight per cluster id over the window.

        Measured-only: an empty dict when nothing has been recorded.
        """
        seconds = WINDOWS.get(window, WINDOWS["1h"])
        cutoff = _iso(
            datetime.fromtimestamp(_now().timestamp() - seconds, tz=timezone.utc)
        )
        weights: dict[str, float] = {}
        with self._lock:
            for e in self._events:
                if e.get("kind") != "node.activate" or str(e.get("ts", "")) < cutoff:
                    continue
                cid = str(e.get("cluster_id", ""))
                weights[cid] = weights.get(cid, 0.0) + float(e.get("weight") or 0.0)
        return weights

    def ladder_rollup(self, window: str = "1h") -> list[dict[str, Any]]:
        """Per-tier routing aggregates from measured ``route.decision`` events."""
        seconds = WINDOWS.get(window, WINDOWS["1h"])
        cutoff = _iso(
            datetime.fromtimestamp(_now().timestamp() - seconds, tz=timezone.utc)
        )
        with self._lock:
            decisions = [
                e
                for e in self._events
                if e.get("kind") == "route.decision" and str(e.get("ts", "")) >= cutoff
            ]
        total = len(decisions)
        tiers: list[dict[str, Any]] = []
        for tier in sorted({str(e.get("tier", "")) for e in decisions}):
            mine = [e for e in decisions if str(e.get("tier", "")) == tier]
            latencies = [float(e["latency_ms"]) for e in mine if e.get("latency_ms") is not None]
            model_counts = Counter(str(e.get("model", "")) for e in mine)
            tiers.append(
                {
                    "tier": tier,
                    "model": model_counts.most_common(1)[0][0] if model_counts else None,
                    "share_1h": round(len(mine) / total, 4) if total else None,
                    "n": len(mine),
                    "p50_latency_ms": _percentile(latencies, 50),
                    "p95_latency_ms": _percentile(latencies, 95),
                }
            )
        return tiers

    # -- internals --------------------------------------------------------------

    @staticmethod
    def _stage_rollup(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, Optional[str]], list[dict[str, Any]]] = {}
        retries: Counter[tuple[str, Optional[str]]] = Counter()
        for e in events:
            if e.get("kind") == "job.stage":
                key = (str(e.get("stage", "")), e.get("task_class"))
                groups.setdefault(key, []).append(e)
            elif e.get("kind") == "retry":
                retries[(str(e.get("stage", "")), e.get("task_class"))] += 1
        out = []
        for (stage, klass), members in sorted(
            groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
        ):
            latencies = [
                float(m["stage_latency_ms"])
                for m in members
                if m.get("stage_latency_ms") is not None
            ]
            waits = [
                float(m["queue_wait_ms"])
                for m in members
                if m.get("queue_wait_ms") is not None
            ]
            out.append(
                {
                    "stage": stage,
                    "task_class": klass,
                    "count": len(members),
                    "p50_ms": _percentile(latencies, 50),
                    "p95_ms": _percentile(latencies, 95),
                    "queue_wait_p95_ms": _percentile(waits, 95),
                    "retries": retries.get((stage, klass), 0),
                }
            )
        return out

    @staticmethod
    def _gate_rollup(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, Optional[str]], Counter[str]] = {}
        for e in events:
            if e.get("kind") != "gate.verdict":
                continue
            key = (str(e.get("gate", "")), e.get("task_class"))
            groups.setdefault(key, Counter())[str(e.get("verdict", ""))] += 1
        out = []
        for (gate, klass), verdicts in sorted(
            groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
        ):
            passes = verdicts.get("pass", 0)
            fails = verdicts.get("fail", 0)
            overrides = verdicts.get("override", 0)
            n = passes + fails + overrides
            out.append(
                {
                    "gate": gate,
                    "task_class": klass,
                    "passes": passes,
                    "fails": fails,
                    "overrides": overrides,
                    "fail_rate": round(fails / n, 4) if n else None,
                }
            )
        return out

    @staticmethod
    def _model_rollup(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for e in events:
            if e.get("kind") not in ("model.call", "route.decision"):
                continue
            key = (str(e.get("tier", "")), str(e.get("model", "")))
            groups.setdefault(key, []).append(e)
        out = []
        for (tier, model), members in sorted(groups.items()):
            latencies = [
                float(m["latency_ms"]) for m in members if m.get("latency_ms") is not None
            ]
            out.append(
                {
                    "tier": tier,
                    "model": model,
                    "calls": len(members),
                    "p95_latency_ms": _percentile(latencies, 95),
                    "tokens_in": sum(int(m.get("tokens_in") or 0) for m in members),
                    "tokens_out": sum(int(m.get("tokens_out") or 0) for m in members),
                    "est_cost_usd": round(
                        sum(float(m.get("est_cost_usd") or 0.0) for m in members), 6
                    ),
                }
            )
        return out

    @staticmethod
    def _cost_rollup(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[float]] = {}
        for e in events:
            if e.get("kind") not in ("model.call", "route.decision"):
                continue
            klass = e.get("task_class")
            if not klass:
                continue
            groups.setdefault(str(klass), []).append(float(e.get("est_cost_usd") or 0.0))
        return [
            {"task_class": klass, "usd": round(sum(usds), 6), "n": len(usds)}
            for klass, usds in sorted(groups.items())
        ]

    @staticmethod
    def _heat(
        stages: list[dict[str, Any]],
        gates: list[dict[str, Any]],
        costs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Spec §5 heat — computed from real measurements only.

        Stage keys use the latency/queue/retry/cost components (no gate-fail
        term); gate keys use the fail-rate component. Keys with
        ``n < MIN_HEAT_N`` report ``heat: null`` with their real ``n``.
        """
        max_p95 = max((s["p95_ms"] or 0.0 for s in stages), default=0.0)
        max_wait = max((s["queue_wait_p95_ms"] or 0.0 for s in stages), default=0.0)
        cost_by_class = {c["task_class"]: c["usd"] / c["n"] if c["n"] else 0.0 for c in costs}
        max_cost = max(cost_by_class.values(), default=0.0)
        w = HEAT_WEIGHTS
        out: list[dict[str, Any]] = []
        for s in stages:
            key = f"stage:{s['stage']}:{s['task_class'] or '*'}"
            n = s["count"]
            if n < MIN_HEAT_N:
                score = None
            else:
                lat = (s["p95_ms"] or 0.0) / max_p95 if max_p95 else 0.0
                que = (s["queue_wait_p95_ms"] or 0.0) / max_wait if max_wait else 0.0
                ret = _clamp01(s["retries"] / n) if n else 0.0
                cost = (
                    cost_by_class.get(s["task_class"], 0.0) / max_cost if max_cost else 0.0
                )
                score = round(
                    _clamp01(
                        w["latency"] * lat + w["queue"] * que + w["retry"] * ret + w["cost"] * cost
                    ),
                    4,
                )
            ref = f"/v1/cockpit/ledger?category=STAGE&kind={s['stage']}"
            out.append({"key": key, "score": score, "n": n, "evidence_ref": ref})
        for g in gates:
            n = g["passes"] + g["fails"] + g["overrides"]
            key = f"gate:{g['gate']}:{g['task_class'] or '*'}"
            score = (
                round(_clamp01(w["fail"] * (g["fail_rate"] or 0.0)), 4)
                if n >= MIN_HEAT_N
                else None
            )
            ref = f"/v1/cockpit/ledger?category=GATE&kind={g['gate']}"
            out.append({"key": key, "score": score, "n": n, "evidence_ref": ref})
        return out

    # -- persistence --------------------------------------------------------

    def _day_path(self, day: str) -> Path:
        return self.root / f"events-{day}.jsonl"

    def _append_jsonl(self, record: dict[str, Any]) -> None:
        """Append one line to today's ring file; prune on day rollover."""
        try:
            day = str(record.get("ts", ""))[:10] or _iso(_now())[:10]
            path = self._day_path(day)
            if not path.exists():
                self.root.mkdir(parents=True, exist_ok=True)
                self._prune_ring(keep_day=day)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception:  # pragma: no cover - best-effort persistence
            self.io_errors += 1

    def _prune_ring(self, *, keep_day: str) -> None:
        """Keep only the newest ``_RING_DAYS`` day-files (including today's)."""
        try:
            files = sorted(self.root.glob("events-*.jsonl"))
            keep = {self._day_path(keep_day).name}
            keep.update(p.name for p in files[-(_RING_DAYS - 1):])
            for p in files:
                if p.name not in keep:
                    p.unlink(missing_ok=True)
        except Exception:  # pragma: no cover - best-effort pruning
            self.io_errors += 1

    def _load_recent(self) -> None:
        """Re-seed the in-memory deque from the JSONL ring (newest first, bounded)."""
        try:
            files = sorted(self.root.glob("events-*.jsonl"), reverse=True)
        except OSError:  # pragma: no cover - defensive
            return
        loaded: list[dict[str, Any]] = []
        for path in files:
            if len(loaded) >= _MAX_EVENTS:
                break
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:  # pragma: no cover - defensive
                continue
            day_records = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    day_records.append(rec)
            loaded = day_records + loaded
        for rec in loaded[-_MAX_EVENTS:]:
            self._events.append(rec)


# ---------------------------------------------------------------------------
# Module singleton — lazy, HERMES_HOME-aware (re-resolves when the home moves,
# matching the lazy-path pattern used by gateway.cockpit.event_log).
# ---------------------------------------------------------------------------

_COLLECTOR: Optional[ObservatoryCollector] = None
_COLLECTOR_LOCK = threading.Lock()


def get_collector() -> ObservatoryCollector:
    """The process-wide collector (created on first use, never on import)."""
    global _COLLECTOR
    root = _default_root()
    with _COLLECTOR_LOCK:
        if _COLLECTOR is None or _COLLECTOR.root != root:
            _COLLECTOR = ObservatoryCollector(root)
        return _COLLECTOR


def reset_collector() -> None:
    """Drop the singleton (tests / explicit re-home)."""
    global _COLLECTOR
    with _COLLECTOR_LOCK:
        _COLLECTOR = None


# ---------------------------------------------------------------------------
# Opt-in seam helpers (module-level) — the only functions the wired seams
# call. When :func:`enabled` is False they return before touching the
# collector: no-ops with zero filesystem access, preserving the default
# byte-for-byte-unchanged gateway behavior. When enabled they are
# best-effort and never raise into their callers.
# ---------------------------------------------------------------------------


def record_route_decision(
    turn_id: str,
    tier: str,
    model: str,
    *,
    reason: str = "",
    latency_ms: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None:
    """Seam: record one per-turn brain-ladder routing decision iff enabled."""
    if not enabled():
        return
    try:
        get_collector().record_route_decision(
            turn_id,
            tier,
            model,
            reason=reason,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception:  # pragma: no cover - seams must never break callers
        pass


def record_query_activations(
    hits: Iterable[tuple[str, str]], *, kind: str = "query", weight: float = 1.0
) -> None:
    """Seam: record GraphRAG query hits as ``node.activate`` iff enabled.

    ``hits`` is an iterable of ``(community_label, node_key)`` pairs — the
    label (a graph node id) is hashed via :func:`cluster_id` into the same
    cluster-id space the snapshot handlers use; the key rides as ``node_id``.
    Per-event coalescing (≤ 10/s) happens in ``record_node_activate``.
    """
    if not enabled():
        return
    try:
        collector = get_collector()
        for label, key in hits:
            collector.record_node_activate(
                cluster_id(str(label)),
                node_id=str(key),
                kind=kind,
                weight=float(weight),
            )
    except Exception:  # pragma: no cover - seams must never break callers
        pass


__all__ = [
    "HEAT_WEIGHTS",
    "MIN_HEAT_N",
    "STREAM_KINDS",
    "WINDOWS",
    "ObservatoryCollector",
    "cluster_id",
    "enabled",
    "get_collector",
    "record_query_activations",
    "record_route_decision",
    "reset_collector",
]
