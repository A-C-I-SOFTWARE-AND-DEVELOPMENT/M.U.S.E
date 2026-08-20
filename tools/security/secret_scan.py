"""Credential scanner for M.U.S.E. — Work Packet §9.2, §4.1, Appendix A.

Why this exists
---------------
§9.2 asks for a *dedicated secret scanner run against the exact commit, with
hand triage and a versioned suppression file*. Checked first (2026-08-16, this
machine): ``detect-secrets``, ``gitleaks``, ``trufflehog``, ``ggshield`` and
``git-secrets`` are all absent from ``PATH``, and ``detect_secrets`` is not
importable from the project venv either. So
this is the fallback the item allows for.

What it must not become
-----------------------
The packet is emphatic (§29.2): **a heuristic count is a triage aid and never a
finding of leaked credentials, and no no-secret claim may be made from it.**
This module is built so that its output cannot easily be mistaken for one:

* every record is a **location** — path, line, column — plus derived *features*
  of the match. **The matched value is never stored, printed, logged or
  hashed into any output.**
* every record carries a *proposed* triage bucket, explicitly labelled a
  proposal, and the suppression file records who hand-triaged it and why.
* the report header states the prohibition in the output itself.

Beyond shape-matching
---------------------
A shape matcher ("something that looks like ``key = "..."``") produces a queue
nobody walks. Three signals are layered on top:

1. **Known key prefixes.** AWS ``AKIA``/``ASIA``, GitHub ``ghp_``/``github_pat_``,
   Slack ``xox*``, OpenAI ``sk-``/``sk-proj-``, Anthropic ``sk-ant-``, Google
   ``AIza``, Stripe ``sk_live_``, SendGrid ``SG.``, npm ``npm_``, PyPI
   ``pypi-``, Hugging Face ``hf_``, GitLab ``glpat-``, NVIDIA ``nvapi-``,
   Telegram bot tokens, JWTs, PEM private-key headers, and passwords inside
   URI authorities. A prefix hit is structurally *stronger* evidence than a
   shape hit and is labelled ``known_prefix`` so triage can sort by it.

2. **Entropy scoring.** Shannon entropy in bits/char over the candidate, plus
   its character-set class. ``changeme``/``your-api-key-here`` scores low;
   a real random key scores high. Reported as a number, never as a verdict.

3. **Context.** Is the hit inside a test fixture, a documentation example, the
   project's own secret-*redaction* code (which necessarily contains
   credential-shaped patterns as data), vendored third-party code, or the
   recovered-source archive? Determined from the path and from redaction
   vocabulary in the surrounding lines.

Fingerprints
------------
A finding's identity is ``sha256(rule | relpath | line-with-the-match-replaced-
by-a-fixed-token)``, truncated. Line numbers are deliberately excluded so a
suppression survives edits above it, and the value is excluded so the
suppression file is not a credential oracle. Two identical-looking lines in one
file share a fingerprint; that is stated rather than hidden, and it means a
suppression covers that shape in that file.

Usage
-----
::

    python -m tools.security.secret_scan --root . --json report.json
    python -m tools.security.secret_scan --root . --suppressions tools/security/secret_scan_suppressions.json
    python -m tools.security.secret_scan --root . --propose-suppressions proposed.json
    python -m tools.security.secret_scan --selftest

Read-only: it opens files for reading, never imports or executes them, and never
writes inside ``--root`` (``--json`` / ``--propose-suppressions`` targets are the
caller's problem). ``sys.dont_write_bytecode`` is set on import so that running
the scanner out of a repository it is auditing cannot leave ``__pycache__``
behind in the evidence.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.dont_write_bytecode = True

SCANNER_NAME = "tools/security/secret_scan.py"
SCANNER_VERSION = 1
SUPPRESSION_FILE_VERSION = 1

REDACTED = "<REDACTED>"

# The five buckets §9.2 asks for, plus two declared extensions.
#
# `archived_source` is separate from `vendor` because "third-party code we
# vendored" and "our own code recovered from an archive" are different claims,
# and merging them would misdescribe the second.
#
# `not_a_credential` covers matches that are provably not a credential value at
# all: a substitution reference (`${VAR}`, `env(VAR)`, `{token_path}`), a shell
# command substitution (`$(hermes cockpit token)`), or a sentinel constant — a
# fixed marker string such as no-key-required bound to an api_key variable.
# Calling those "doc examples" would be wrong: they are production code that
# never holds a secret.
TRIAGE_BUCKETS = (
    "true_positive",
    "test_fixture",
    "doc_example",
    "redaction_code",
    "vendor",
    "archived_source",
    "not_a_credential",
    "unreviewed",
)

DISCLAIMER = (
    "Work Packet 29.2: these are heuristic locations and are a TRIAGE AID, NOT "
    "a finding of leaked credentials. No matched value is stored here. This "
    "file licenses no no-secret and no no-vulnerability claim in either "
    "direction."
)

# ---------------------------------------------------------------------------
# Walk policy
# ---------------------------------------------------------------------------

# Packet §4.1 exclusion set, plus the usual cache/output directories.
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        "site-packages",
        "dist",
        "build",
        ".gradle",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".next",
        ".nuxt",
        ".parcel-cache",
        ".turbo",
        ".terraform",
        "Pods",
        ".idea",
        ".vs",
        ".vscode-test",
        "coverage",
        "htmlcov",
    }
)

# Virtualenv directories are identified by name; the packet names them too.
VENV_DIR_NAMES = frozenset({".venv", "venv", ".env-venv", "virtualenv"})

BINARY_SUFFIXES = frozenset(
    """
    .png .jpg .jpeg .gif .bmp .ico .icns .webp .tiff .svgz .avif .heic
    .mp3 .mp4 .wav .ogg .flac .avi .mov .mkv .webm .m4a .aac
    .zip .gz .tgz .bz2 .xz .7z .rar .tar .whl .jar .war .apk .aab .dmg .iso
    .exe .dll .so .dylib .bin .obj .o .a .lib .pdb .class .pyc .pyo .pyd
    .pdf .doc .docx .xls .xlsx .ppt .pptx .odt .ods
    .ttf .otf .woff .woff2 .eot
    .pkl .pickle .npy .npz .pt .pth .ckpt .safetensors .onnx .gguf .ggml .cact
    .parquet .arrow .feather .db .sqlite .sqlite3 .mdb .realm
    .blend .fbx .obj3d .glb .gltf .usd .usdz .uasset .umap .psd .exr .hdr
    .map .wasm .node
    """.split()
)

DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".adoc", ".mdx"})

DEFAULT_MAX_BYTES = 2 * 1024 * 1024


def _is_excluded_dir(name: str) -> bool:
    return name in EXCLUDED_DIR_NAMES or name in VENV_DIR_NAMES


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    name: str
    kind: str  # known_prefix | structural | shape
    pattern: re.Pattern[str]
    group: int
    description: str
    min_entropy: float = 0.0
    min_length: int = 0


def _c(pattern: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(pattern, flags)


# Order matters: the most specific rule wins when two matches overlap.
RULES: Tuple[Rule, ...] = (
    Rule(
        "aws_access_key_id",
        "known_prefix",
        _c(r"\b((?:AKIA|ASIA|ABIA|ACCA|AIDA|AROA|AGPA|ANPA|ANVA|APKA)[0-9A-Z]{16})\b"),
        1,
        "AWS access key ID prefix + 16 uppercase alphanumerics",
    ),
    Rule(
        "github_pat_fine_grained",
        "known_prefix",
        _c(r"\b(github_pat_[A-Za-z0-9_]{50,255})\b"),
        1,
        "GitHub fine-grained personal access token",
    ),
    Rule(
        "github_token",
        "known_prefix",
        _c(r"\b(gh[pousr]_[A-Za-z0-9]{30,255})\b"),
        1,
        "GitHub classic PAT / OAuth / user-to-server / server / refresh token",
    ),
    Rule(
        "gitlab_pat",
        "known_prefix",
        _c(r"\b(glpat-[A-Za-z0-9_\-]{20,})\b"),
        1,
        "GitLab personal access token",
    ),
    Rule(
        "slack_token",
        "known_prefix",
        _c(r"\b(xox[baprse]-[A-Za-z0-9\-]{10,})\b"),
        1,
        "Slack bot/app/user/refresh token",
    ),
    Rule(
        "slack_webhook",
        "known_prefix",
        _c(r"(https://hooks\.slack\.com/services/T[A-Za-z0-9_/\-]{20,})"),
        1,
        "Slack incoming-webhook URL",
    ),
    Rule(
        "anthropic_api_key",
        "known_prefix",
        _c(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})\b"),
        1,
        "Anthropic API key",
    ),
    Rule(
        "openrouter_api_key",
        "known_prefix",
        _c(r"\b(sk-or-v1-[A-Za-z0-9]{32,})\b"),
        1,
        "OpenRouter API key",
    ),
    Rule(
        "stripe_secret_key",
        "known_prefix",
        _c(r"\b((?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,})\b"),
        1,
        "Stripe secret/restricted key",
    ),
    Rule(
        "openai_api_key",
        "known_prefix",
        _c(r"\b(sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,})\b"),
        1,
        "OpenAI-style API key (also used by many OpenAI-compatible providers)",
    ),
    Rule(
        "google_api_key",
        "known_prefix",
        _c(r"\b(AIza[0-9A-Za-z_\-]{35})\b"),
        1,
        "Google API key",
    ),
    Rule(
        "sendgrid_api_key",
        "known_prefix",
        _c(r"\b(SG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,})\b"),
        1,
        "SendGrid API key",
    ),
    Rule(
        "npm_token",
        "known_prefix",
        _c(r"\b(npm_[A-Za-z0-9]{36})\b"),
        1,
        "npm automation/publish token",
    ),
    Rule(
        "pypi_token",
        "known_prefix",
        _c(r"\b(pypi-[A-Za-z0-9_\-]{32,})\b"),
        1,
        "PyPI upload token",
    ),
    Rule(
        "huggingface_token",
        "known_prefix",
        _c(r"\b(hf_[A-Za-z]{34,40})\b"),
        1,
        "Hugging Face access token",
    ),
    Rule(
        "nvidia_nim_key",
        "known_prefix",
        _c(r"\b(nvapi-[A-Za-z0-9_\-]{40,})\b"),
        1,
        "NVIDIA NIM / build.nvidia.com API key",
    ),
    Rule(
        "telegram_bot_token",
        "known_prefix",
        _c(r"\b([0-9]{8,12}:AA[A-Za-z0-9_\-]{30,})\b"),
        1,
        "Telegram bot token",
    ),
    Rule(
        "twilio_api_key_sid",
        "known_prefix",
        _c(r"\b(SK[0-9a-fA-F]{32})\b"),
        1,
        "Twilio API key SID",
    ),
    Rule(
        "private_key_header",
        "structural",
        _c(r"(-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----)"),
        1,
        "PEM private-key header",
    ),
    Rule(
        "jwt",
        "structural",
        _c(r"\b(eyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,})"),
        1,
        "JSON Web Token (three base64url segments, JSON header)",
    ),
    Rule(
        "connection_string_password",
        "structural",
        _c(r"\b[a-zA-Z][a-zA-Z0-9+.\-]{2,20}://[^\s:/@\"']{1,64}:([^\s:/@\"']{3,})@"),
        1,
        "Password inside a URI authority",
        min_entropy=1.5,
    ),
    Rule(
        "authorization_bearer_literal",
        "shape",
        _c(
            r"""(?i)\b(?:authorization|proxy-authorization)\b["']?\s*[:=]\s*["']?"""
            r"""(?:bearer|token)\s+([A-Za-z0-9._~+/=\-]{16,})"""
        ),
        1,
        "Literal bearer token in an Authorization header",
        min_entropy=3.0,
    ),
    Rule(
        "generic_secret_assignment",
        "shape",
        _c(
            r"""(?i)\b((?:api[_\-]?key|apikey|secret[_\-]?key|client[_\-]?secret|"""
            r"""auth[_\-]?token|access[_\-]?token|refresh[_\-]?token|private[_\-]?key|"""
            r"""secret|passwd|password|token))\b\s*[:=]\s*"""
            r"""["'`]([^"'`\n\r]{8,200})["'`]"""
        ),
        2,
        "A credential-named identifier assigned a quoted literal",
        min_entropy=3.0,
        min_length=12,
    ),
)

