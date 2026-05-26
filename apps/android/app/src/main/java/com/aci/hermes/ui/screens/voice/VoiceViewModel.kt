package com.aci.hermes.ui.screens.voice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.safety.JarvisPermission
import com.aci.hermes.safety.PermissionKernel
import com.aci.hermes.safety.PermissionState
import com.aci.hermes.voice.VoiceCapture
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

data class VoiceUiState(
    val capture: VoiceCapture.State = VoiceCapture.State.IDLE,
    val transcript: String = "",
    val micState: PermissionState = PermissionState.NOT_REQUESTED,
    /**
     * Set non-null when the screen needs the Activity-bound router to
     * walk the owner through the mic-permission flow.
     */
    val requestMicPermission: Boolean = false,
)

class VoiceViewModel(
    private val capture: VoiceCapture,
    private val permissionKernel: PermissionKernel,
) : ViewModel() {

    private val _state = MutableStateFlow(VoiceUiState())
    val state: StateFlow<VoiceUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            combine(capture.state, capture.transcript, permissionKernel.states) { c, t, perms ->
                VoiceUiState(
                    capture = c,
                    transcript = t,
                    micState = perms[JarvisPermission.MICROPHONE] ?: PermissionState.NOT_REQUESTED,
                )
            }.collect { snapshot ->
                _state.value = _state.value.copy(
                    capture = snapshot.capture,
                    transcript = snapshot.transcript,
                    micState = snapshot.micState,
                )
            }
        }
    }

    /** User tapped the hold-to-talk control. */
    fun onTalkPressed() {
        if (state.value.micState != PermissionState.GRANTED) {
            _state.value = _state.value.copy(requestMicPermission = true)
            return
        }
        capture.arm()
        capture.start()
    }

    fun onTalkReleased(): String {
        if (state.value.micState != PermissionState.GRANTED) return ""
        return capture.release().also { capture.reset() }
    }

    fun consumePermissionRequest() {
        _state.value = _state.value.copy(requestMicPermission = false)
    }
}
