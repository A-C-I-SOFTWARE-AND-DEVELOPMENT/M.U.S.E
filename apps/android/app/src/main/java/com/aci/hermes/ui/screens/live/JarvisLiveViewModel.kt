package com.aci.hermes.ui.screens.live

import android.app.Application
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class JarvisLiveViewModel(
    application: Application,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(
        JarvisLiveUiState(reducedMotion = systemReducedMotion()),
    )
    val state: StateFlow<JarvisLiveUiState> = _state.asStateFlow()

    private val _showStatusSheet = MutableStateFlow(false)
    val showStatusSheet: StateFlow<Boolean> = _showStatusSheet.asStateFlow()

    private val _showEmergencyConfirm = MutableStateFlow(false)
    val showEmergencyConfirm: StateFlow<Boolean> = _showEmergencyConfirm.asStateFlow()

    fun refreshReducedMotion() {
        val current = systemReducedMotion()
        _state.update { it.copy(reducedMotion = current) }
    }

    fun onCommandChange(text: String) {
        _state.update { it.copy(command = text) }
    }

    fun onSend() {
        val current = _state.value
        if (current.command.isBlank() || current.emergencyStop) return
        _state.update { it.copy(thinking = true, listening = false) }
    }

    fun openStatusSheet() { _showStatusSheet.value = true }
    fun dismissStatusSheet() { _showStatusSheet.value = false }

    fun requestEmergencyConfirm() { _showEmergencyConfirm.value = true }
    fun dismissEmergencyConfirm() { _showEmergencyConfirm.value = false }

    fun confirmEmergencyStop() {
        _showEmergencyConfirm.value = false
        _state.update {
            it.copy(
                emergencyStop = true,
                thinking = false,
                working = false,
                speaking = false,
                listening = false,
            )
        }
    }

    fun releaseEmergencyStop() {
        _state.update { it.copy(emergencyStop = false) }
    }

    fun approveApproval() {
        _state.update { it.copy(approvalNeeded = false, working = true) }
    }

    private fun systemReducedMotion(): Boolean {
        val ctx = getApplication<Application>()
        val scale = Settings.Global.getFloat(
            ctx.contentResolver,
            Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        )
        return scale == 0f
    }
}
