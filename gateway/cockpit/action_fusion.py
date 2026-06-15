"""Read-only multiplexer fusing every real M.U.S.E action into one stream.

Backs ``GET /v1/observatory/actions`` — the live "neural network wallpaper" feed.
It fuses, **without fabricating anything**, the four honest action sources that
are observable from the cockpit gateway process:

* the observatory collector's in-memory stream ring (``node.activate`` /
  ``route.decision`` / ``job.stage`` / ``gate.verdict``) via
  :meth:`ObservatoryCollector.events_since`,
* the flywheel JSONL (``$HERMES_HOME/flywheel/events.jsonl``),
* the cockpit event log (``$HERMES_HOME/cockpit/events.jsonl``),
* the axiom hash-chain (``$HERMES_HOME/axiom/chain.jsonl``).

Honest by construction:

* **Only recorded events.** Every emitted :class:`ActionEvent` derives 1:1 from a
  real ring entry / JSONL line. Unmapped source events are dropped, never invented.
* **No producer coupling.** Producers run in other processes (CLI invocations write
  the flywheel/axiom files); the gateway only *reads* the durable truth they left.
  The orchestrator's in-memory broker lives in a separate process and is therefore
  **not** a fusable source here — claiming it would be a fabricated data path.
* **Collector events come only via** ``events_since`` — the multiplexer must not
  also tail ``observatory/events-*.jsonl`` or every collector event double-counts.
* **Dormant gate.** The caller (``server._stream_actions``) returns ``503`` when the
  observatory collector is opt-out, so the actions feed is a single opt-in surface.

Each connection owns a :class:`FusionTailer` whose cursor (an opaque base64url
JSON of per-source offsets) round-trips through the SSE ``Last-Event-ID`` header so
a reconnect resumes after the last delivered batch.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import event_log

ACTION_VERSION = 1

# Closed visual vocabulary — native renderers (Android GL, UE5) pin this set.
# An unrecognized source event maps to nothing (dropped), never a new primitive.
KINDS: tuple[str, ...] = (
    "cluster.spark",   # GraphRAG cluster/node activation
    "pipeline.packet",  # job stage moving down the pipeline
    "gate.flare",      # verification-gate verdict
    "ladder.streak",   # brain-ladder routing decision
    "owner.pulse",     # owner prompt
    "agent.pulse",     # agent action / tool actuation
    "skill.pulse",     # skill invocation
    "system.pulse",    # cockpit event-log line
    "audit.flare",     # axiom-chain decision / gated action
    "meta.resync",     # control: client should (re)load the snapshot
)

_SEVERITIES = ("info", "warn", "error", "critical")


# --------------------------------------------------------------------------- io
def _hermes_home() -> Path:
    import os

    return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:  # pragma: no cover - defensive
        return 0


def _tail_jsonl(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    """``(new_records, new_offset)`` for complete JSONL lines after ``offset``.

    Mirrors :func:`event_log.read_since_offset`: only whole lines are consumed; a
    trailing partial line waits for the next read; a shrunk file restarts at 0.
    """
    try:
        if not path.is_file():
            return [], offset
        size = path.stat().st_size
        if size < offset:  # rotated/truncated → restart
            offset = 0
        with path.open("rb") as fh:
            fh.seek(offset)
            data = fh.read()
    except OSError:  # pragma: no cover - defensive
        return [], offset
    newline = data.rfind(b"\n")
    if newline == -1:
        return [], offset
    consumed = data[: newline + 1]
    new_offset = offset + len(consumed)
    out: list[dict[str, Any]] = []
    for line in consumed.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out, new_offset


# ----------------------------------------------------------------- normalizers
def _to_iso(ts: Any) -> str:
    """Normalize a float-epoch or ISO timestamp to an ISO-8601 UTC string."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    if isinstance(ts, str) and ts:
        return ts
    return datetime.now(timezone.utc).isoformat()


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _short(value: Any, limit: int = 80) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _event(
    kind: str,
    source: str,
    *,
    target: Optional[dict[str, Any]] = None,
    label: Any = "",
    weight: float = 1.0,
    severity: str = "info",
    ts: Any = None,
) -> dict[str, Any]:
    """Build one ActionEvent (the ``id`` is assigned later in :meth:`drain`)."""
    return {
        "v": ACTION_VERSION,
        "id": 0,
        "ts": _to_iso(ts),
        "kind": kind,
        "source": source,
        "target": {k: v for k, v in (target or {}).items() if v is not None},
        "label": _short(label),
        "weight": float(weight),
        "severity": severity if severity in _SEVERITIES else "info",
    }