RULES_BY_NAME = {rule.name: rule for rule in RULES}


# ---------------------------------------------------------------------------
# Feature extraction (never stores the value)
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"\A[0-9a-fA-F]+\Z")
_B64URL_RE = re.compile(r"\A[A-Za-z0-9_\-]+\Z")
_B64_RE = re.compile(r"\A[A-Za-z0-9+/=]+\Z")

_PLACEHOLDER_WORDS = (
    "example",
    "sample",
    "dummy",
    "placeholder",
    "changeme",
    "change_me",
    "your",
    "yourkey",
    "yourtoken",
    "insert",
    "replace",
    "fakekey",
    "faketoken",
    "notarealkey",
    "xxxx",
    "abcdef",
    "deadbeef",
    "0123456789",
    "1234567890",
    "redacted",
    "sk-...",
    "todo",
    "n/a",
    "none",
    "null",
    "unset",
    "test",
    "fake",
    "mock",
    "stub",
    "demo",
)

# A value containing one of these is a *reference*, not a credential: the real
# value lives somewhere else and is substituted at runtime.
_TEMPLATE_MARKERS = (
    "${",
    "{{",
    "<",
    ">",
    "%s",
    "%(",
    "{0}",
    "{}",
    "…",
    "...",
    "os.environ",
    "getenv",
    "process.env",
    "env.",
    "env(",
    "%ENV",
)

