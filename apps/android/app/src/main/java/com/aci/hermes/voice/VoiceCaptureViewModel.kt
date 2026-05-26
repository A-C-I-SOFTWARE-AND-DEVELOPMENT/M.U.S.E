package com.aci.hermes.voice

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Drives the JARVIS Prime voice-capture sheet. All transitions are
 * triggered by explicit user actions — the ViewModel never starts the
 * recognizer on its own, and it never executes a captured command
 * directly. Routing decisions go through [VoiceCaptureRouter].
 *
 * Permission handling lives in the Compose layer. The ViewModel only
 * sees boolean outcomes via [onPermissionResult]; it does not hold
 * Android Context or `ActivityResultLauncher` references, so it stays
 * unit-testable on plain JVM.
 */
class VoiceCaptureViewModel(
    private val recognizer: VoiceRecognizer,
    private val router: VoiceCaptureRouter,
    private val classifier: VoiceIntentClassifier = VoiceIntentClassifier(),
    scope: CoroutineScope? = null,
) : ViewModel() {

    private val ownScope = scope == null
    private val workScope: CoroutineScope =
        scope ?: CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private val _state = MutableStateFlow(
        VoiceCaptureUiState(sttAvailable = recognizer.isAvailable),
    )
    val state: StateFlow<VoiceCaptureUiState> = _state.asStateFlow()

    private var recognizerJob: Job? = null

    init {
        recognizerJob = workScope.launch {
            recognizer.events.collect { event -> handleRecognizerEvent(event) }
        }
    }

    // -----------------------------------------------------------------------
    // Public entry points — every step is a user-initiated action.
    // -----------------------------------------------------------------------

    /** User tapped the voice button. Open the sheet with the education panel. */
    fun open() {
        _state.update {
            it.copy(
                step = VoiceCaptureStep.Education,
                partialTranscript = "",
                finalTranscript = "",
                classification = null,
                dismiss = false,
                message = null,
            )
        }
    }

    /** User read the education and tapped "Allow microphone". */
    fun acknowledgeEducation() {
        if (!recognizer.isAvailable) {
            _state.update {
                it.copy(
                    step = VoiceCaptureStep.ManualEntry,
                    message = "No on-device speech recogniser. Type your request instead.",
                )
            }
            return
        }
        _state.update { it.copy(step = VoiceCaptureStep.RequestingPermission) }
    }

    /** The Compose layer reports the result of the system permission dialog. */
    fun onPermissionResult(granted: Boolean, permanentlyDenied: Boolean = false) {
        if (!granted) {
            _state.update {
                it.copy(
                    step = VoiceCaptureStep.PermissionDenied,
                    permissionPermanentlyDenied = permanentlyDenied,
                )
            }
            return
        }
        _state.update {
            it.copy(
                step = VoiceCaptureStep.Listening,
                partialTranscript = "",
                finalTranscript = "",
                classification = null,
                permissionPermanentlyDenied = false,
            )
        }
        recognizer.start()
    }

    /** User pressed "Stop". The recognizer should deliver a final result. */
    fun stop() {
        if (_state.value.step !is VoiceCaptureStep.Listening) return
        recognizer.stop()
    }

    /** User pressed the X / back. Abort everything and reset to Idle. */
    fun cancel() {
        recognizer.cancel()
        _state.update {
            it.copy(
                step = VoiceCaptureStep.Idle,
                partialTranscript = "",
                finalTranscript = "",
                classification = null,
                dismiss = true,
            )
        }
    }

    /** Used by the manual entry text field. */
    fun setManualTranscript(text: String) {
        _state.update { it.copy(finalTranscript = text) }
    }

    /** Confirm the manually typed transcript (or one captured from STT) for routing. */
    fun acceptCapturedTranscript() {
        val current = _state.value
        val text = current.finalTranscript.ifBlank { current.partialTranscript }.trim()
        if (text.isEmpty()) {
            _state.update { it.copy(message = "Nothing captured yet.") }
            return
        }
        val classified = classifier.classify(text)
        if (classified.category == VoiceCommandCategory.CANCEL) {
            cancel()
            return
        }
        _state.update {
            it.copy(
                step = VoiceCaptureStep.Captured,
                finalTranscript = text,
                classification = classified,
            )
        }
    }

    /** Edit the transcript before routing (e.g. fix a recognition mistake). */
    fun editTranscript(text: String) {
        _state.update { current ->
            // Re-classify on edit so the approval banner stays accurate.
            val classified = classifier.classify(text)
            current.copy(
                finalTranscript = text,
                classification = classified,
            )
        }
    }

    /** Route the captured text to the chat / orchestrator new-task draft. */
    fun sendToChat() {
        val current = _state.value
        val text = current.finalTranscript.trim()
        if (text.isEmpty()) return
        val classification = current.classification ?: classifier.classify(text)
        workScope.launch {
            val result = router.sendToChat(text, classification)
            applyRoutingResult(result)
        }
    }

    /** Route the captured text into a new draft [HermesTask]. */
    fun createTask() {
        val current = _state.value
        val text = current.finalTranscript.trim()
        if (text.isEmpty()) return
        val classification = current.classification ?: classifier.classify(text)
        workScope.launch {
            val result = router.createTask(text, classification)
            applyRoutingResult(result)
        }
    }

    fun consumeMessage() {
        _state.update { it.copy(message = null) }
    }

    fun consumeDismiss() {
        _state.update { it.copy(dismiss = false, step = VoiceCaptureStep.Idle) }
    }

    // -----------------------------------------------------------------------
    // Recognizer plumbing
    // -----------------------------------------------------------------------

    private fun handleRecognizerEvent(event: VoiceRecognizerEvent) {
        when (event) {
            is VoiceRecognizerEvent.Partial -> {
                if (_state.value.step is VoiceCaptureStep.Listening) {
                    _state.update { it.copy(partialTranscript = event.text) }
                }
            }
            is VoiceRecognizerEvent.Final -> {
                val text = event.text.trim()
                if (text.isEmpty()) {
                    _state.update {
                        it.copy(
                            step = VoiceCaptureStep.Captured,
                            finalTranscript = "",
                            classification = null,
                            message = "No speech detected — try again or type the request.",
                        )
                    }
                    return
                }
                val classified = classifier.classify(text)
                if (classified.category == VoiceCommandCategory.CANCEL) {
                    cancel()
                    return
                }
                _state.update {
                    it.copy(
                        step = VoiceCaptureStep.Captured,
                        finalTranscript = text,
                        partialTranscript = "",
                        classification = classified,
                    )
                }
            }
            is VoiceRecognizerEvent.Error -> {
                _state.update {
                    it.copy(
                        step = VoiceCaptureStep.Error(event.message),
                        message = event.message,
                    )
                }
            }
            VoiceRecognizerEvent.Ready,
            VoiceRecognizerEvent.Listening,
            VoiceRecognizerEvent.EndOfSpeech -> {
                // No state change — listening UI is already visible. The
                // EndOfSpeech signal is followed by Final or Error.
            }
        }
    }

    private fun applyRoutingResult(result: VoiceCaptureRouter.RoutingResult) {
        when (result) {
            is VoiceCaptureRouter.RoutingResult.Ok -> {
                _state.update {
                    it.copy(
                        message = result.message,
                        dismiss = true,
                        step = VoiceCaptureStep.Idle,
                        partialTranscript = "",
                        finalTranscript = "",
                        classification = null,
                    )
                }
            }
            is VoiceCaptureRouter.RoutingResult.Failed -> {
                _state.update { it.copy(message = result.message) }
            }
        }
    }

    /**
     * Release recognizer resources and cancel the collector job. Exposed
     * so unit tests can clean up without poking the protected
     * [ViewModel.onCleared] hook.
     */
    fun dispose() {
        recognizerJob?.cancel()
        recognizer.cancel()
        recognizer.release()
        if (ownScope) {
            workScope.cancel()
        }
    }

    override fun onCleared() {
        dispose()
        super.onCleared()
    }
}
