package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.jeremiahecherd.jarvisprime.data.JarvisMode
import com.jeremiahecherd.jarvisprime.data.OnboardingState
import com.jeremiahecherd.jarvisprime.data.SettingsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch

class OnboardingViewModel(
    private val settings: SettingsRepository,
) : ViewModel() {

    val state: Flow<OnboardingState> = settings.state

    fun selectMode(mode: JarvisMode) {
        viewModelScope.launch { settings.setMode(mode) }
    }

    /**
     * Records that the user explicitly opted in to notifications.
     *
     * The runtime POST_NOTIFICATIONS prompt is launched from the
     * education screen itself — this only persists the user's choice.
     */
    fun recordNotificationOptIn() {
        viewModelScope.launch { settings.setNotificationOptIn(true) }
    }

    /**
     * Records that the user explicitly opted in to voice capture.
     *
     * The runtime RECORD_AUDIO prompt is launched from the education
     * screen itself — this only persists the user's choice.
     */
    fun recordVoiceOptIn() {
        viewModelScope.launch { settings.setVoiceOptIn(true) }
    }

    fun completeOnboarding() {
        viewModelScope.launch { settings.setOnboardingComplete(true) }
    }

    fun replayOnboarding() {
        viewModelScope.launch { settings.resetForReplay() }
    }

    fun toggleEmergencyStop(engaged: Boolean) {
        viewModelScope.launch { settings.setEmergencyStopEngaged(engaged) }
    }
}

class OnboardingViewModelFactory(
    private val settings: SettingsRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass.isAssignableFrom(OnboardingViewModel::class.java))
        return OnboardingViewModel(settings) as T
    }
}