# `{identifier}` — Python f-strings, .NET/JS template placeholders, TOML/YAML
# interpolation. Kept separate from the literal markers above so the reason
# string can say which kind of reference it is.
_BRACE_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_.\[\]'\"]*\}")

# `$(cmd)` and backtick command substitution in shell.
_COMMAND_SUBSTITUTION_RE = re.compile(r"\$\([^)]*\)|`[^`]+`")

_REDACTION_VOCAB = re.compile(
    r"(?i)\b(redact|redaction|scrub|sanitiz|sanitis|mask(?:ed|ing)?|"
    r"secret[_\-]?pattern|credential[_\-]?pattern|_PATTERNS\b|detect[_\-]?secret|"
    r"leak[_\-]?guard|obfuscat|anonymi[sz])"
)

_TEST_PATH_RE = re.compile(r"(?i)(^|[/\\])(tests?|testing|__tests__|fixtures?|testdata|test_data|spec|specs|e2e|mocks?|golden)([/\\]|$)")
# Python `test_x.py` / `x_test.py` / `conftest.py`, and the JS/TS convention
# `x.test.ts` / `x.spec.tsx`, and Go's `x_test.go`. Missing the JS/TS form put
# eight obvious Electron test fixtures into the hand queue on the first run.
_TEST_FILE_RE = re.compile(
    r"(?i)(^|[/\\])([^/\\]*\.(?:test|spec)\.[a-z0-9]+|test_[^/\\]+|[^/\\]+_test|conftest)\.?[a-z0-9]*$"
)
_DOC_PATH_RE = re.compile(r"(?i)(^|[/\\])(docs?|documentation|examples?|samples?|tutorials?|website|guides?|cookbook|recipes?)([/\\]|$)")
# `bundled` was deliberately dropped: in this repository it names bundled
# *skills documentation*, not vendored third-party code, and including it
# mislabelled two website doc pages as vendor on the first run.
_VENDOR_PATH_RE = re.compile(r"(?i)(^|[/\\])(vendor|vendored|third[_\-]?party|3rdparty|external|extern|node_modules)([/\\]|$)")
_ARCHIVE_PATH_RE = re.compile(r"(?i)(^|[/\\])(recovered-agent-sources|recovered|archive[d]?|legacy|backup|old)([/\\]|$)")
_REDACTION_PATH_RE = re.compile(r"(?i)(redact|sanitiz|sanitis|scrub|security-guidance|secret[_\-]?filter|leak)")


