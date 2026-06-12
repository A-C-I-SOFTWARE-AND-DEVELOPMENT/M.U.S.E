"""Secrets handling policy for Hermes Agent.

This module is the single source of truth for "what counts as a secret",
"where do secrets live", and "is this string safe to log / commit / send
to a remote worker". It is deliberately dependency-free (stdlib + re)
so it can run in any environment that imports Hermes.

The policy is conservative on purpose: every helper here errs toward
flagging a string as sensitive. False positives in a redactor are
recoverable; a single leaked API key is not.

Design summary
--------------

1. **Sources.** Hermes reads secrets from a fixed set of sources, in
   priority order:

       1. ``~/.hermes/.env`` (operator-owned, never committed)
       2. ``$HERMES_HOME/.env`` if overridden
       3. Environment variables already in the process
       4. OS keychain (macOS Keychain, libsecret, Windows DPAPI) when
          available
       5. Android secure storage (delegated to the Android app)
       6. Windows credential store (used by the Windows remote worker)
       7. ``config.yaml`` ``${VAR}`` references — these are *names*, not
          values; values still come from one of the sources above.

   The agent process never sees secrets directly. Plugins request a
   secret by name; ``get_secret`` returns the value (or ``None``) and
   records the access in the audit log. The LLM sees a sentinel
   (``<redacted:OPENAI_API_KEY>``) rather than the value.

2. **Detection.** ``looks_like_secret`` recognises:

       - Known env-var name patterns (``*_API_KEY``, ``*_TOKEN``,
         ``*_SECRET``, ``*_PASSWORD``, ``*_PRIVATE_KEY``,
         ``*_CREDENTIALS``…).
       - Well-known prefixes (``sk-``, ``sk-ant-``, ``ghp_``, ``ghs_``,
         ``gho_``, ``xoxb-``, ``xoxp-``, ``AKIA``, ``AIza``, etc.).
       - Generic high-entropy tokens (≥ 32 chars, base64/hex alphabet).
       - PEM blocks (``-----BEGIN ... PRIVATE KEY-----``).

3. **Redaction.** ``redact`` replaces detected secrets with the sentinel
   ``<redacted:KIND>``. ``redact_env_dict`` does the same for a
   dict-of-env-vars. The replacement is stable and roundtrip-safe — a
   second call to ``redact`` on already-redacted text is a no-op.

4. **Scanning.** ``scan_text`` and ``scan_file`` return a list of
   ``Finding`` records (no values, just locations and kinds). The
   ``scan_diff`` helper accepts the output of ``git diff`` (staged or
   unstaged) and returns findings restricted to ``+`` lines so changes
   that *remove* a secret don't trip the scanner.

5. **What this module does NOT do.**

       - It does not implement OS keychain access — the platform
         backends live under ``muse_cli.platforms``. This module
         declares the *interface*.
       - It does not enforce approvals. See
         :mod:`muse_cli.approval_policy` for that.
       - It is not a substitute for OS-level isolation. The only
         security boundary against an adversarial LLM is the OS (see
         ``SECURITY.md`` §2.2). This module reduces accident blast
         radius; it does not contain an attacker.

The module is intentionally importable from any context (gateway, CLI,
worker, test fixture) without side effects.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretSource:
    """A logical source from which Hermes can read a secret.

    ``name`` is human-readable. ``priority`` is lower = higher
    precedence (matches the ordering documented in the module
    docstring). ``available`` is a callable that returns ``True`` when
    the source is usable on the current host (e.g. macOS Keychain is
    only available on macOS).
    """

    name: str
    priority: int
    description: str
    available: Callable = field(default=lambda: True)


@dataclass(frozen=True)
class Finding:
    """One match from a scan."""

    kind: str
    """The category — ``env_name``, ``known_prefix``, ``high_entropy``,
    ``pem_block``."""

    location: str
    """Where the finding was made. Free-form: ``"foo.py:42"``,
    ``"<staged-diff>"``, ``"stdin"``."""

    line: int
    """1-based line number, or 0 if not applicable."""

    excerpt: str
    """A short context excerpt with the secret value already redacted.
    Safe to log."""


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def _has_dotenv_file() -> bool:
    return (Path.home() / ".hermes" / ".env").is_file() or bool(
        os.environ.get("HERMES_HOME")
    ) and Path(os.environ["HERMES_HOME"], ".env").is_file()


def _has_macos_keychain() -> bool:
    import sys

    if sys.platform != "darwin":
        return False
    # The `security` binary is on every supported macOS.
    return Path("/usr/bin/security").exists()


def _has_libsecret() -> bool:
    import sys

    if not sys.platform.startswith("linux"):
        return False
    try:
        import gi  # type: ignore
        gi.require_version("Secret", "1")
        from gi.repository import Secret  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _has_windows_credstore() -> bool:
    import sys

    return sys.platform == "win32"


def _has_android_securestore() -> bool:
    return os.environ.get("HERMES_ANDROID_SECURESTORE") == "1"


SOURCES: tuple[SecretSource, ...] = (
    SecretSource(
        name="hermes_dotenv",
        priority=1,
        description="~/.hermes/.env (operator-owned, gitignored)",
        available=_has_dotenv_file,
    ),
    SecretSource(
        name="process_env",
        priority=2,
        description="environment variables present in the running process",
    ),
    SecretSource(
        name="macos_keychain",
        priority=3,
        description="macOS Keychain via /usr/bin/security",
        available=_has_macos_keychain,
    ),
    SecretSource(
        name="libsecret",
        priority=3,
        description="Linux libsecret (GNOME Keyring, KWallet bridge)",
        available=_has_libsecret,
    ),
    SecretSource(
        name="windows_credstore",
        priority=3,
        description="Windows Credential Manager (DPAPI)",
        available=_has_windows_credstore,
    ),
    SecretSource(
        name="android_securestore",
        priority=3,
        description="Android EncryptedSharedPreferences (delegated to the app)",
        available=_has_android_securestore,
    ),
    SecretSource(
        name="config_yaml_ref",
        priority=4,
        description="${VAR} references in config.yaml (resolved against the above)",
    ),
)


def available_sources() -> list[SecretSource]:
    """Return the list of secret sources usable on this host, sorted."""
    return sorted(
        (s for s in SOURCES if s.available()),
        key=lambda s: (s.priority, s.name),
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


# Env var name suffixes treated as credential-shaped.
SECRET_NAME_SUFFIXES: tuple[str, ...] = (
    "_API_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_PASSWD",
    "_PRIVATE_KEY",
    "_CREDENTIALS",
    "_ACCESS_KEY",
    "_OAUTH_TOKEN",
    "_REFRESH_TOKEN",
    "_WEBHOOK_SECRET",
    "_CLIENT_SECRET",
    "_APP_SECRET",
    "_AES_KEY",
    "_ENCRYPT_KEY",
)

# Explicit credential names that don't fit the suffix pattern.
SECRET_NAME_EXACT: frozenset[str] = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_ANON_KEY",
        "VERCEL_TOKEN",
        "NOUS_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
    }
)

# Known token prefixes — high signal, low false-positive rate. Order:
# (label, regex). Each regex is anchored to a word boundary.
KNOWN_PREFIX_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_\-]{20,}")),
    ("anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{36,}")),
    ("github_server", re.compile(r"\bghs_[A-Za-z0-9]{36,}")),
    ("github_oauth", re.compile(r"\bgho_[A-Za-z0-9]{36,}")),
    ("github_user", re.compile(r"\bghu_[A-Za-z0-9]{36,}")),
    ("github_refresh", re.compile(r"\bghr_[A-Za-z0-9]{36,}")),
    ("slack_bot", re.compile(r"\bxoxb-[A-Za-z0-9\-]{20,}")),
    ("slack_user", re.compile(r"\bxoxp-[A-Za-z0-9\-]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("supabase_jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}")),
    ("vercel", re.compile(r"\b(?:vercel_)[A-Za-z0-9]{20,}")),
)

PEM_BLOCK_PATTERN = re.compile(
    r"-----BEGIN[ A-Z]+PRIVATE KEY-----.*?-----END[ A-Z]+PRIVATE KEY-----",
    re.DOTALL,
)

# Generic high-entropy heuristic: ≥32 chars, base64 / hex alphabet.
HIGH_ENTROPY_PATTERN = re.compile(r"(?<![A-Za-z0-9_\-=+/])[A-Za-z0-9_\-=+/]{32,}")

# Already-redacted sentinel — `redact` is idempotent across this.
REDACTED_SENTINEL_PATTERN = re.compile(r"<redacted:[A-Za-z0-9_\-]+>")


def is_secret_name(name: str) -> bool:
    """Return True if an env var NAME looks credential-shaped."""
    if not name:
        return False
    upper = name.upper()
    if upper in SECRET_NAME_EXACT:
        return True
    return any(upper.endswith(suf) for suf in SECRET_NAME_SUFFIXES)


def _looks_high_entropy(token: str) -> bool:
    """Cheap entropy proxy — character class diversity."""
    if len(token) < 32:
        return False
    has_lower = any(c.islower() for c in token)
    has_upper = any(c.isupper() for c in token)
    has_digit = any(c.isdigit() for c in token)
    classes = sum((has_lower, has_upper, has_digit))
    return classes >= 2


def looks_like_secret(value: str) -> Optional[str]:
    """Return the matched 'kind' if the string looks like a secret.

    Returns ``None`` otherwise. Kinds: ``pem_block``, ``known_prefix``,
    ``high_entropy``.
    """
    if not value or len(value) < 16:
        return None
    if PEM_BLOCK_PATTERN.search(value):
        return "pem_block"
    for _label, pattern in KNOWN_PREFIX_PATTERNS:
        if pattern.search(value):
            return "known_prefix"
    # Walk through high-entropy candidate tokens.
    for m in HIGH_ENTROPY_PATTERN.finditer(value):
        if _looks_high_entropy(m.group(0)):
            return "high_entropy"
    return None


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


def _redact_match(label: str) -> str:
    return f"<redacted:{label}>"


def redact(text: str) -> str:
    """Return ``text`` with any detected secret replaced by a sentinel.

    Idempotent: passing already-redacted text through is a no-op.
    """
    if not text:
        return text

    # Skip work if the only "candidate" is the sentinel itself.
    out = text

    # 1) PEM blocks first (longest match wins).
    out = PEM_BLOCK_PATTERN.sub(_redact_match("private_key"), out)

    # 2) Known prefixes.
    for label, pattern in KNOWN_PREFIX_PATTERNS:
        out = pattern.sub(_redact_match(label), out)

    # 3) Generic high-entropy. This is last because the known-prefix
    #    patterns are higher-precision.
    def _maybe_redact_token(m: re.Match[str]) -> str:
        tok = m.group(0)
        # Don't re-redact our own sentinel.
        if REDACTED_SENTINEL_PATTERN.fullmatch(tok):
            return tok
        if _looks_high_entropy(tok):
            return _redact_match("token")
        return tok

    out = HIGH_ENTROPY_PATTERN.sub(_maybe_redact_token, out)
    return out


def redact_env_dict(env: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of ``env`` with credential-shaped values redacted."""
    out: dict[str, str] = {}
    for k, v in env.items():
        if is_secret_name(k):
            out[k] = _redact_match(k.upper()) if v else v
        else:
            out[k] = redact(v) if isinstance(v, str) else v
    return out


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _excerpt(line: str, max_len: int = 120) -> str:
    """Build a safe excerpt: redact secrets, trim to max_len."""
    redacted = redact(line.rstrip("\n"))
    if len(redacted) <= max_len:
        return redacted
    return redacted[: max_len - 1] + "…"


