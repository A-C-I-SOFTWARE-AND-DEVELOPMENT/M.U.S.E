package com.aci.hermes.ui.screens.voice

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.conversation.ConversationRepository
import com.aci.hermes.data.model.AuditKind
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class VoiceCaptureState { Idle, Recording, Transcribing, Captured, Denied }

data class VoiceUiState(
    val state: VoiceCaptureState = VoiceCaptureState.Idle,
    val transcript: String = "",
    val hasMicPermission: Boolean = false,
)

/**
 * Voice capture is a one-shot flow.
 *
 * The mic permission is requested only when the user taps "Start
 * capture" — there is no always-listening, no background mic, no
 * always-on hot-word. When the gateway is wired, the captured audio
 * goes there for transcription. In mock mode we simulate a short
 * latency then drop a sample transcript in.
 */
class VoiceCaptureViewModel(
    application: Application,
    private val conversations: ConversationRepository,
    private val audit: AuditRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(VoiceUiState())
    val state: StateFlow<VoiceUiState> = _state.asStateFlow()

    fun onPermissionResult(granted: Boolean) {
        _state.update {
            it.copy(
                hasMicPermission = granted,
                state = if (granted) VoiceCaptureState.Recording else VoiceCaptureState.Denied,
            )
        }
        if (granted) startMockCapture()
    }

    fun startCapture() {
        if (_state.value.hasMicPermission) {
            _state.update { it.copy(state = VoiceCaptureState.Recording) }
            startMockCapture()
        }
    }

    fun stopCapture() {
        if (_state.value.state == VoiceCaptureState.Recording) {
            _state.update { it.copy(state = VoiceCaptureState.Transcribing) }
        }
    }

    private fun startMockCapture() {
        // Mock mode just plays the role of an STT engine; replace with
        // gateway dispatch when wiring real speech recognition.
        viewModelScope.launch {
            kotlinx.coroutines.delay(1500)
            _state.update { it.copy(state = VoiceCaptureState.Transcribing) }
            kotlinx.coroutines.delay(700)
            val transcript = SAMPLE_TRANSCRIPTS.random()
            _state.update {
                it.copy(
                    state = VoiceCaptureState.Captured,
                    transcript = transcript,
                )
            }
            conversations.appendUser(transcript)
            audit.record(
                kind = AuditKind.SYSTEM,
                title = "Voice captured",
                detail = "Mic was opened once, captured \"${transcript.take(80)}\", then released.",
            )
        }
    }

    fun reset() {
        _state.update { it.copy(state = VoiceCaptureState.Idle, transcript = "") }
    }

    companion object {
        private val SAMPLE_TRANSCRIPTS = listOf(
            "Show me what's waiting for approval.",
            "Plan a draft of the release notes.",
            "Remember that I prefer short replies.",
            "What did you do in the last hour?",
        )
    }
}