def shannon_entropy(value: str) -> float:
    """Shannon entropy in bits per character. 0.0 for the empty string."""
    if not value:
        return 0.0
    counts: Dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(value)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def charset_class(value: str) -> str:
    if not value:
        return "empty"
    if _HEX_RE.match(value):
        return "hex"
    if _B64URL_RE.match(value):
        return "base64url"
    if _B64_RE.match(value):
        return "base64"
    if value.isascii() and value.isprintable():
        return "printable_ascii"
    return "other"


def placeholder_signals(value: str) -> List[str]:
    """Evidence that a match is a placeholder. Returns signal *names*, not text."""
    signals: List[str] = []
    lowered = value.lower()
    if any(word in lowered for word in _PLACEHOLDER_WORDS):
        signals.append("placeholder_vocabulary")
    if any(marker in value for marker in _TEMPLATE_MARKERS) or _BRACE_PLACEHOLDER_RE.search(
        value
    ):
        signals.append("template_or_env_reference")
    if _COMMAND_SUBSTITUTION_RE.search(value):
        signals.append("command_substitution")
    if len(set(value)) <= 3:
        signals.append("almost_no_distinct_characters")
    if re.search(r"(.)\1{5,}", value):
        signals.append("long_character_run")
    if value.strip() == "":
        signals.append("blank")
    return signals


# Signals that say the match is a *reference* rather than a value at all. These
# are structural facts about the text, so they outrank path context.
_NOT_A_CREDENTIAL_SIGNALS = frozenset(
    {"template_or_env_reference", "command_substitution", "blank"}
)


# ---------------------------------------------------------------------------
# Context classification
# ---------------------------------------------------------------------------


def context_signals(relpath: str, window: str) -> List[str]:
    """Signals about *where* a hit sits. Path first, then nearby-line vocabulary."""
    signals: List[str] = []
    posix = relpath.replace("\\", "/")
    if _ARCHIVE_PATH_RE.search(posix):
        signals.append("path:archived_source")
    if _VENDOR_PATH_RE.search(posix):
        signals.append("path:vendor")
    if _TEST_PATH_RE.search(posix) or _TEST_FILE_RE.search(posix):
        signals.append("path:test")
    if _DOC_PATH_RE.search(posix):
        signals.append("path:docs")
    if Path(posix).suffix.lower() in DOC_SUFFIXES:
        signals.append("suffix:doc")
    if _REDACTION_PATH_RE.search(posix):
        signals.append("path:redaction")
    if _REDACTION_VOCAB.search(window):
        signals.append("nearby:redaction_vocabulary")
    if re.search(r"(?i)\b(example|e\.g\.|for instance|sample)\b", window):
        signals.append("nearby:example_vocabulary")
    return signals


