package com.aci.hermes.ui.screens.emergency

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.model.EmergencyStopState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EmergencyStopUiState(
    val state: EmergencyStopState = EmergencyStopState(),
)

class EmergencyStopViewModel(
    application: Application,
    private val emergencyStop: EmergencyStopController,
    @Suppress("UNUSED_PARAMETER") private val audit: AuditRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(EmergencyStopUiState())
    val state: StateFlow<EmergencyStopUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            emergencyStop.state.collect { es ->
                _state.update { it.copy(state = es) }
            }
        }
    }

    fun engage(reason: String?) {
        emergencyStop.engage(reason)
    }

    fun release() {
        emergencyStop.release()
    }
}
