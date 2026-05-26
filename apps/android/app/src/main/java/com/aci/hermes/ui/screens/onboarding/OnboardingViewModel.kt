package com.aci.hermes.ui.screens.onboarding

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class OnboardingStep { Welcome, Safety, Voice, Notifications }

data class OnboardingUiState(
    val step: OnboardingStep = OnboardingStep.Welcome,
    val notificationPermissionGranted: Boolean = true, // < Android 13
)

class OnboardingViewModel(
    application: Application,
    private val settings: SettingsRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(OnboardingUiState(notificationPermissionGranted = currentNotificationGranted()))
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    fun next() {
        _state.update {
            val nextStep = when (it.step) {
                OnboardingStep.Welcome -> OnboardingStep.Safety
                OnboardingStep.Safety -> OnboardingStep.Voice
                OnboardingStep.Voice -> OnboardingStep.Notifications
                OnboardingStep.Notifications -> OnboardingStep.Notifications
            }
            it.copy(step = nextStep)
        }
    }

    fun back() {
        _state.update {
            val prev = when (it.step) {
                OnboardingStep.Welcome -> OnboardingStep.Welcome
                OnboardingStep.Safety -> OnboardingStep.Welcome
                OnboardingStep.Voice -> OnboardingStep.Safety
                OnboardingStep.Notifications -> OnboardingStep.Voice
            }
            it.copy(step = prev)
        }
    }

    fun onNotificationPermissionResult(granted: Boolean) {
        _state.update { it.copy(notificationPermissionGranted = granted) }
        viewModelScope.launch {
            settings.setStatusNotificationOptIn(granted)
        }
    }

    fun skipNotifications() {
        viewModelScope.launch {
            settings.setStatusNotificationOptIn(false)
        }
    }

    fun complete() {
        viewModelScope.launch {
            settings.setOnboarded(true)
        }
    }

    private fun currentNotificationGranted(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            getApplication(),
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
    }
}