def propose_triage(
    rule: Rule,
    ctx: List[str],
    placeholders: List[str],
    entropy: float,
) -> Tuple[str, str]:
    """Propose a bucket. A *proposal*, never a verdict — a human confirms it."""
    structural = sorted(_NOT_A_CREDENTIAL_SIGNALS.intersection(placeholders))
    if structural:
        return (
            "not_a_credential",
            "the match is a substitution reference rather than a value ("
            + ", ".join(structural)
            + ")",
        )
    if "path:archived_source" in ctx:
        return "archived_source", "path is inside a recovered/archived source tree"
    if "path:vendor" in ctx:
        return "vendor", "path is inside a vendored/third-party tree"
    if "path:redaction" in ctx or "nearby:redaction_vocabulary" in ctx:
        return (
            "redaction_code",
            "the file or surrounding lines are secret-redaction logic, which "
            "necessarily contains credential-shaped patterns as data",
        )
    if "path:test" in ctx:
        return "test_fixture", "path is a test, fixture or testdata location"
    if "suffix:doc" in ctx or "path:docs" in ctx:
        return "doc_example", "hit is in documentation or an example"
    if placeholders:
        return (
            "doc_example",
            "value carries placeholder signals (" + ", ".join(placeholders) + ")",
        )
    if rule.kind == "shape" and entropy < 3.5:
        return (
            "unreviewed",
            f"shape-only rule with low entropy ({entropy:.2f} bits/char); "
            "weak evidence, still needs a human",
        )
    return (
        "unreviewed",
        f"{rule.kind} rule with no exculpating context; needs a human decision",
    )


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    fingerprint: str
    rule: str
    rule_kind: str
    path: str
    line: int
    column: int
    value_length: int
    value_entropy_bits_per_char: float
    value_charset: str
    placeholder_signals: List[str] = field(default_factory=list)
    context_signals: List[str] = field(default_factory=list)
    proposed_triage: str = "unreviewed"
    proposed_reason: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _fingerprint(rule_name: str, relpath: str, redacted_line: str) -> str:
    normalized = " ".join(redacted_line.split())
    payload = f"{rule_name}|{relpath.replace(os.sep, '/')}|{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _redact_line(line: str, spans: Sequence[Tuple[int, int]]) -> str:
    """Replace every matched span with a fixed token. The value never survives."""
    out: List[str] = []
    cursor = 0
    for start, end in sorted(spans):
        if start < cursor:
            continue
        out.append(line[cursor:start])
        out.append(REDACTED)
        cursor = end
    out.append(line[cursor:])
    return "".join(out)