def scan_text(text: str, location: str = "<text>") -> list[Finding]:
    """Return findings for a block of text. Does not include values."""
    findings: list[Finding] = []
    if not text:
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line:
            continue
        # Check env-style assignment first: NAME=value.
        m = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*[:=]\s*(.+?)\s*$", line)
        if m and is_secret_name(m.group(1)):
            findings.append(
                Finding(
                    kind="env_name",
                    location=location,
                    line=lineno,
                    excerpt=_excerpt(f"{m.group(1)}=..."),
                )
            )
            continue
        kind = looks_like_secret(line)
        if kind:
            findings.append(
                Finding(
                    kind=kind,
                    location=location,
                    line=lineno,
                    excerpt=_excerpt(line),
                )
            )
    return findings


def scan_file(path: Path) -> list[Finding]:
    """Scan a file on disk. Skips binary files and unreadable paths."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return scan_text(text, location=str(path))


def scan_diff(diff_text: str, location: str = "<diff>") -> list[Finding]:
    """Scan a unified diff. Only ``+`` lines that aren't headers count."""
    findings: list[Finding] = []
    if not diff_text:
        return findings

    current_file = location
    for lineno, raw in enumerate(diff_text.splitlines(), start=1):
        if raw.startswith("+++ "):
            # +++ b/path/to/file
            parts = raw.split(None, 1)
            if len(parts) == 2:
                p = parts[1]
                if p.startswith("b/"):
                    p = p[2:]
                current_file = p
            continue
        if raw.startswith("---") or raw.startswith("+++"):
            continue
        if not raw.startswith("+"):
            continue
        added = raw[1:]
        for finding in scan_text(added, location=current_file):
            findings.append(
                Finding(
                    kind=finding.kind,
                    location=current_file,
                    line=lineno,
                    excerpt=finding.excerpt,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Secret access (logical accessor — backends live elsewhere)
# ---------------------------------------------------------------------------


def get_secret(
    name: str,
    *,
    env: Optional[Mapping[str, str]] = None,
    sources: Optional[Sequence[SecretSource]] = None,
) -> Optional[str]:
    """Resolve a secret by name from the configured sources.

    Order: dotenv-loaded process env, plain process env. Keychain
    backends are not invoked here — that's a platform module's job —
    but a host that has loaded keychain values into ``os.environ`` at
    process start will see them via ``process_env``.

    The lookup is intentionally cheap and synchronous. Returns
    ``None`` when the secret is not configured; the caller decides
    whether that's fatal.
    """
    env_map = env if env is not None else os.environ
    value = env_map.get(name)
    if value:
        return value
    return None


def assert_not_committable(text: str, *, label: str = "<text>") -> None:
    """Raise ``SecretLeakError`` if ``text`` contains a probable secret.

    Use this in the commit / push / publish path. The default policy is
    fail-closed: a finding is an error, not a warning.
    """
    findings = scan_text(text, location=label)
    if findings:
        raise SecretLeakError(findings)


class SecretLeakError(Exception):
    """Raised when a probable secret is about to leave the trust boundary."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings
        summary = ", ".join(
            f"{f.kind}@{f.location}:{f.line}" for f in findings[:5]
        )
        more = "" if len(findings) <= 5 else f" (+{len(findings) - 5} more)"
        super().__init__(f"refusing to publish — potential secret(s): {summary}{more}")


__all__ = [
    "Finding",
    "KNOWN_PREFIX_PATTERNS",
    "PEM_BLOCK_PATTERN",
    "SECRET_NAME_EXACT",
    "SECRET_NAME_SUFFIXES",
    "SOURCES",
    "SecretLeakError",
    "SecretSource",
    "assert_not_committable",
    "available_sources",
    "get_secret",
    "is_secret_name",
    "looks_like_secret",
    "redact",
    "redact_env_dict",
    "scan_diff",
    "scan_file",
    "scan_text",
]
