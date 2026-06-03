"""Secret redaction for cockpit ledger projections.

The mobile *Activity timeline* (``/v1/cockpit/ledger``) projects the
orchestrator's per-job event ledger, whose entries can carry verbatim
worker output, command lines, and diffs — any of which might contain a
credential a worker accidentally echoed. This module scrubs that material
before it ever leaves the loopback API.

Design choices:

* **Detection mirrors the memory write-gate.** The standalone-token
  patterns (private-key blocks, AWS keys, ``sk-``/``gh*``/``xox*`` tokens,
  bearer headers) mirror
  :data:`hermes_cli.jarvis_prime.memory_tree._SECRET_PATTERNS`, so the
  cockpit and the gate agree on what a secret looks like. The capture-group
  patterns here exist so the *replacement* can preserve the key name
  (``API_KEY=[REDACTED]`` reads better than ``[REDACTED]``) — the Android
  ``SecretRedactor`` uses the same shape, so both layers redact identically
  (defense in depth).
* **Conservative.** Favors over-redaction; the cost of leaking one real
  secret dwarfs the cost of redacting a lookalike.
* **Recursive.** :func:`redact_value` walks dicts/lists/strings so a whole
  ledger entry can be scrubbed in one call without the caller enumerating
  fields.

Stdlib-only at import time.
"""

from __future__ import annotations

import re
from typing import Any

REDACTION_MARKER = "[REDACTED]"

# Capture-group patterns whose *value* is replaced (key/prefix preserved).
# Mirrors the Android com.aci.hermes.data.audit.SecretRedactor patterns so
# the two redaction layers produce identical output.
_KEY_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<key>
      (?:[A-Z][A-Z0-9_]*_)?
      (?:api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|
         private[_-]?key|client[_-]?secret|auth|bearer|session)
      [A-Z0-9_]*
    )
    (?P<delim>\s*[:=]\s*)
    (?P<quote>["']?)
    (?P<value>[^\s"',;]+)
    (?P=quote)
    """,
)

_AUTH_HEADER_RE = re.compile(
    r"(?i)(authorization\s*:\s*)(bearer\s+|basic\s+)?([A-Za-z0-9+/=._\-]{12,})",
)

# Standalone whole-match tokens — replaced wholesale. These mirror
# ``hermes_cli.jarvis_prime.memory_tree._SECRET_PATTERNS`` (the memory
# write-gate) so the cockpit and the gate agree on what a secret looks like.
# They are re-listed locally rather than imported-and-filtered: the gate's
# tuple also carries the key=value and bearer shapes, which we handle above
# via capture groups so the *replacement* can preserve the key name. Keeping
# an explicit local list means a change to the gate's tuple order can't
# silently alter cockpit redaction.
_WHOLE_MATCH_RE = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"sk-(?:proj-|live-|test-)?[A-Za-z0-9\-_]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
)


def redact_text(text: Any) -> str:
    """Return ``text`` with secret-like substrings replaced by the marker.

    Non-strings are coerced via ``str``; ``None``/empty yields ``""``.
    """
    if text is None:
        return ""
    result = text if isinstance(text, str) else str(text)
    if not result:
        return ""

    for pat in _WHOLE_MATCH_RE:
        result = pat.sub(REDACTION_MARKER, result)

    def _auth(match: re.Match[str]) -> str:
        token = match.group(3)
        if token == REDACTION_MARKER:
            return match.group(0)
        return match.group(1) + (match.group(2) or "") + REDACTION_MARKER

    result = _AUTH_HEADER_RE.sub(_auth, result)

    def _kv(match: re.Match[str]) -> str:
        if match.group("value") == REDACTION_MARKER:
            return match.group(0)
        quote = match.group("quote") or ""
        return f"{match.group('key')}{match.group('delim')}{quote}{REDACTION_MARKER}{quote}"

    result = _KEY_VALUE_RE.sub(_kv, result)
    return result


def contains_secret(text: Any) -> bool:
    """True when ``text`` carries a secret-like substring."""
    if text is None:
        return False
    s = text if isinstance(text, str) else str(text)
    if not s:
        return False
    if any(p.search(s) for p in _WHOLE_MATCH_RE):
        return True
    if any(m.group(3) != REDACTION_MARKER for m in _AUTH_HEADER_RE.finditer(s)):
        return True
    return any(m.group("value") != REDACTION_MARKER for m in _KEY_VALUE_RE.finditer(s))


def redact_value(value: Any, *, max_str: int = 2000) -> Any:
    """Recursively redact strings inside dicts/lists/tuples.

    Strings are scrubbed and truncated to ``max_str`` chars (ledger payloads
    can be large; the mobile timeline only needs a readable excerpt). Scalars
    other than ``str`` pass through unchanged. Keys are left intact (they are
    field names, not values).
    """
    if isinstance(value, str):
        out = redact_text(value)
        if len(out) > max_str:
            out = out[: max_str - 1].rstrip() + "…"
        return out
    if isinstance(value, dict):
        return {k: redact_value(v, max_str=max_str) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v, max_str=max_str) for v in value]
    return value


__all__ = [
    "REDACTION_MARKER",
    "contains_secret",
    "redact_text",
    "redact_value",
]
