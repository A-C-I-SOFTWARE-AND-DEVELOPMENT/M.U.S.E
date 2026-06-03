package com.aci.hermes.ui.screens.live

import android.app.Application
import android.graphics.BitmapFactory
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.avatar.AvatarRepository
import com.aci.hermes.data.avatar.AvatarSource
import com.aci.hermes.data.life.BehaviorScheduler
import java.util.Calendar
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class JarvisLiveViewModel(
    application: Application,
    private val avatarRepository: AvatarRepository? = null,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(
        JarvisLiveUiState(reducedMotion = systemReducedMotion()),
    )
    val state: StateFlow<JarvisLiveUiState> = _state.asStateFlow()

    // Ambient life: when the user is away, Jarvis idles → wanders → sleeps so the
    // body reads as alive rather than frozen. Driven by the pure, tested
    // BehaviorScheduler; suppressed while the agent is busy or motion is reduced.
    private val ambientScheduler = BehaviorScheduler()

    @Volatile
    private var lastInteractionAtMs = System.currentTimeMillis()

    init {
        startAmbientLife()
        observeSavedAvatar()
    }

    /** Render the user's saved avatar as the living body: a GENERATED photo
     *  becomes a breathing photo face; otherwise the procedural humanoid. */
    private fun observeSavedAvatar() {
        val repo = avatarRepository ?: return
        viewModelScope.launch {
            repo.profileFlow.collect { profile ->
                val photo = if (
                    profile?.source == AvatarSource.GENERATED && profile.generatedPath != null
                ) {
                    withContext(Dispatchers.IO) {
                        runCatching { BitmapFactory.decodeFile(profile.generatedPath) }.getOrNull()
                    }
                } else {
                    null
                }
                _state.update {
                    if (photo != null) {
                        it.copy(avatarKind = AvatarKind.Photo, avatarPhoto = photo)
                    } else {
                        it.copy(avatarKind = AvatarKind.Character3D, avatarPhoto = null)
                    }
                }
            }
        }
    }

    private fun markInteraction() {
        lastInteractionAtMs = System.currentTimeMillis()
    }

    private fun startAmbientLife() {
        viewModelScope.launch {
            while (isActive) {
                val s = _state.value
                val idleFor = (System.currentTimeMillis() - lastInteractionAtMs)
                    .coerceAtLeast(0L).milliseconds
                val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
                val behavior = ambientScheduler.decide(
                    BehaviorScheduler.Tick(
                        idleFor = idleFor,
                        localHour = hour,
                        hasPendingRecommendation = false,
                        sinceLastRecommendation = Duration.ZERO,
                        agentBusy = s.thinking || s.working || s.speaking,
                        ambientMuted = s.reducedMotion || s.emergencyStop,
                    ),
                )
                if (behavior != s.avatarBehavior) {
                    _state.update { it.copy(avatarBehavior = behavior) }
                }
                delay(AMBIENT_TICK_MS)
            }
        }
    }

    private val _showStatusSheet = MutableStateFlow(false)
    val showStatusSheet: StateFlow<Boolean> = _showStatusSheet.asStateFlow()

    private val _showEmergencyConfirm = MutableStateFlow(false)
    val showEmergencyConfirm: StateFlow<Boolean> = _showEmergencyConfirm.asStateFlow()

    fun refreshReducedMotion() {
        val current = systemReducedMotion()
        _state.update { it.copy(reducedMotion = current) }
    }

    fun onCommandChange(text: String) {
        markInteraction()
        _state.update { it.copy(command = text) }
    }

    fun onSend() {
        markInteraction()
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

    private companion object {
        const val AMBIENT_TICK_MS = 5_000L
    }
}
