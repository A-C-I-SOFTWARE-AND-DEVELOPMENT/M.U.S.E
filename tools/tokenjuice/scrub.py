"""Credential scrubbing for tool output.

Clean-room implementation: redacts common secret shapes from tool output
*before* it is compacted and shown to the model. Runs in both tool-execution
paths (see ``agent/tool_executor.py``). This closes a real pre-existing gap —
Hermes previously sent raw tool output (including any printed secrets) straight
to the model.

Design: preserve a 4-character prefix of the value for debuggability/context,
then redact the remainder. Never log the matched secret.
"""

from __future__ import annotations

import re

# key = value | key: value | key="value" | "key": "value"  (value >= 8 chars)
_SENSITIVE_KV_RE = re.compile(
    r"""(?ix)
    (token|api[_-]?key|access[_-]?key|secret|client[_-]?secret|password|passwd|
     pwd|bearer|credential|private[_-]?key|refresh[_-]?token|session[_-]?key|
     auth[_-]?token)
    (["']?\s*[:=]\s*)
    (?:"([^"]{8,})"|'([^']{8,})'|([A-Za-z0-9_\-\.\/\+]{8,}))
    """,
)

# Standalone high-entropy token shapes (provider keys, JWTs, bearer headers).
_BEARER_RE = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9_\-\.=]{12,})")
_PROVIDER_KEY_RE = re.compile(r"\b(sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{12,}|xox[baprs]-[A-Za-z0-9-]{10,})")
_PEM_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)

REDACTED = "[REDACTED]"


def _prefix(value: str, keep: int = 4) -> str:
    if len(value) > keep:
        return value[:keep]
    return ""


def _kv_sub(match: re.Match) -> str:
    key = match.group(1)
    sep = match.group(2)
    value = match.group(3) or match.group(4) or match.group(5) or ""
    quoted = '"' in sep or (match.group(3) is not None) or (match.group(4) is not None)
    prefix = _prefix(value)
    body = f"{prefix}*{REDACTED}"
    sep_clean = sep.strip()
    joiner = ": " if ":" in sep_clean else "="
    if quoted:
        return f'{key}{joiner}"{body}"'
    return f"{key}{joiner}{body}"


def scrub_credentials(text: str) -> str:
    """Redact common credential patterns from ``text``.

    Pass-through safe: returns the input unchanged when no patterns match.
    Order matters — PEM blocks first (multiline), then standalone provider keys
    and bearer headers, then generic key/value pairs.
    """
    if not text:
        return text
    out = _PEM_RE.sub(f"-----BEGIN PRIVATE KEY----- {REDACTED} -----END PRIVATE KEY-----", text)
    out = _PROVIDER_KEY_RE.sub(lambda m: f"{_prefix(m.group(1))}*{REDACTED}", out)
    out = _BEARER_RE.sub(lambda m: f"Bearer {_prefix(m.group(1))}*{REDACTED}", out)
    out = _SENSITIVE_KV_RE.sub(_kv_sub, out)
    return out
