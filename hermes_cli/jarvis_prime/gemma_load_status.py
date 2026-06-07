"""Persisted "does this Gemma variant load cleanly?" status.

The router's local-default policy says coding/reasoning lanes use ``gemma4-e4b``
*only if it loads cleanly* on this host — otherwise they fall back to the
lighter ``gemma4-e2b``. "Loads cleanly" is not something the router can probe
inline (spawning local inference must stay an explicit operator choice), so this
module gives a tiny **persisted record** that the opt-in smoke check writes and
the router reads:

* ``record_status(variant, ok, detail)`` — called by ``hermes models gemma
  smoke`` after a real ``ollama run`` completion (success or failure).
* ``variant_failed(variant)`` — the router's gate: ``True`` **only** when a
  smoke check is on record *and* it failed. Unknown / never-probed / passed all
  read as "don't downgrade", so a fresh install is never penalised — the gate
  only demotes a variant that has *demonstrably* failed to load.

The store lives at ``${HERMES_HOME:-~/.hermes}/jarvis_prime/gemma_load_status.json``
and is written atomically (temp file + ``os.replace``), 0600, mirroring the
``model_route_overrides.json`` / scorecard write pattern. stdlib-only; every
read degrades to an empty map so a stripped or read-only install stays inert.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1

# Statuses we persist. "ok" = a completion succeeded; "failed" = the runner ran
# but did not produce a clean completion (OOM, missing tag, error).
STATUS_OK = "ok"
STATUS_FAILED = "failed"


def status_path() -> Path:
    """``${HERMES_HOME:-~/.hermes}/jarvis_prime/gemma_load_status.json``."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "gemma_load_status.json"


def canonical_variant(variant: str) -> str:
    """Normalise a variant/tag spelling to the catalog ``gemma4-e4b`` form.

    Accepts ``gemma4-e4b``, ``gemma4:e4b``, ``ollama-local/gemma4-e2b`` and
    ``gemma4:26b`` → ``gemma4-26b``. Best-effort; unknown shapes pass through
    lowercased so the store never raises on an odd key.
    """
    name = (variant or "").strip().lower()
    name = name.rsplit("/", 1)[-1]  # drop any provider prefix
    name = name.replace(":", "-")   # gemma4:e4b -> gemma4-e4b
    return name


def load_status(path: Optional[Path] = None) -> dict[str, Any]:
    """Return the persisted status map (``{}`` when absent/unreadable)."""
    target = Path(path) if path else status_path()
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data.get("variants", {}) if "variants" in data else data


def record_status(
    variant: str,
    ok: bool,
    detail: str = "",
    *,
    path: Optional[Path] = None,
) -> Path:
    """Persist a variant's load result atomically. Returns the file path."""
    target = Path(path) if path else status_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    variants = load_status(target)
    variants[canonical_variant(variant)] = {
        "status": STATUS_OK if ok else STATUS_FAILED,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "detail": (detail or "")[:200],
    }
    payload = {"version": SCHEMA_VERSION, "variants": variants}
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".gemma-load-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def variant_status(variant: str, *, status_map: Optional[dict[str, Any]] = None) -> Optional[str]:
    """Return the recorded status string for a variant, or ``None`` if unknown."""
    variants = status_map if status_map is not None else load_status()
    entry = variants.get(canonical_variant(variant))
    if isinstance(entry, dict):
        return entry.get("status")
    return None


def variant_failed(variant: str, *, status_map: Optional[dict[str, Any]] = None) -> bool:
    """The router gate: ``True`` only when a smoke check is on record AND failed.

    Unknown / never-probed / passed → ``False`` (don't downgrade). This keeps a
    fresh install routing optimistically while honouring a *demonstrated* load
    failure.
    """
    return variant_status(variant, status_map=status_map) == STATUS_FAILED


__all__ = [
    "SCHEMA_VERSION",
    "STATUS_OK",
    "STATUS_FAILED",
    "status_path",
    "canonical_variant",
    "load_status",
    "record_status",
    "variant_status",
    "variant_failed",
]
