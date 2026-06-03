"""Append-only raw tool-output log (debug fidelity).

Records the **pre-scrub** full raw output of a tool call so that compaction and
scrubbing never destroy debuggability. The log is local-first, gitignored, and
**never auto-read back into the model context** — it exists for humans and
explicit debug tooling only.

Location: ``$HERMES_HOME/tool-raw/<session>/<tool_use_id>.log`` (default
``~/.hermes/tool-raw/...``). Writes fail open: a logging failure never breaks the
tool loop.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _base_dir() -> Path:
    home = os.environ.get("HERMES_HOME") or os.path.join(os.path.expanduser("~"), ".hermes")
    return Path(home) / "tool-raw"


def _safe(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in (name or "unknown"))[:120]


def record(
    *,
    session_id: Optional[str],
    tool_use_id: Optional[str],
    tool_name: str,
    arguments: Any,
    raw_output: str,
    exit_code: Optional[int] = None,
) -> Optional[str]:
    """Persist one raw tool result. Returns the file path, or ``None`` on failure."""
    try:
        session = _safe(session_id or "session")
        directory = _base_dir() / session
        directory.mkdir(parents=True, exist_ok=True)
        tid = _safe(tool_use_id or f"{tool_name}-{int(time.time() * 1000)}")
        path = directory / f"{tid}.log"
        header = {
            "ts": time.time(),
            "tool": tool_name,
            "tool_use_id": tool_use_id,
            "exit_code": exit_code,
            "arguments": arguments if _json_safe(arguments) else str(arguments),
            "chars": len(raw_output or ""),
        }
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(header, ensure_ascii=False) + "\n")
            fh.write(raw_output or "")
        return str(path)
    except Exception as err:  # fail open — never break the tool loop
        logger.debug("[tokenjuice] raw_log.record failed: %s", err)
        return None


def _json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False
