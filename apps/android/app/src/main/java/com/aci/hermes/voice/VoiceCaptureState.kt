package com.aci.hermes.voice

/**
 * State machine for the JARVIS Prime voice capture surface.
 *
 * The screen always starts in [Idle]. Transitions are linear and only
 * advance after an explicit user action — there is no auto-recording,
 * no wake-word listening, and the microphone is not opened until
 * [Listening] is reached, which itself requires the user to have
 * acknowledged the education step and granted RECORD_AUDIO.
 */
sealed class VoiceCaptureStep {
    /** Sheet is closed. Nothing is being captured. */
    data object Idle : VoiceCaptureStep()

    /** User tapped the voice button. The education panel is showing. */
    data object Education : VoiceCaptureStep()

    /** Education acknowledged. The screen is asking the OS for RECORD_AUDIO. */
    data object RequestingPermission : VoiceCaptureStep()

    /** OS returned denied. Show rationale + retry / fall back to manual entry. */
    data object PermissionDenied : VoiceCaptureStep()

    /** Microphone is open. The recognizer is listening. */
    data object Listening : VoiceCaptureStep()

    /** Recognizer finished (or user pressed stop). The transcript is editable. */
    data object Captured : VoiceCaptureStep()

    /**
     * Native STT not available. The user can type a transcript manually
     * to exercise the rest of the pipeline.
     */
    data object ManualEntry : VoiceCaptureStep()

    /** Recognizer error. Held until the user retries or cancels. */
    data class Error(val message: String) : VoiceCaptureStep()
}

/** What kind of action a captured transcript maps to. */
enum class VoiceCommandCategory {
    /** Safe text — fine to drop into chat or a draft task. */
    SAFE_TEXT,

    /**
     * Vague *or* serious action ("delete the repo", "deploy to prod",
     * "publish it"). Never auto-executed; routed to an approval-needed
     * task instead.
     */
    APPROVAL_REQUIRED,

    /** User cancelled mid-capture (e.g. said "never mind"). */
    CANCEL,
}

/** Result of classifying a transcript. */
data class VoiceCommandClassification(
    val category: VoiceCommandCategory,
    val reason: String? = null,
    val matchedTrigger: String? = null,
)

/**
 * Snapshot the [VoiceCaptureViewModel] exposes to Compose. The screen
 * is a pure function of this state — there are no side channels.
 */
data class VoiceCaptureUiState(
    val step: VoiceCaptureStep = VoiceCaptureStep.Idle,
    val partialTranscript: String = "",
    val finalTranscript: String = "",
    val classification: VoiceCommandClassification? = null,
    /** True when the platform reports SpeechRecognizer support. */
    val sttAvailable: Boolean = true,
    /** Last permission denial was permanent ("don't ask again"). */
    val permissionPermanentlyDenied: Boolean = false,
    /** One-shot toast / snackbar — UI consumes via [VoiceCaptureViewModel.consumeMessage]. */
    val message: String? = null,
    /** One-shot signal that the sheet should close. */
    val dismiss: Boolean = false,
)
