package com.aci.hermes.ui.screens.live

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.emergency.EmergencyStopRepository
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.ui.jarvis.AvatarActivity
import com.aci.hermes.ui.jarvis.AvatarRenderSpec
import com.aci.hermes.ui.jarvis.AvatarStateMapper
import com.aci.hermes.ui.jarvis.IconStateInputs
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn

/**
 * One-screen render state for the Jarvis Live cockpit. Combines:
 *  - the orchestrator service liveness (drives `gatewayOnline`),
 *  - the emergency-stop subsystem (drives `blocked`),
 *  - the operator's current activity hint (drives status text),
 *  - the platform's reduced-motion preference.
 *
 * The mapper ([AvatarStateMapper]) is the single source of truth for
 * how these collapse — this VM does not re-implement the rules.
 *
 * Inputs are deliberately limited at launch: listening / thinking /
 * speaking / approval signals are not wired here yet. The full
 * cockpit-grade wiring lands in a follow-up branch; the safety floor
 * (emergency stop → blocked, service down → offline) is the must-have.
 */
class JarvisLiveViewModel(
    private val emergencyStop: EmergencyStopRepository,
    private val serviceRunning: StateFlow<Boolean>,
    private val reducedMotion: StateFlow<Boolean>,
) : ViewModel() {

    private val _activity = MutableStateFlow(AvatarActivity.Idle)

    /** Current activity hint. Callers (e.g. chat VM) push updates here. */
    val activity: StateFlow<AvatarActivity> = _activity

    fun setActivity(next: AvatarActivity) {
        _activity.value = next
    }

    val renderSpec: StateFlow<AvatarRenderSpec> = combine(
        serviceRunning,
        emergencyStop.state,
        _activity,
        reducedMotion,
    ) { running, stopState, activity, reduced ->
        val inputs = IconStateInputs(
            gatewayOnline = running,
            blocked = stopState != EmergencyStopState.INACTIVE,
        )
        AvatarStateMapper.map(inputs, activity, reduced)
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000L),
        initialValue = AvatarStateMapper.map(
            inputs = IconStateInputs(gatewayOnline = false),
            activity = AvatarActivity.Idle,
            reducedMotion = false,
        ),
    )

    class Factory(
        private val emergencyStop: EmergencyStopRepository,
        private val serviceRunning: StateFlow<Boolean>,
        private val reducedMotion: StateFlow<Boolean>,
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
            JarvisLiveViewModel(emergencyStop, serviceRunning, reducedMotion) as T
    }
}
