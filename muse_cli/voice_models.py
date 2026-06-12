"""Voice-intake data models for Hermes.

These dataclasses describe the on-disk and in-memory shape of a
voice-first job intake (transcript -> intent classification -> draft
job -> hands-free read-back -> explicit approval). Everything here is
stdlib-only and JSON-serialisable so the gateway, CLI, Termux runtime,
and the Android cockpit can all share one source of truth without
pulling in voice/audio dependencies.

The pipeline that consumes these models lives in
``muse_cli.voice_intake``. The architecture, safety, and provider
policy are documented under ``docs/voice/``. None of this module
captures audio or talks to an STT provider; it just describes the
contract.

Mode contract
-------------

Four voice modes are recognised end-to-end (CLI, gateway, cockpit):

* ``push_to_talk`` — default. The user is the trigger: a key, button,
  or wake gesture starts capture; release stops it. Safe everywhere.
* ``wake_word`` — opt-in. A local wake-word detector arms capture; no
  remote audio leaves the device until a wake event fires. Requires
  ``HERMES_VOICE_WAKE_WORD`` and an on-device wake engine.
* ``driving_capture`` — opt-in. Hands-free capture intended for use
  while the device is mounted in a vehicle. Pipeline behaviour
  changes: transcripts never auto-execute, the read-back step is
  mandatory, and explicit voice confirmation is required before any
  publish/implementation action.
* ``disabled`` — voice intake is off. Any call that would create a
  voice job raises ``VoiceDisabledError``.

Approval state
--------------

Every voice intake produces an ``ApprovalState`` value:

* ``pending_readback`` — transcript captured, draft built, but the
  user has not yet heard or read the summary.
* ``awaiting_confirmation`` — read-back delivered; the pipeline is
  waiting for an explicit ``yes`` / ``no`` from the user.
* ``approved`` — user said yes; the job has been created.
* ``cancelled`` — user said no, the timeout elapsed, or the safety
  layer vetoed the action.
* ``expired`` — the confirmation window closed without input.

The terminal states (``approved`` / ``cancelled`` / ``expired``) are
the only ones that get persisted to ``voice/approval-state.json``.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Constants — kept as plain strings (not Enum) so the on-disk JSON files are
# trivially diffable and forward-compatible with hand edits or older readers.
# ---------------------------------------------------------------------------

MODE_PUSH_TO_TALK = "push_to_talk"
MODE_WAKE_WORD = "wake_word"
MODE_DRIVING_CAPTURE = "driving_capture"
MODE_DISABLED = "disabled"

VOICE_MODES: tuple[str, ...] = (
    MODE_PUSH_TO_TALK,
    MODE_WAKE_WORD,
    MODE_DRIVING_CAPTURE,
    MODE_DISABLED,
)


APPROVAL_PENDING_READBACK = "pending_readback"
APPROVAL_AWAITING_CONFIRMATION = "awaiting_confirmation"
APPROVAL_APPROVED = "approved"
APPROVAL_CANCELLED = "cancelled"
APPROVAL_EXPIRED = "expired"

APPROVAL_STATES: tuple[str, ...] = (
    APPROVAL_PENDING_READBACK,
    APPROVAL_AWAITING_CONFIRMATION,
    APPROVAL_APPROVED,
    APPROVAL_CANCELLED,
    APPROVAL_EXPIRED,
)


INTENT_CAPTURE_NOTE = "capture_note"
INTENT_CREATE_JOB = "create_job"
INTENT_QUERY_STATUS = "query_status"
INTENT_CANCEL = "cancel"
INTENT_CONFIRM = "confirm"
INTENT_REPEAT = "repeat"
INTENT_UNKNOWN = "unknown"

VOICE_INTENTS: tuple[str, ...] = (
    INTENT_CAPTURE_NOTE,
    INTENT_CREATE_JOB,
    INTENT_QUERY_STATUS,
    INTENT_CANCEL,
    INTENT_CONFIRM,
    INTENT_REPEAT,
    INTENT_UNKNOWN,
)


# Intent classification weights used by ``classify_intent``. Each
# entry is ``(intent, regex)``. The list is ordered by specificity so
# the explicit ``cancel`` / ``confirm`` phrases win over the broader
# ``create_job`` heuristics. ``re.IGNORECASE`` is applied at compile
# time so the patterns can stay readable.
_INTENT_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    (
        INTENT_CANCEL,
        re.compile(r"\b(cancel|abort|never\s*mind|forget\s*it|stop)\b", re.IGNORECASE),
    ),
    (
        INTENT_CONFIRM,
        re.compile(
            r"\b(yes|yeah|yep|confirm|go\s*ahead|do\s*it|approve|approved)\b",
            re.IGNORECASE,
        ),
    ),
    (
        INTENT_REPEAT,
        re.compile(
            r"\b(repeat|say\s*again|read\s*back|one\s*more\s*time)\b", re.IGNORECASE
        ),
    ),
    (
        INTENT_QUERY_STATUS,
        re.compile(
            r"\b(status|what(?:'|\s+i)s\s+(?:happening|the\s+status)|how\s+is|update\s+me)\b",
            re.IGNORECASE,
        ),
    ),
    (
        INTENT_CREATE_JOB,
        re.compile(
            r"\b(create|implement|build|publish|deploy|ship|fix|refactor|add|run|kick\s*off)\b",
            re.IGNORECASE,
        ),
    ),
    (
        INTENT_CAPTURE_NOTE,
        re.compile(
            r"\b(note|remember|jot|capture|log|save|todo|to\s*do|reminder|remind\s*me)\b",
            re.IGNORECASE,
        ),
    ),
)


# Spoken-secret heuristics. The driving-mode and STT-policy docs both
# require redaction before the transcript hits disk. Patterns are
# conservative on purpose — false positives (a chunk of text replaced
# with ``[REDACTED]``) are much cheaper than leaking a key to a
# transcript file.
_SECRET_PATTERNS: tuple["re.Pattern[str]", ...] = (
    # OpenAI / Anthropic / xAI / generic ``sk-...`` style tokens.
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    # GitHub PAT prefixes.
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    # AWS-style access key IDs and secret keys.
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"\b[A-Za-z0-9/+=]{40}\b"),
    # Bearer tokens and password-style assignments.
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{16,}\b"),
    re.compile(
        r"(?i)\b(password|passcode|pin|secret|api[\s_-]?key|token)\s+(?:is\s+)?[A-Za-z0-9._\-]{4,}\b"
    ),
)


_REDACTION_MARKER = "[REDACTED]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_voice_id() -> str:
    """Stable ID for a single voice intake interaction."""
    return f"voi-{uuid.uuid4().hex[:8]}"


def _now() -> int:
    """Unix epoch in microseconds, monotonic-safe.

    Mirrors ``muse_cli.orchestrator._now`` so voice-intake timelines
    interleave cleanly with the orchestrator ledger.
    """
    return time.time_ns() // 1_000


def normalize_mode(value: Any) -> str:
    """Return one of ``VOICE_MODES`` for any plausible input.

    Unknown / typo'd / ``None`` / non-string values collapse to
    ``push_to_talk`` so a malformed config can never silently leave a
    user in driving mode — the safest default is "user has to push
    something".
    """
    if not isinstance(value, str):
        return MODE_PUSH_TO_TALK
    lowered = value.strip().lower().replace("-", "_").replace(" ", "_")
    if lowered in VOICE_MODES:
        return lowered
    # Friendly aliases.
    aliases = {
        "ptt": MODE_PUSH_TO_TALK,
        "press_to_talk": MODE_PUSH_TO_TALK,
        "wake": MODE_WAKE_WORD,
        "wakeword": MODE_WAKE_WORD,
        "hotword": MODE_WAKE_WORD,
        "driving": MODE_DRIVING_CAPTURE,
        "drive": MODE_DRIVING_CAPTURE,
        "car": MODE_DRIVING_CAPTURE,
        "off": MODE_DISABLED,
        "none": MODE_DISABLED,
    }
    return aliases.get(lowered, MODE_PUSH_TO_TALK)


def normalize_approval(value: Any) -> str:
    if isinstance(value, str) and value in APPROVAL_STATES:
        return value
    return APPROVAL_PENDING_READBACK


def redact_transcript(text: str) -> str:
    """Replace likely spoken secrets with ``[REDACTED]``.

    Driving-mode capture and the STT provider policy both require this
    before any transcript leaves the in-memory buffer.
    """
    if not isinstance(text, str) or not text:
        return ""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(_REDACTION_MARKER, redacted)
    return redacted


def classify_intent(text: str) -> str:
    """Return one of ``VOICE_INTENTS`` for *text*.

    The classifier is deliberately a small set of regex heuristics —
    no model call, no network. It is fast enough to run on the
    transcript callback thread and easy enough to audit that the
    driving-mode safety layer can rely on it.
    """
    if not isinstance(text, str) or not text.strip():
        return INTENT_UNKNOWN
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return INTENT_UNKNOWN


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VoiceIntakeConfig:
    """Configuration snapshot for the voice-intake pipeline.

    The config object is built once per session (CLI start, gateway
    connect, cockpit app launch) and threaded through the pipeline so
    every safety decision references the same values. The defaults
    are intentionally conservative: push-to-talk, local STT preferred,
    no raw audio kept, two-step confirmation required for any
    publish.
    """

    mode: str = MODE_PUSH_TO_TALK
    stt_provider: str = "local"
    allow_remote_stt: bool = False
    store_raw_audio: bool = False
    require_voice_confirmation: bool = True
    readback_enabled: bool = True
    confirmation_timeout_s: float = 20.0
    wake_word: Optional[str] = None
    driving_max_transcript_chars: int = 600
    redact_secrets: bool = True

    def __post_init__(self) -> None:
        self.mode = normalize_mode(self.mode)
        # Driving mode tightens a few defaults regardless of caller
        # input. This is the single chokepoint where "the user picked
        # driving" gets translated into "raw audio off, confirmation
        # required, read-back required". Doing it here means later
        # callers cannot accidentally override one of the safety bits.
        if self.mode == MODE_DRIVING_CAPTURE:
            self.store_raw_audio = False
            self.require_voice_confirmation = True
            self.readback_enabled = True
            self.redact_secrets = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoiceIntakeConfig":
        if not isinstance(data, dict):
            return cls()
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class VoiceTranscript:
    """A single STT result, plus its provenance.

    ``provider`` is the STT engine that produced the text (e.g.
    ``"local-whisper"`` or ``"groq-whisper-v3"``). ``confidence`` is
    optional — many providers do not return a single scalar — and
    callers must treat ``None`` as "unknown", not "high".
    """

    text: str
    provider: str = "unknown"
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration_s: Optional[float] = None
    captured_at: int = field(default_factory=_now)
    redacted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoiceTranscript":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


@dataclass
class VoiceDraftJob:
    """A draft action derived from a transcript.

    The draft is what the user will hear in the read-back. It is
    *not* a committed job — the pipeline only hands it to the
    orchestrator after explicit approval.
    """

    id: str = field(default_factory=_new_voice_id)
    intent: str = INTENT_UNKNOWN
    summary: str = ""
    prompt: str = ""
    requires_implementation: bool = False
    publish_action: bool = False
    created_at: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoiceDraftJob":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


@dataclass
class VoiceApproval:
    """Terminal record of how a draft was resolved."""

    state: str = APPROVAL_PENDING_READBACK
    decided_at: Optional[int] = None
    decided_by: str = "user"
    confirmation_phrase: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.state = normalize_approval(self.state)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoiceApproval":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in (data or {}).items() if k in known})

    @property
    def is_terminal(self) -> bool:
        return self.state in {APPROVAL_APPROVED, APPROVAL_CANCELLED, APPROVAL_EXPIRED}


@dataclass
class VoiceIntake:
    """End-to-end record of one voice interaction.

    A ``VoiceIntake`` instance is the in-memory shape; the on-disk
    artefacts (``voice/transcript.txt``,
    ``voice/plain-english-confirmation.md``,
    ``voice/approval-state.json``) are written by the pipeline based
    on this object.
    """

    id: str = field(default_factory=_new_voice_id)
    mode: str = MODE_PUSH_TO_TALK
    transcript: VoiceTranscript = field(
        default_factory=lambda: VoiceTranscript(text="")
    )
    draft: VoiceDraftJob = field(default_factory=VoiceDraftJob)
    approval: VoiceApproval = field(default_factory=VoiceApproval)
    config: VoiceIntakeConfig = field(default_factory=VoiceIntakeConfig)

    def __post_init__(self) -> None:
        self.mode = normalize_mode(self.mode)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "transcript": self.transcript.to_dict(),
            "draft": self.draft.to_dict(),
            "approval": self.approval.to_dict(),
            "config": self.config.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoiceIntake":
        if not isinstance(data, dict):
            return cls()
        return cls(
            id=data.get("id") or _new_voice_id(),
            mode=normalize_mode(data.get("mode")),
            transcript=VoiceTranscript.from_dict(data.get("transcript", {})),
            draft=VoiceDraftJob.from_dict(data.get("draft", {})),
            approval=VoiceApproval.from_dict(data.get("approval", {})),
            config=VoiceIntakeConfig.from_dict(data.get("config", {})),
        )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VoiceIntakeError(RuntimeError):
    """Base class for voice-intake errors."""


class VoiceDisabledError(VoiceIntakeError):
    """Raised when voice intake is called while ``mode == disabled``."""


class VoiceConfirmationRequired(VoiceIntakeError):
    """Raised when a publish/implementation action is attempted without confirmation."""


class DrivingSafetyVeto(VoiceIntakeError):
    """Raised when the driving-mode safety layer blocks an action.

    The action was syntactically valid (intent classified, draft
    built) but the driving safety policy refused it — typically
    because it would have required hands-on phone interaction or
    implicit (no-readback) approval.
    """


__all__ = [
    # Mode constants
    "MODE_PUSH_TO_TALK",
    "MODE_WAKE_WORD",
    "MODE_DRIVING_CAPTURE",
    "MODE_DISABLED",
    "VOICE_MODES",
    # Approval constants
    "APPROVAL_PENDING_READBACK",
    "APPROVAL_AWAITING_CONFIRMATION",
    "APPROVAL_APPROVED",
    "APPROVAL_CANCELLED",
    "APPROVAL_EXPIRED",
    "APPROVAL_STATES",
    # Intent constants
    "INTENT_CAPTURE_NOTE",
    "INTENT_CREATE_JOB",
    "INTENT_QUERY_STATUS",
    "INTENT_CANCEL",
    "INTENT_CONFIRM",
    "INTENT_REPEAT",
    "INTENT_UNKNOWN",
    "VOICE_INTENTS",
    # Helpers
    "normalize_mode",
    "normalize_approval",
    "redact_transcript",
    "classify_intent",
    # Dataclasses
    "VoiceIntakeConfig",
    "VoiceTranscript",
    "VoiceDraftJob",
    "VoiceApproval",
    "VoiceIntake",
    # Errors
    "VoiceIntakeError",
    "VoiceDisabledError",
    "VoiceConfirmationRequired",
    "DrivingSafetyVeto",
]
