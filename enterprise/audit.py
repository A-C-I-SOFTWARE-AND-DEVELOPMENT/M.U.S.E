"""Structured audit trail for enterprise council runs.

One JSONL file per session, written under ``~/.hermes/enterprise/audit/``
(or the path returned by ``get_hermes_home()`` if Hermes' own helper is
available — falls back to the default if not, so tests don't have to
mount the full Hermes layout).

Each row is a single JSON object with a stable schema. Things we
deliberately do NOT include in audit rows:
  * Raw secret values — even where a secret was fetched, we log only
    the fingerprint emitted by ``enterprise.secrets.secret_fingerprint``.
  * Verbatim tool args — we hash them (args_hash) so a reviewer can
    confirm "same inputs as the previous run" without storing the
    actual payload.
  * Free-form model output — the agent's final structured result is
    captured by ``result_hash`` + ``result_summary`` (≤200 chars).

The Monitor agent consumes this file to propose improvements. The
schema below is the contract the Monitor relies on; don't break it
silently.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from enterprise.policy import Risk

_logger = logging.getLogger("enterprise.audit")


def _audit_dir() -> Path:
    """Pick the right directory for audit files, falling back when Hermes' helpers
    aren't importable (e.g. in a stripped-down test environment).
    """
    try:
        from muse_cli.config import get_hermes_home  # local import — heavy

        base = Path(get_hermes_home())
    except Exception:
        base = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    target = base / "enterprise" / "audit"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _hash(obj: Any) -> str:
    """Stable short hash for an audit row's args/result.

    JSON-serialise with sorted keys so structurally-equal inputs hash
    the same. Non-JSON values fall back to their ``repr``.
    """

    def default(value: Any) -> str:
        return repr(value)

    try:
        text = json.dumps(obj, sort_keys=True, default=default)
    except Exception:
        text = repr(obj)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class AuditEvent:
    """One structured row in the audit trail.

    Field order in the dataclass is the on-disk JSON key order (Python
    3.7+ dicts preserve insertion order, and ``asdict`` follows the
    field declaration order).
    """

    ts: float
    session_id: str
    event: str  # one of: plan | dispatch | leaf_result | judge | escalate | retry | done | improvement
    agent: str  # "orchestrator" | "judge" | "monitor" | "<domain>"
    tool: Optional[str] = None
    args_hash: Optional[str] = None
    result_hash: Optional[str] = None
    result_summary: str = ""
    risk: Optional[str] = None  # Risk.value
    validation: Optional[str] = (
        None  # "ok" | "schema_fail" | "policy_fail" | "judge_disagree" | "escalated"
    )
    retry_count: int = 0
    duration_ms: Optional[float] = None
    secret_fingerprints: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


def _redact_summary(text: str, max_len: int = 200) -> str:
    """Truncate + run the redactor over a free-form summary string."""
    if not text:
        return ""
    snippet = text.strip().replace("\n", " ")[:max_len]
    try:
        from agent.redact import redact_sensitive_text

        return redact_sensitive_text(snippet, force=True)
    except Exception:  # pragma: no cover — redactor present in any real env
        return snippet


def _build_event(
    *,
    session_id: str,
    event: str,
    agent: str,
    tool: Optional[str] = None,
    args: Optional[Mapping[str, Any]] = None,
    result: Any = None,
    result_summary: str = "",
    risk: Optional[Risk] = None,
    validation: Optional[str] = None,
    retry_count: int = 0,
    duration_ms: Optional[float] = None,
    secret_fingerprints: tuple[str, ...] = (),
    extra: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    return AuditEvent(
        ts=time.time(),
        session_id=session_id,
        event=event,
        agent=agent,
        tool=tool,
        args_hash=_hash(dict(args)) if args else None,
        result_hash=_hash(result) if result is not None else None,
        result_summary=_redact_summary(result_summary),
        risk=risk.value if isinstance(risk, Risk) else None,
        validation=validation,
        retry_count=retry_count,
        duration_ms=duration_ms,
        secret_fingerprints=tuple(secret_fingerprints),
        extra=dict(extra or {}),
    )


def audit(
    session_id: str,
    event: str,
    agent: str,
    **kwargs: Any,
) -> AuditEvent:
    """Append one row to the session's audit file and return the event.

    The file path is ``<audit_dir>/<session_id>.jsonl``. Each call opens
    in append mode so concurrent leaves writing to the same session
    don't lose rows. Writes are line-flushed so a crash mid-session
    leaves a valid prefix on disk.
    """
    ev = _build_event(session_id=session_id, event=event, agent=agent, **kwargs)
    path = _audit_dir() / f"{session_id}.jsonl"
    row = asdict(ev)
    line = json.dumps(row, default=str, sort_keys=False)
    # Belt and braces: scrub the rendered line through the redactor too,
    # in case a caller passed a free-form string we didn't hash.
    try:
        from agent.redact import redact_sensitive_text

        line = redact_sensitive_text(line, force=True)
    except Exception:  # pragma: no cover
        pass
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    _logger.debug("audit %s/%s/%s -> %s", session_id, event, agent, path)
    return ev


def read_events(session_id: str) -> list[AuditEvent]:
    """Load every row for ``session_id``. Used by the Monitor and tests."""
    path = _audit_dir() / f"{session_id}.jsonl"
    if not path.exists():
        return []
    out: list[AuditEvent] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        data = json.loads(raw)
        # `extra` may be missing on rows written before that field existed;
        # AuditEvent has defaults, so unpack what we have.
        try:
            out.append(AuditEvent(**data))
        except TypeError:
            # Forward-compatibility: ignore unknown keys.
            known = {
                k: v for k, v in data.items() if k in AuditEvent.__dataclass_fields__
            }
            out.append(AuditEvent(**known))
    return out
