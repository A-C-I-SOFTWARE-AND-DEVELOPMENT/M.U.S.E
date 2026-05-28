package com.aci.hermes.ui.screens.voice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.jarvis.JarvisTaskSink
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Hands-free capture surface for Jarvis Prime.
 *
 * The screen drives the *system* speech recognizer (an Activity result
 * contract over [android.speech.RecognizerIntent]); this view model
 * only owns the resulting transcript and the "promote to task" action.
 * That split keeps the VM a plain [ViewModel] with no Android speech
 * dependency, so it unit-tests without Robolectric and the app never
 * needs the RECORD_AUDIO permission (the system UI owns the mic).
 *
 * Promotion reuses the same [JarvisTaskSink] the chat surface uses, so
 * a voice-created task lands in exactly the same orchestrator store and
 * shows up on the Tasks screen.
 */
class VoiceCaptureViewModel(
    private val taskSink: JarvisTaskSink,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(VoiceCaptureUiState())
    val state: StateFlow<VoiceCaptureUiState> = _state.asStateFlow()

    fun onListeningStart() {
        _state.update { it.copy(listening = true, error = null) }
    }

    fun onListeningCancelled() {
        _state.update { it.copy(listening = false) }
    }

    fun onRecognizerUnavailable() {
        _state.update {
            it.copy(
                listening = false,
                error = "No speech recognizer is available on this device.",
            )
        }
    }

    fun onTranscript(text: String) {
        val cleaned = text.trim()
        _state.update {
            it.copy(
                listening = false,
                transcript = cleaned,
                error = if (cleaned.isEmpty()) "Didn't catch that — try again." else null,
            )
        }
    }

    fun clearTranscript() {
        _state.update { it.copy(transcript = "", error = null) }
    }

    /**
     * Promote the current transcript into a draft task. No-op when the
     * transcript is blank or a save is already in flight. On success the
     * created task id is surfaced so the screen can route to Tasks.
     */
    fun saveAsTask() {
        val transcript = _state.value.transcript.trim()
        if (transcript.isEmpty() || _state.value.saving) return
        _state.update { it.copy(saving = true) }
        viewModelScope.launch {
            val task = HermesTask(
                title = deriveTitle(transcript),
                description = transcript,
                taskType = TaskType.PLANNING,
                status = TaskStatus.DRAFT,
                promptBody = transcript,
            )
            val saved = taskSink.upsert(task)
            logBuffer.info(TAG, "Voice capture promoted to task ${saved.id}")
            _state.update {
                it.copy(saving = false, savedTaskId = saved.id, transcript = "")
            }
        }
    }

    fun consumeSavedTask() {
        _state.update { it.copy(savedTaskId = null) }
    }

    private fun deriveTitle(transcript: String): String {
        val firstLine = transcript.lineSequence().firstOrNull()?.trim().orEmpty()
        val base = firstLine.ifEmpty { transcript }
        return if (base.length <= TITLE_MAX) base else base.take(TITLE_MAX).trimEnd() + "…"
    }

    private companion object {
        const val TAG = "VoiceCapture"
        const val TITLE_MAX = 60
    }
}

data class VoiceCaptureUiState(
    val listening: Boolean = false,
    val transcript: String = "",
    val saving: Boolean = false,
    val savedTaskId: String? = null,
    val error: String? = null,
)