# --------------------------------------------------------------------- mappers
def _map_collector(kind: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    ts = payload.get("ts")
    if kind == "node.activate":
        return _event(
            "cluster.spark", "collector",
            target={"cluster_id": payload.get("cluster_id"), "node_id": payload.get("node_id")},
            label=payload.get("cluster_id") or "", weight=_num(payload.get("weight"), 1.0), ts=ts,
        )
    if kind == "job.stage":
        return _event(
            "pipeline.packet", "collector",
            target={"job_id": payload.get("job_id")}, label=payload.get("stage") or "", ts=ts,
        )
    if kind == "gate.verdict":
        verdict = str(payload.get("verdict") or "")
        return _event(
            "gate.flare", "collector", target={"job_id": payload.get("job_id")},
            label=f"{payload.get('gate', '')}·{verdict}",
            severity="error" if verdict.lower() == "fail" else "info", ts=ts,
        )
    if kind == "route.decision":
        latency = _num(payload.get("latency_ms"), 0.0)
        return _event(
            "ladder.streak", "collector",
            label=f"{payload.get('tier', '')}·{payload.get('model', '')}",
            weight=min(1.0, latency / 1000.0) if latency else 1.0, ts=ts,
        )
    return None  # unmapped collector kind → dropped, never invented


_FLYWHEEL_KIND = {
    "owner.prompt": "owner.pulse",
    "agent.action": "agent.pulse",
    "skill.used": "skill.pulse",
    "model.routed": "ladder.streak",
}


def _map_flywheel(rec: dict[str, Any]) -> Optional[dict[str, Any]]:
    mapped = _FLYWHEEL_KIND.get(str(rec.get("kind") or ""))
    if mapped is None:
        return None
    payload = rec.get("payload") or {}
    label = payload.get("skill") or payload.get("name") or payload.get("summary") or rec.get("kind")
    severity = "error" if str(rec.get("outcome") or "").lower() == "failure" else "info"
    return _event(mapped, "flywheel", label=label, severity=severity, ts=rec.get("ts"))


def _map_eventlog(rec: dict[str, Any]) -> Optional[dict[str, Any]]:
    level = str(rec.get("level") or "info")
    return _event(
        "system.pulse", "cockpit", target={"job_id": rec.get("job_id")},
        label=rec.get("message") or "", severity=level, ts=rec.get("ts"),
    )


def _map_axiom(rec: dict[str, Any]) -> Optional[dict[str, Any]]:
    return _event("audit.flare", "axiom", label=rec.get("kind") or "", ts=rec.get("ts"))


# ----------------------------------------------------------------- the tailer
def _encode_cursor(state: dict[str, int]) -> str:
    raw = json.dumps(state, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: Optional[str]) -> Optional[dict[str, int]]:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


class FusionTailer:
    """Per-connection cursor over the four action sources.

    A fresh tailer (absent/malformed cursor) starts **from now** — current
    end-of-file offsets + the collector's latest seq — so a new client sees only
    actions that happen after it connects (matching the other observatory
    streams). A decoded cursor resumes each source from its recorded offset.
    """

    def __init__(self, cursor: Optional[str] = None) -> None:
        home = _hermes_home()
        self._flywheel = home / "flywheel" / "events.jsonl"
        self._axiom = home / "axiom" / "chain.jsonl"
        decoded = _decode_cursor(cursor)
        if decoded is None:
            self.fresh = True
            self._collector_seq = _collector_latest_seq()
            self._eventlog_off = event_log.current_offset()
            self._flywheel_off = _file_size(self._flywheel)
            self._axiom_off = _file_size(self._axiom)
            self._fused_id = 0
        else:
            self.fresh = False
            self._collector_seq = int(decoded.get("o", 0))
            self._eventlog_off = int(decoded.get("e", 0))
            self._flywheel_off = int(decoded.get("f", 0))
            self._axiom_off = int(decoded.get("a", 0))
            self._fused_id = int(decoded.get("n", 0))

    def cursor(self) -> str:
        """Opaque resume cursor reflecting the current per-source offsets."""
        return _encode_cursor({
            "o": self._collector_seq, "e": self._eventlog_off,
            "f": self._flywheel_off, "a": self._axiom_off, "n": self._fused_id,
        })

    def drain(self) -> list[dict[str, Any]]:
        """All new ActionEvents since the last drain, time-ordered, id-stamped."""
        events: list[dict[str, Any]] = []

        # Collector stream ring (NOT the JSONL file — avoids double-counting).
        try:
            from gateway.cockpit import observatory_metrics as om

            ring, self._collector_seq, _gap = om.get_collector().events_since(self._collector_seq)
            for _seq, kind, payload in ring:
                mapped = _map_collector(kind, payload)
                if mapped is not None:
                    events.append(mapped)
        except Exception:  # pragma: no cover - defensive
            pass

        # Cockpit event log.
        try:
            recs, self._eventlog_off = event_log.read_since_offset(self._eventlog_off)
            for rec in recs:
                mapped = _map_eventlog(rec)
                if mapped is not None:
                    events.append(mapped)
        except Exception:  # pragma: no cover - defensive
            pass

        # Flywheel + axiom — durable JSONL written by other processes.
        recs, self._flywheel_off = _tail_jsonl(self._flywheel, self._flywheel_off)
        for rec in recs:
            mapped = _map_flywheel(rec)
            if mapped is not None:
                events.append(mapped)
        recs, self._axiom_off = _tail_jsonl(self._axiom, self._axiom_off)
        for rec in recs:
            mapped = _map_axiom(rec)
            if mapped is not None:
                events.append(mapped)

        events.sort(key=lambda e: (e["ts"], e["source"]))
        for event in events:
            self._fused_id += 1
            event["id"] = self._fused_id
        return events


def _collector_latest_seq() -> int:
    try:
        from gateway.cockpit import observatory_metrics as om

        return om.get_collector().latest_seq()
    except Exception:  # pragma: no cover - defensive
        return 0


__all__ = ["ACTION_VERSION", "KINDS", "FusionTailer"]