def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def scan_text(text: str, relpath: str) -> List[Finding]:
    """Scan already-decoded text. Pure function — used by the selftest too."""
    lines = text.splitlines()
    findings: List[Finding] = []

    for index, line in enumerate(lines, start=1):
        if len(line) > 8192:
            # A minified bundle or an embedded blob: matching inside it is noise.
            continue
        raw_hits: List[Tuple[Rule, Tuple[int, int], str]] = []
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                value = match.group(rule.group)
                if value is None:
                    continue
                span = match.span(rule.group)
                if len(value) < rule.min_length:
                    continue
                if shannon_entropy(value) < rule.min_entropy:
                    continue
                if any(_overlaps(span, existing[1]) for existing in raw_hits):
                    continue  # a more specific rule already claimed these bytes
                raw_hits.append((rule, span, value))

        if not raw_hits:
            continue

        redacted = _redact_line(line, [span for _, span, _ in raw_hits])
        low = max(0, index - 4)
        high = min(len(lines), index + 3)
        window = "\n".join(lines[low:high])
        ctx = context_signals(relpath, window)

        for rule, span, value in raw_hits:
            entropy = shannon_entropy(value)
            placeholders = placeholder_signals(value)
            triage, reason = propose_triage(rule, ctx, placeholders, entropy)
            findings.append(
                Finding(
                    fingerprint=_fingerprint(rule.name, relpath, redacted),
                    rule=rule.name,
                    rule_kind=rule.kind,
                    path=relpath.replace(os.sep, "/"),
                    line=index,
                    column=span[0] + 1,
                    value_length=len(value),
                    value_entropy_bits_per_char=round(entropy, 3),
                    value_charset=charset_class(value),
                    placeholder_signals=placeholders,
                    context_signals=ctx,
                    proposed_triage=triage,
                    proposed_reason=reason,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Walking a tree
# ---------------------------------------------------------------------------


@dataclass
class ScanStats:
    files_considered: int = 0
    files_scanned: int = 0
    skipped_binary_suffix: int = 0
    skipped_binary_content: int = 0
    skipped_too_large: int = 0
    skipped_unreadable: int = 0
    bytes_scanned: int = 0
    excluded_dirs: int = 0


def iter_files(root: Path, max_bytes: int, stats: ScanStats) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        kept = []
        for name in dirnames:
            if _is_excluded_dir(name):
                stats.excluded_dirs += 1
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            stats.files_considered += 1
            path = Path(dirpath) / name
            if path.suffix.lower() in BINARY_SUFFIXES:
                stats.skipped_binary_suffix += 1
                continue
            try:
                size = path.stat().st_size
            except OSError:
                stats.skipped_unreadable += 1
                continue
            if size > max_bytes:
                stats.skipped_too_large += 1
                continue
            yield path


def scan_tree(
    root: Path, *, max_bytes: int = DEFAULT_MAX_BYTES
) -> Tuple[List[Finding], ScanStats]:
    stats = ScanStats()
    findings: List[Finding] = []
    root = root.resolve()
    for path in iter_files(root, max_bytes, stats):
        try:
            raw = path.read_bytes()
        except OSError:
            stats.skipped_unreadable += 1
            continue
        if b"\x00" in raw[:8192]:
            stats.skipped_binary_content += 1
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        stats.files_scanned += 1
        stats.bytes_scanned += len(raw)
        try:
            relpath = str(path.resolve().relative_to(root))
        except ValueError:
            relpath = str(path)
        findings.extend(scan_text(text, relpath))
    return findings, stats


# ---------------------------------------------------------------------------
# Suppressions
# ---------------------------------------------------------------------------


class SuppressionError(RuntimeError):
    """The suppression file is malformed or claims something it may not claim."""


@dataclass
class Suppression:
    triage: str
    reason: str
    fingerprint: Optional[str] = None
    path_glob: Optional[str] = None
    rule: Optional[str] = None
    added_at: str = ""
    added_by: str = ""

    def matches(self, finding: Finding) -> bool:
        if self.rule and self.rule != finding.rule:
            return False
        if self.fingerprint and self.fingerprint == finding.fingerprint:
            return True
        if self.path_glob and fnmatch.fnmatch(finding.path, self.path_glob):
            return True
        return False


def load_suppressions(path: Path) -> List[Suppression]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuppressionError(f"cannot read suppression file {path}: {exc}") from exc
    if doc.get("version") != SUPPRESSION_FILE_VERSION:
        raise SuppressionError(
            f"suppression file version {doc.get('version')!r} unsupported "
            f"(expected {SUPPRESSION_FILE_VERSION}): {path}"
        )
    out: List[Suppression] = []
    for i, entry in enumerate(doc.get("suppressions", [])):
        triage = entry.get("triage")
        reason = (entry.get("reason") or "").strip()
        if triage not in TRIAGE_BUCKETS:
            raise SuppressionError(
                f"entry {i} in {path}: triage {triage!r} is not one of {TRIAGE_BUCKETS}"
            )
        if triage == "true_positive":
            raise SuppressionError(
                f"entry {i} in {path}: a true_positive may not be suppressed. "
                "Rotate the credential and remove it from the tree instead."
            )
        if not reason:
            raise SuppressionError(f"entry {i} in {path}: a reason is required")
        if not entry.get("fingerprint") and not entry.get("path_glob"):
            raise SuppressionError(
                f"entry {i} in {path}: needs a fingerprint or a path_glob"
            )
        out.append(
            Suppression(
                triage=triage,
                reason=reason,
                fingerprint=entry.get("fingerprint"),
                path_glob=entry.get("path_glob"),
                rule=entry.get("rule"),
                added_at=entry.get("added_at", ""),
                added_by=entry.get("added_by", ""),
            )
        )
    return out


def apply_suppressions(
    findings: Sequence[Finding], suppressions: Sequence[Suppression]
) -> Tuple[List[Finding], List[Tuple[Finding, Suppression]]]:
    remaining: List[Finding] = []
    suppressed: List[Tuple[Finding, Suppression]] = []
    for finding in findings:
        hit = next((s for s in suppressions if s.matches(finding)), None)
        if hit is None:
            remaining.append(finding)
        else:
            suppressed.append((finding, hit))
    return remaining, suppressed


def _utc_now() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_suppression_document(
    findings: Sequence[Finding], *, commit: str, added_by: str
) -> Dict[str, object]:
    """Turn a queue into a *proposed* suppression file for hand review."""
    entries = []
    for finding in sorted(findings, key=lambda f: (f.path, f.line, f.rule)):
        triage = finding.proposed_triage
        if triage in {"unreviewed", "true_positive"}:
            # Never auto-suppress something the scanner could not exculpate.
            continue
        entries.append(
            {
                "fingerprint": finding.fingerprint,
                "rule": finding.rule,
                "path": finding.path,
                "triage": triage,
                "reason": finding.proposed_reason,
                "added_at": _utc_now(),
                "added_by": added_by,
            }
        )
    return {
        "version": SUPPRESSION_FILE_VERSION,
        "_comment": DISCLAIMER,
        "_hand_review_required": (
            "Entries generated by --propose-suppressions are PROPOSALS. Each one "
            "must be read by a human and its 'added_by' changed to that person "
            "before the file is treated as triaged."
        ),
        "scanner": f"{SCANNER_NAME}@{SCANNER_VERSION}",
        "repo_commit": commit,
        "generated_at": _utc_now(),
        "suppressions": entries,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return "ABSENT (git not available)"
    if result.returncode != 0:
        return "ABSENT (not a git repository)"
    return result.stdout.strip()


def build_report(
    root: Path,
    findings: Sequence[Finding],
    suppressed: Sequence[Tuple[Finding, Suppression]],
    stats: ScanStats,
    commit: str,
) -> Dict[str, object]:
    by_rule: Dict[str, int] = {}
    by_triage: Dict[str, int] = {}
    by_kind: Dict[str, int] = {}
    for finding in findings:
        by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1
        by_triage[finding.proposed_triage] = by_triage.get(finding.proposed_triage, 0) + 1
        by_kind[finding.rule_kind] = by_kind.get(finding.rule_kind, 0) + 1
    suppressed_by_triage: Dict[str, int] = {}
    for _, suppression in suppressed:
        suppressed_by_triage[suppression.triage] = (
            suppressed_by_triage.get(suppression.triage, 0) + 1
        )
    return {
        "_disclaimer": DISCLAIMER,
        "scanner": f"{SCANNER_NAME}@{SCANNER_VERSION}",
        "root": str(root),
        "repo_commit": commit,
        "scanned_at": _utc_now(),
        "values_stored": False,
        "stats": asdict(stats),
        "unsuppressed_total": len(findings),
        "suppressed_total": len(suppressed),
        "unsuppressed_by_rule": dict(sorted(by_rule.items(), key=lambda kv: -kv[1])),
        "unsuppressed_by_rule_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "unsuppressed_by_proposed_triage": dict(
            sorted(by_triage.items(), key=lambda kv: -kv[1])
        ),
        "suppressed_by_triage": dict(sorted(suppressed_by_triage.items())),
        "findings": [f.to_dict() for f in findings],
    }


def print_summary(report: Dict[str, object], limit: int) -> None:
    print(report["_disclaimer"])
    print()
    print(f"scanner      : {report['scanner']}")
    print(f"root         : {report['root']}")
    print(f"repo commit  : {report['repo_commit']}")
    print(f"scanned at   : {report['scanned_at']}")
    stats = report["stats"]
    print(
        f"files        : {stats['files_scanned']} scanned of "
        f"{stats['files_considered']} considered "
        f"({stats['skipped_binary_suffix']} binary suffix, "
        f"{stats['skipped_binary_content']} binary content, "
        f"{stats['skipped_too_large']} too large, "
        f"{stats['skipped_unreadable']} unreadable)"
    )
    print(f"bytes scanned: {stats['bytes_scanned']:,}")
    print()
    print(f"unsuppressed : {report['unsuppressed_total']}")
    print(f"suppressed   : {report['suppressed_total']}  {report['suppressed_by_triage']}")
    print()
    if report["unsuppressed_by_rule"]:
        print("unsuppressed by rule:")
        for name, count in report["unsuppressed_by_rule"].items():
            print(f"  {count:>6}  {name}  [{RULES_BY_NAME[name].kind}]")
        print()
        print("unsuppressed by proposed triage (a PROPOSAL, not a verdict):")
        for name, count in report["unsuppressed_by_proposed_triage"].items():
            print(f"  {count:>6}  {name}")
        print()
    findings = report["findings"]
    if findings and limit:
        print(f"queue (first {min(limit, len(findings))} of {len(findings)}):")
        for finding in findings[:limit]:
            print(
                f"  {finding['path']}:{finding['line']}:{finding['column']}  "
                f"{finding['rule']}  len={finding['value_length']} "
                f"H={finding['value_entropy_bits_per_char']} "
                f"charset={finding['value_charset']} "
                f"-> {finding['proposed_triage']}"
            )


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

_SELFTEST_HIGH_ENTROPY = "7Zq3XvB9nKp2LdWs4TyH8mCe1RfJ6uGa"


def _selftest() -> int:
    failures: List[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    # 1. Known prefixes are detected.
    prefix_cases = {
        "aws_access_key_id": "AKIA" + "Q" * 16,
        "github_token": "ghp_" + "b" * 36,
        "slack_token": "xoxb-1234567890-" + "c" * 24,
        "google_api_key": "AIza" + "d" * 35,
        "anthropic_api_key": "sk-ant-" + "e" * 40,
        "nvidia_nim_key": "nvapi-" + "f" * 44,
    }
    for rule_name, sample in prefix_cases.items():
        found = scan_text(f'KEY = "{sample}"\n', "src/app.py")
        check(
            f"detects {rule_name}",
            any(f.rule == rule_name for f in found),
            f"(got {[f.rule for f in found]})",
        )

    # 2. Values never leave the scanner.
    secret = "AKIA" + "Z" * 16
    found = scan_text(f'AWS = "{secret}"\n', "src/app.py")
    blob = json.dumps([f.to_dict() for f in found])
    check("no matched value in output", secret not in blob)
    check("no matched value hashed recoverably", secret[8:] not in blob)

    # 3. Entropy discriminates.
    high = shannon_entropy(_SELFTEST_HIGH_ENTROPY)
    low = shannon_entropy("aaaaaaaaaaaaaaaa")
    check("entropy: random > repeated", high > 4.0 > low, f"({high:.2f} vs {low:.2f})")
    check("entropy: empty string is 0.0", shannon_entropy("") == 0.0)

    # 4. Shape rule gated by entropy and placeholder context.
    weak = scan_text('password = "aaaaaaaaaaaaaaaa"\n', "src/app.py")
    check("low-entropy shape hit is dropped", weak == [], f"(got {len(weak)})")
    placeholder = scan_text('api_key = "your-api-key-here-1234"\n', "src/app.py")
    check(
        "placeholder proposed as doc_example",
        bool(placeholder) and placeholder[0].proposed_triage == "doc_example",
        f"(got {[f.proposed_triage for f in placeholder]})",
    )

    # 4b. A substitution reference is not a credential, whatever the path.
    reference_cases = {
        'api_key = "${OPENAI_API_KEY}"\n': "template_or_env_reference",
        'auth_token = "env(SUPABASE_AUTH_SMS_TWILIO_AUTH_TOKEN)"\n': "template_or_env_reference",
        'token = "{token_path_value}"\n': "template_or_env_reference",
        'TOKEN="$(hermes cockpit token)"\n': "command_substitution",
    }
    for source, signal in reference_cases.items():
        got = scan_text(source, "src/prod.py")
        check(
            f"reference -> not_a_credential ({signal})",
            bool(got)
            and got[0].proposed_triage == "not_a_credential"
            and signal in got[0].placeholder_signals,
            f"(got {[(f.proposed_triage, f.placeholder_signals) for f in got]})",
        )

    # 5. Context classification.
    line = f'API_KEY = "{_SELFTEST_HIGH_ENTROPY}0000"\n'
    cases = {
        "tests/unit/test_client.py": "test_fixture",
        "apps/desktop/electron/backend-health.test.ts": "test_fixture",
        "apps/desktop/electron/store.spec.tsx": "test_fixture",
        "pkg/client/client_test.go": "test_fixture",
        "docs/getting-started.md": "doc_example",
        "website/docs/user-guide/skills/bundled/github/auth.md": "doc_example",
        "third_party/lib/config.py": "vendor",
        "recovered-agent-sources/old/config.py": "archived_source",
        "src/app.py": "unreviewed",
    }
    for path, expected in cases.items():
        got = scan_text(line, path)
        check(
            f"context {path} -> {expected}",
            bool(got) and got[0].proposed_triage == expected,
            f"(got {[f.proposed_triage for f in got]})",
        )
    redaction = scan_text(
        "# redact credentials before logging\n" + line, "src/logging_utils.py"
    )
    check(
        "redaction vocabulary -> redaction_code",
        bool(redaction) and redaction[0].proposed_triage == "redaction_code",
        f"(got {[f.proposed_triage for f in redaction]})",
    )

    # 6. Fingerprint stability across line drift.
    a = scan_text(line, "src/app.py")
    b = scan_text("\n\n\n" + line, "src/app.py")
    check(
        "fingerprint survives line drift",
        bool(a) and bool(b) and a[0].fingerprint == b[0].fingerprint,
    )
    c = scan_text(line, "src/other.py")
    check("fingerprint is path-specific", bool(c) and c[0].fingerprint != a[0].fingerprint)

    # 7. Overlapping rules resolve to the most specific.
    overlap = scan_text(f'api_key = "sk-ant-{"g" * 40}"\n', "src/app.py")
    check(
        "specific rule wins over generic shape",
        [f.rule for f in overlap] == ["anthropic_api_key"],
        f"(got {[f.rule for f in overlap]})",
    )

    # 8. Suppression semantics.
    doc = build_suppression_document(a, commit="deadbeef", added_by="selftest")
    check("unreviewed is not auto-suppressed", doc["suppressions"] == [])
    fixture_findings = scan_text(line, "tests/unit/test_client.py")
    doc2 = build_suppression_document(
        fixture_findings, commit="deadbeef", added_by="selftest"
    )
    check("test fixture is auto-proposed", len(doc2["suppressions"]) == 1)

    print()
    if failures:
        print(f"SELFTEST FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("SELFTEST PASSED")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.security.secret_scan",
        description=(
            "Credential scanner recording LOCATIONS ONLY (Work Packet 9.2). "
            "Output is a triage queue, never a finding of leaked credentials."
        ),
    )
    parser.add_argument("--root", default=".", help="tree to scan (default: cwd)")
    parser.add_argument("--json", dest="json_out", default=None, help="write the report")
    parser.add_argument("--suppressions", default=None, help="apply a suppression file")
    parser.add_argument(
        "--propose-suppressions",
        default=None,
        help="write a PROPOSED suppression file for hand review",
    )
    parser.add_argument("--commit", default=None, help="commit SHA to record")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--limit", type=int, default=40, help="queue rows to print")
    parser.add_argument(
        "--triage",
        default=None,
        choices=TRIAGE_BUCKETS,
        help="only show findings with this proposed triage",
    )
    parser.add_argument("--rule", default=None, help="only show findings from this rule")
    parser.add_argument(
        "--fail-on-unsuppressed",
        action="store_true",
        help="exit non-zero when the queue is not empty (for CI)",
    )
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    commit = args.commit or _git_head(root)
    findings, stats = scan_tree(root, max_bytes=args.max_bytes)

    suppressions: List[Suppression] = []
    if args.suppressions:
        try:
            suppressions = load_suppressions(Path(args.suppressions))
        except SuppressionError as exc:
            print(f"suppression file rejected: {exc}", file=sys.stderr)
            return 2
    remaining, suppressed = apply_suppressions(findings, suppressions)

    shown = remaining
    if args.triage:
        shown = [f for f in shown if f.proposed_triage == args.triage]
    if args.rule:
        shown = [f for f in shown if f.rule == args.rule]

    report = build_report(root, shown, suppressed, stats, commit)
    print_summary(report, args.limit)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nreport written to {args.json_out}")

    if args.propose_suppressions:
        doc = build_suppression_document(
            remaining, commit=commit, added_by="auto-proposed (REQUIRES HAND REVIEW)"
        )
        Path(args.propose_suppressions).write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"proposed {len(doc['suppressions'])} suppression(s) -> "
            f"{args.propose_suppressions} (hand review required)"
        )

    if args.fail_on_unsuppressed and remaining:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
