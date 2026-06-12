"""Voice intake pipeline — transcripts to approved jobs, safely.

Hermes already owns the *audio* side of voice
(``muse_cli.voice``) — recording, transcription, TTS. This module
owns the *intake* side: what happens once a transcript exists and the
agent needs to decide whether to act on it.

The pipeline runs in five explicit steps. Each step has its own
function so the gateway, CLI, Termux runtime, and the Android cockpit
can call them independently and the safety properties are easy to
audit:

1. ``begin_intake(config)`` — open a per-interaction folder under
   ``~/.hermes/voice/<voice-id>/`` and capture mode + config.
2. ``ingest_transcript(intake, transcript)`` — write
   ``voice/transcript.txt`` (redacted), classify intent, build the
   draft job.
3. ``build_readback(intake)`` — produce
   ``voice/plain-english-confirmation.md`` and return the read-back
   string for TTS / on-screen display.
4. ``record_decision(intake, phrase)`` — interpret the user's
   spoken / typed confirmation and persist
   ``voice/approval-state.json``.
5. ``finalize(intake)`` — for ``approved`` intakes, hand the prompt
   to ``muse_cli.orchestrator.submit_job`` and return the new job
   ID; for ``cancelled`` / ``expired`` intakes, return ``None``.

The pipeline never touches a microphone or a TTS provider directly —
``muse_cli.voice`` already does that, and keeping intake decoupled
from the audio stack means it stays testable without sounddevice,
faster-whisper, or any platform-specific audio code installed.

Safety properties (also see ``docs/voice/driving-mode-safety.md``):

* Raw audio is never written to the intake folder. The pipeline only
  ever receives a ``VoiceTranscript`` value; whoever called it is
  responsible for *not* persisting the WAV.
* Driving-mode intakes always require a spoken-confirmation phrase
  before an implementation/publish action is allowed to proceed.
* Unknown intents in driving mode degrade to "capture note" — the
  agent never guesses what to do while the user is on the road.
* The intake folder is created with mode ``0o700`` to match the
  rest of ``~/.hermes/``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

from muse_cli.voice_models import (
    APPROVAL_APPROVED,
    APPROVAL_AWAITING_CONFIRMATION,
    APPROVAL_CANCELLED,
    APPROVAL_EXPIRED,
    APPROVAL_PENDING_READBACK,
    INTENT_CANCEL,
    INTENT_CAPTURE_NOTE,
    INTENT_CONFIRM,
    INTENT_CREATE_JOB,
    INTENT_QUERY_STATUS,
    INTENT_REPEAT,
    INTENT_UNKNOWN,
    MODE_DISABLED,
    MODE_DRIVING_CAPTURE,
    MODE_PUSH_TO_TALK,
    MODE_WAKE_WORD,
    DrivingSafetyVeto,
    VoiceApproval,
    VoiceConfirmationRequired,
    VoiceDisabledError,
    VoiceDraftJob,
    VoiceIntake,
    VoiceIntakeConfig,
    VoiceTranscript,
    classify_intent,
    normalize_mode,
    redact_transcript,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

_VOICE_DIR_NAME = "voice"

# Stored under each intake folder. Keep the names stable — both the
# gateway diagnostics and the cockpit's "review last voice intake"
# screen read them by path.
TRANSCRIPT_FILE = "transcript.txt"
CONFIRMATION_FILE = "plain-english-confirmation.md"
APPROVAL_FILE = "approval-state.json"
INTAKE_FILE = "intake.json"


def _hermes_home() -> Path:
    """Return the active Hermes home directory.

    Same lookup ``muse_cli.orchestrator`` uses, so voice artefacts
    and orchestrator artefacts live in sibling folders under
    ``~/.hermes/``.
    """
    try:
        from muse_constants import get_hermes_home

        return get_hermes_home()
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _voice_root() -> Path:
    root = _hermes_home() / _VOICE_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        # ``chmod`` is best-effort: on Windows or shared file systems
        # the call may fail. The directory is still created.
        pass
    return root


def intake_folder(voice_id: str) -> Path:
    """Folder for a single voice intake — exposed so callers can
    bundle it into a tarball alongside an orchestrator job."""
    folder = _voice_root() / voice_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        folder.chmod(0o700)
    except OSError:
        pass
    return folder


# ---------------------------------------------------------------------------
# Confirmation grammar
# ---------------------------------------------------------------------------

# Words that count as an explicit "go" answer to the read-back. Kept
# small on purpose: a long list invites false positives ("ok, but
# wait, ..." is *not* approval) and the driving safety layer is the
# wrong place to be lenient.
_AFFIRM_PHRASES: tuple[str, ...] = (
    "yes",
    "yes please",
    "yep",
    "yeah",
    "confirm",
    "confirmed",
    "approve",
    "approved",
    "go ahead",
    "do it",
    "proceed",
    "ship it",
    "publish it",
)

_DENY_PHRASES: tuple[str, ...] = (
    "no",
    "nope",
    "cancel",
    "abort",
    "stop",
    "never mind",
    "nevermind",
    "forget it",
    "don't",
    "do not",
    "scratch that",
)


def _matches_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    if not isinstance(text, str):
        return False
    lowered = text.strip().lower().rstrip(".!?")
    if not lowered:
        return False
    if lowered in phrases:
        return True
    # Prefix match catches "yes, do it" / "no, cancel that".
    for phrase in phrases:
        if (
            lowered == phrase
            or lowered.startswith(phrase + " ")
            or lowered.startswith(phrase + ",")
        ):
            return True
    return False


def is_affirmative(text: str) -> bool:
    """Whether *text* should be treated as approval."""
    return _matches_phrase(text, _AFFIRM_PHRASES)


def is_negative(text: str) -> bool:
    """Whether *text* should be treated as cancellation."""
    return _matches_phrase(text, _DENY_PHRASES)


# ---------------------------------------------------------------------------
# Pipeline — step 1: begin
# ---------------------------------------------------------------------------


def begin_intake(config: Optional[VoiceIntakeConfig] = None) -> VoiceIntake:
    """Open a new voice intake.

    Raises ``VoiceDisabledError`` if voice intake is turned off.
    Returns a fresh ``VoiceIntake`` whose folder is already on disk
    but whose transcript/draft are empty.
    """
    cfg = config or VoiceIntakeConfig()
    if cfg.mode == MODE_DISABLED:
        raise VoiceDisabledError("voice intake is disabled")
    intake = VoiceIntake(mode=cfg.mode, config=cfg)
    folder = intake_folder(intake.id)
    # Touch the on-disk record up front so concurrent diagnostics
    # (``hermes voice last``) see *something* even if the user never
    # finishes the interaction.
    _write_intake_json(folder, intake)
    return intake


# ---------------------------------------------------------------------------
# Pipeline — step 2: ingest
# ---------------------------------------------------------------------------


def ingest_transcript(intake: VoiceIntake, transcript: VoiceTranscript) -> VoiceIntake:
    """Attach *transcript* to *intake* and build the draft job.

    Redaction runs before anything hits disk so the on-disk
    ``transcript.txt`` never contains a captured secret.
    Classification + draft construction follow the rules documented
    in ``docs/voice/voice-first-architecture.md``.
    """
    if not isinstance(transcript, VoiceTranscript):
        raise TypeError("transcript must be a VoiceTranscript")

    cfg = intake.config
    text = transcript.text or ""
    if cfg.redact_secrets:
        text = redact_transcript(text)
        transcript.redacted = transcript.redacted or text != (transcript.text or "")
    transcript.text = text

    # Driving mode trims the transcript so the read-back fits in one
    # spoken sentence; the unredacted/untrimmed version never
    # existed in this dataclass to begin with.
    if intake.mode == MODE_DRIVING_CAPTURE:
        cap = max(40, int(cfg.driving_max_transcript_chars))
        if len(text) > cap:
            text = text[:cap].rstrip() + "..."
            transcript.text = text

    intake.transcript = transcript
    intake.draft = _build_draft(intake, text)
    folder = intake_folder(intake.id)
    _write_transcript_file(folder, intake)
    _write_intake_json(folder, intake)
    return intake


def _build_draft(intake: VoiceIntake, text: str) -> VoiceDraftJob:
    intent = classify_intent(text)

    # Driving-mode degradation: an unknown / ambiguous transcript is
    # captured as a note instead of being inflated into "implement
    # this for me". This is the rule the safety doc relies on.
    if intake.mode == MODE_DRIVING_CAPTURE and intent in {
        INTENT_UNKNOWN,
        INTENT_CREATE_JOB,
    }:
        if intent == INTENT_UNKNOWN:
            intent = INTENT_CAPTURE_NOTE

    requires_impl = intent == INTENT_CREATE_JOB
    publishes = bool(text) and any(
        word in text.lower()
        for word in (
            "publish",
            "ship it",
            "deploy",
            "merge",
            "release",
            "send the pr",
            "open the pr",
        )
    )

    summary = _summarize_for_readback(intent, text)
    return VoiceDraftJob(
        intent=intent,
        summary=summary,
        prompt=text.strip(),
        requires_implementation=requires_impl,
        publish_action=publishes,
    )


def _summarize_for_readback(intent: str, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "I did not hear anything to act on."
    snippet = text if len(text) <= 240 else text[:237].rstrip() + "..."
    if intent == INTENT_CAPTURE_NOTE:
        return f"Capture a note: {snippet}"
    if intent == INTENT_CREATE_JOB:
        return f"Create a job to: {snippet}"
    if intent == INTENT_QUERY_STATUS:
        return f"Read back status for: {snippet}"
    if intent == INTENT_CANCEL:
        return "Cancel the pending voice action."
    if intent == INTENT_CONFIRM:
        return "Confirm the pending voice action."
    if intent == INTENT_REPEAT:
        return "Repeat the last read-back."
    return f"I heard: {snippet}. I am not sure what to do — captured as a note."


# ---------------------------------------------------------------------------
# Pipeline — step 3: read-back
# ---------------------------------------------------------------------------


def build_readback(intake: VoiceIntake) -> str:
    """Return the plain-English read-back string and persist it.

    The string is what the TTS layer will speak. We also store the
    full Markdown summary in ``plain-english-confirmation.md`` so
    on-screen review (cockpit, CLI) shows exactly what the user was
    asked to confirm.
    """
    if intake.config.mode == MODE_DISABLED:
        raise VoiceDisabledError("voice intake is disabled")

    draft = intake.draft
    transcript = intake.transcript

    spoken = _compose_spoken_readback(intake)
    md = _compose_markdown_readback(intake)

    folder = intake_folder(intake.id)
    (folder / CONFIRMATION_FILE).write_text(md, encoding="utf-8")

    # Move the approval state forward so callers that look at the
    # intake mid-flight see the correct stage.
    if intake.approval.state == APPROVAL_PENDING_READBACK:
        intake.approval = VoiceApproval(state=APPROVAL_AWAITING_CONFIRMATION)
        _write_intake_json(folder, intake)

    # Touch a metadata-only access so transcript provider attribution
    # is testable end-to-end.
    logger.debug(
        "voice readback built (provider=%s, intent=%s)",
        transcript.provider,
        draft.intent,
    )
    return spoken


def _compose_spoken_readback(intake: VoiceIntake) -> str:
    draft = intake.draft
    mode = intake.mode
    parts: list[str] = []
    if mode == MODE_DRIVING_CAPTURE:
        parts.append("Driving-safe summary.")
    parts.append(draft.summary)
    if draft.requires_implementation:
        parts.append("This would create a new job.")
    if draft.publish_action:
        parts.append("This would publish or merge code.")
    if intake.config.require_voice_confirmation and draft.intent in {
        INTENT_CREATE_JOB,
        INTENT_CAPTURE_NOTE,
    }:
        parts.append("Say yes to proceed or no to cancel.")
    return " ".join(parts).strip()


def _compose_markdown_readback(intake: VoiceIntake) -> str:
    draft = intake.draft
    transcript = intake.transcript
    cfg = intake.config
    lines: list[str] = [
        "# Voice intake — plain-English confirmation",
        "",
        f"- **Intake ID:** `{intake.id}`",
        f"- **Mode:** `{intake.mode}`",
        f"- **STT provider:** `{transcript.provider}`",
        f"- **Intent:** `{draft.intent}`",
        f"- **Requires implementation:** {'yes' if draft.requires_implementation else 'no'}",
        f"- **Publish/merge action:** {'yes' if draft.publish_action else 'no'}",
        "",
        "## Heard transcript",
        "",
        "```",
        (transcript.text or "(empty)"),
        "```",
        "",
        "## Read-back",
        "",
        draft.summary,
        "",
    ]
    if cfg.require_voice_confirmation:
        lines.extend([
            "## Confirmation contract",
            "",
            "- Say **yes** / **confirm** / **go ahead** to approve.",
            "- Say **no** / **cancel** / **never mind** to reject.",
            f"- Timeout: {cfg.confirmation_timeout_s:.0f} seconds; expired intakes are treated as cancelled.",
            "",
        ])
    if intake.mode == MODE_DRIVING_CAPTURE:
        lines.extend([
            "## Driving-mode safety",
            "",
            "Driving-mode intakes never auto-execute. Implementation",
            "and publish actions require a spoken confirmation that is",
            "recorded in `voice/approval-state.json`. Raw audio is",
            "discarded and is never written to disk.",
            "",
        ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline — step 4: decision
# ---------------------------------------------------------------------------


def record_decision(intake: VoiceIntake, phrase: Optional[str]) -> VoiceIntake:
    """Interpret *phrase* and write the terminal approval state.

    *phrase* may be ``None`` (the confirmation window closed) or any
    short user utterance / typed reply. The function is forgiving
    about wording but conservative about meaning: anything that is
    not an explicit affirmative is treated as a cancellation in
    driving mode, and as "still waiting" elsewhere only if the
    caller passes ``None``.
    """
    folder = intake_folder(intake.id)
    state: str
    notes: list[str] = []
    text = (phrase or "").strip()

    if phrase is None:
        state = APPROVAL_EXPIRED
        notes.append("confirmation window expired")
    elif is_affirmative(text):
        state = APPROVAL_APPROVED
    elif is_negative(text):
        state = APPROVAL_CANCELLED
    elif intake.mode == MODE_DRIVING_CAPTURE:
        # Driving mode never assumes consent — if the user said
        # something other than yes, we cancel and let them try again.
        state = APPROVAL_CANCELLED
        notes.append("ambiguous response in driving mode treated as cancel")
    else:
        # In non-driving modes, an ambiguous reply leaves us
        # awaiting confirmation. The caller can call back later
        # with the next utterance.
        intake.approval = VoiceApproval(
            state=APPROVAL_AWAITING_CONFIRMATION,
            confirmation_phrase=text or None,
        )
        _write_intake_json(folder, intake)
        return intake

    intake.approval = VoiceApproval(
        state=state,
        decided_at=_now_us(),
        confirmation_phrase=text or None,
        notes=notes,
    )
    _write_approval_file(folder, intake.approval)
    _write_intake_json(folder, intake)
    return intake


def _now_us() -> int:
    import time as _time

    return _time.time_ns() // 1_000


# ---------------------------------------------------------------------------
# Pipeline — step 5: finalize
# ---------------------------------------------------------------------------

#: Type of the callable used to actually submit an orchestrator job.
JobSubmitter = Callable[[str], Any]


def finalize(
    intake: VoiceIntake,
    submitter: Optional[JobSubmitter] = None,
) -> Optional[str]:
    """Hand an approved intake to the orchestrator.

    Returns the new orchestrator job ID on success, ``None`` if the
    intake was cancelled / expired / never approved.

    *submitter* is the function that will create the orchestrator
    job. The default uses ``muse_cli.orchestrator.submit_job`` —
    callers in tests can pass a fake to avoid touching the on-disk
    jobs file. The injection seam also lets the cockpit hand the
    intake to the local API instead of the in-process orchestrator.

    Raises ``VoiceConfirmationRequired`` if the draft asked for a
    publish/implementation action but ``config.require_voice_confirmation``
    is on and the approval is not ``approved``.
    """
    cfg = intake.config
    draft = intake.draft
    approval = intake.approval

    if approval.state != APPROVAL_APPROVED:
        return None

    if (
        draft.requires_implementation or draft.publish_action
    ) and cfg.require_voice_confirmation:
        # We already know the state is ``approved`` — but if the user
        # somehow approved an empty/unknown intent (e.g. a wake-word
        # false positive), refuse rather than creating a junk job.
        if draft.intent == INTENT_UNKNOWN:
            raise VoiceConfirmationRequired(
                "voice intake approved but intent is unknown — refusing to create a job"
            )

    if intake.mode == MODE_DRIVING_CAPTURE and draft.publish_action:
        # Final defence-in-depth: even an "approved" driving-mode
        # publish requires an out-of-band, non-driving confirmation
        # step before the publisher runs. This module emits the
        # veto; the orchestrator is responsible for queuing the
        # follow-up.
        raise DrivingSafetyVeto(
            "driving-mode publish requires a non-driving confirmation step"
        )

    if draft.intent == INTENT_CAPTURE_NOTE and not draft.requires_implementation:
        # Notes still get persisted, but they are not orchestrator
        # jobs — the read-back already shows the captured note on
        # screen / in the confirmation file.
        return None

    submit = submitter or _default_submitter
    try:
        job = submit(draft.prompt or draft.summary)
    except Exception as e:  # pragma: no cover — submitter is provided
        logger.warning("voice intake submitter raised: %s", e)
        raise

    job_id = getattr(job, "id", None) or (job if isinstance(job, str) else None)
    if job_id:
        folder = intake_folder(intake.id)
        intake.approval.notes.append(f"orchestrator-job:{job_id}")
        _write_approval_file(folder, intake.approval)
        _write_intake_json(folder, intake)
    return job_id


def _default_submitter(prompt: str) -> Any:
    from muse_cli.orchestrator import submit_job

    return submit_job(prompt)


# ---------------------------------------------------------------------------
# Convenience: full pipeline wrapper
# ---------------------------------------------------------------------------


def run_pipeline(
    transcript: VoiceTranscript,
    *,
    config: Optional[VoiceIntakeConfig] = None,
    confirmation: Optional[str] = None,
    submitter: Optional[JobSubmitter] = None,
) -> tuple[VoiceIntake, Optional[str]]:
    """Run the whole pipeline against an already-captured transcript.

    Useful for tests, the cockpit's "paste a transcript" debug page,
    and any synchronous caller that has the user's confirmation phrase
    on hand. Real interactive callers should drive the five steps
    individually so they can render the read-back and wait for the
    user.
    """
    intake = begin_intake(config)
    intake = ingest_transcript(intake, transcript)
    build_readback(intake)
    intake = record_decision(intake, confirmation)
    job_id = finalize(intake, submitter=submitter)
    return intake, job_id


# ---------------------------------------------------------------------------
# Persistence helpers (kept private — callers should not write the
# JSON files directly).
# ---------------------------------------------------------------------------


def _write_intake_json(folder: Path, intake: VoiceIntake) -> None:
    path = folder / INTAKE_FILE
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(intake.to_json(), encoding="utf-8")
    os.replace(tmp, path)


def _write_transcript_file(folder: Path, intake: VoiceIntake) -> None:
    path = folder / TRANSCRIPT_FILE
    body = intake.transcript.text or ""
    path.write_text(body, encoding="utf-8")


def _write_approval_file(folder: Path, approval: VoiceApproval) -> None:
    path = folder / APPROVAL_FILE
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(asdict(approval), indent=2, sort_keys=True), encoding="utf-8"
    )
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Inspection helpers (used by ``hermes voice last`` and the cockpit
# diagnostics page)
# ---------------------------------------------------------------------------


def load_intake(voice_id: str) -> Optional[VoiceIntake]:
    folder = _voice_root() / voice_id
    intake_path = folder / INTAKE_FILE
    if not intake_path.is_file():
        return None
    try:
        data = json.loads(intake_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return VoiceIntake.from_dict(data)


def list_intakes(limit: int = 25) -> list[VoiceIntake]:
    root = _voice_root()
    intakes: list[VoiceIntake] = []
    for child in sorted(root.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        intake = load_intake(child.name)
        if intake is not None:
            intakes.append(intake)
        if len(intakes) >= max(1, int(limit)):
            break
    return intakes


__all__ = [
    "TRANSCRIPT_FILE",
    "CONFIRMATION_FILE",
    "APPROVAL_FILE",
    "INTAKE_FILE",
    "intake_folder",
    "is_affirmative",
    "is_negative",
    "begin_intake",
    "ingest_transcript",
    "build_readback",
    "record_decision",
    "finalize",
    "run_pipeline",
    "load_intake",
    "list_intakes",
    "JobSubmitter",
]
