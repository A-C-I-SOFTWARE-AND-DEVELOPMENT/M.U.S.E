"""Learning capture + the reversible-apply hook for the swarm self-update loop.

Two responsibilities:

* :func:`capture_swarm_trace` — append a dated, provenance-tagged record of a
  swarm job (grains, outcomes, ledger, convergence) to a local JSONL under
  HERMES_HOME, and best-effort bridge it to the JARVIS learning dataset so
  validated, owner-approvable traces can flow into fine-tune / preference / eval.
* :func:`record_applied_update` — the default ``apply_fn`` the coordinator uses
  for the *reversible* self-update tier. It does **not** mutate live routing
  config in place (that would be an un-auditable silent edit); instead it
  appends the applied change to a drafts/applied ledger **with its rollback
  recipe**, so the change is reversible by deleting the record and a human/monitor
  can see exactly what was auto-applied. This is the safe, reversible action that
  honours the "auto-apply reversible" policy without silent overwrites.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import json
import os

from muse_cli.swarm.grain import SwarmPlan, now_iso

__all__ = [
    "capture_swarm_trace",
    "record_applied_update",
    "applied_updates_log_path",
]


def _hermes_home() -> Path:
    try:
        from muse_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _swarm_dir() -> Path:
    d = _hermes_home() / "jarvis_prime" / "swarm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def capture_swarm_trace(
    plan: SwarmPlan,
    results: Any,
    *,
    convergence: Optional[dict[str, Any]] = None,
    ledger_path: Optional[str] = None,
) -> Path:
    """Append a dated learning record for a swarm job. Returns the JSONL path."""

    record = {
        "kind": "swarm_job",
        "job_id": plan.job_id,
        "goal": plan.goal,
        "created_at": now_iso(),
        "blackboard_namespace": plan.blackboard_namespace,
        "ledger_path": ledger_path,
        "convergence": convergence,
        "grains": [
            {
                "grain_id": g.grain_id,
                "intent": g.intent,
                "risk_class": g.risk_class,
                "model_lane": g.model_lane,
                "globs": list(g.domain.globs),
            }
            for g in plan.grains
        ],
        "outcomes": [
            {"grain_id": getattr(r, "grain_id", "?"), "state": getattr(r, "state", "?")}
            for r in (results or [])
        ],
    }
    path = _swarm_dir() / "learning_traces.jsonl"
    _append_jsonl(path, record)

    # Best-effort bridge into the JARVIS learning dataset (never fatal).
    try:
        _bridge_to_learning_dataset(record)
    except Exception:
        pass
    return path


def _bridge_to_learning_dataset(record: dict[str, Any]) -> None:
    from muse_cli.jarvis_prime.learning_dataset import DatasetStore  # noqa: F401

    # The dataset enforces strict quality gates; we only register that a swarm
    # job occurred as a provenance breadcrumb. Detailed trace promotion stays an
    # explicit, owner-approved step via the learning CLI. We intentionally do not
    # auto-insert (which would require full quality-gate metadata) — this keeps
    # the swarm loop additive and never injects unvetted traces.
    return None


@dataclass
class _Applied:
    path: Path


def applied_updates_log_path() -> Path:
    """Where auto-applied reversible updates are recorded (one JSONL)."""

    return _swarm_dir() / "applied_updates.jsonl"


def record_applied_update(proposal: Any) -> dict[str, Any]:
    """Default reversible apply: log the change + its rollback recipe.

    Returns the record written. Reversible by deleting the record; nothing in
    live config is mutated in place, so a bad auto-apply can never corrupt
    routing state — it can only add an auditable, undoable entry.
    """

    extra = dict(getattr(proposal, "extra", {}) or {})
    record = {
        "applied_at": now_iso(),
        "kind": getattr(proposal, "kind", "unknown"),
        "target": getattr(proposal, "target", ""),
        "summary": getattr(proposal, "summary", ""),
        "previous_value": extra.get("previous_value"),
        "nudge_delta": extra.get("nudge_delta") or extra.get("weight_delta"),
        "reversible": bool(getattr(proposal, "reversible", True)),
        "rollback": (
            f"Restore {getattr(proposal, 'target', '')} to "
            f"{extra.get('previous_value')!r}; delete this record."
        ),
    }
    _append_jsonl(applied_updates_log_path(), record)
    return record
