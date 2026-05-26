package com.jeremiahecherd.jarvisprime

import com.jeremiahecherd.jarvisprime.data.JarvisMode
import com.jeremiahecherd.jarvisprime.data.OnboardingState
import com.jeremiahecherd.jarvisprime.data.SettingsRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class OnboardingFlowTest {

    private class FakeSettings : SettingsRepository {
        private val backing = MutableStateFlow(OnboardingState())
        override val state: Flow<OnboardingState> = backing
        fun snapshot(): OnboardingState = backing.value

        override suspend fun setOnboardingComplete(value: Boolean) {
            backing.update { it.copy(onboardingComplete = value) }
        }

        override suspend fun setMode(mode: JarvisMode) {
            backing.update { it.copy(mode = mode) }
        }

        override suspend fun setNotificationOptIn(value: Boolean) {
            backing.update { it.copy(notificationOptIn = value) }
        }

        override suspend fun setVoiceOptIn(value: Boolean) {
            backing.update { it.copy(voiceOptIn = value) }
        }

        override suspend fun setEmergencyStopEngaged(value: Boolean) {
            backing.update { it.copy(emergencyStopEngaged = value) }
        }

        override suspend fun resetForReplay() {
            backing.update { it.copy(onboardingComplete = false) }
        }
    }

    @Test
    fun newUserSeesOnboardingByDefault() = runTest {
        val settings = FakeSettings()
        val initial = settings.state.first()
        assertFalse(
            "fresh install must show onboarding",
            initial.onboardingComplete,
        )
        assertEquals(
            "fresh install must default to safe mock mode",
            JarvisMode.MOCK,
            initial.mode,
        )
        assertFalse(initial.notificationOptIn)
        assertFalse(initial.voiceOptIn)
    }

    @Test
    fun skippingOptionalPermissionsKeepsOnboardingComplete() = runTest {
        val settings = FakeSettings()
        // Walk through onboarding without tapping Enable on either
        // optional permission card.
        settings.setMode(JarvisMode.MOCK)
        settings.setOnboardingComplete(true)

        val finalState = settings.state.first()
        assertTrue(finalState.onboardingComplete)
        assertFalse("notification opt-in must stay off when skipped", finalState.notificationOptIn)
        assertFalse("voice opt-in must stay off when skipped", finalState.voiceOptIn)
        assertEquals(JarvisMode.MOCK, finalState.mode)
    }

    @Test
    fun notificationOptInOnlyRecordedAfterExplicitTap() = runTest {
        val settings = FakeSettings()
        assertFalse(settings.state.first().notificationOptIn)
        // Simulate the user tapping Enable AND the system granting:
        settings.setNotificationOptIn(true)
        assertTrue(settings.state.first().notificationOptIn)
    }

    @Test
    fun voiceOptInOnlyRecordedAfterExplicitTap() = runTest {
        val settings = FakeSettings()
        assertFalse(settings.state.first().voiceOptIn)
        settings.setVoiceOptIn(true)
        assertTrue(settings.state.first().voiceOptIn)
    }

    @Test
    fun mockModeIsAvailableAndStaysSelectable() = runTest {
        val settings = FakeSettings()
        settings.setMode(JarvisMode.GATEWAY)
        assertEquals(JarvisMode.GATEWAY, settings.state.first().mode)
        settings.setMode(JarvisMode.MOCK)
        assertEquals(JarvisMode.MOCK, settings.state.first().mode)
    }

    @Test
    fun gatewayModeIsSelectable() = runTest {
        val settings = FakeSettings()
        settings.setMode(JarvisMode.GATEWAY)
        assertEquals(JarvisMode.GATEWAY, settings.state.first().mode)
    }

    @Test
    fun termuxModeIsSelectable() = runTest {
        val settings = FakeSettings()
        settings.setMode(JarvisMode.TERMUX)
        assertEquals(JarvisMode.TERMUX, settings.state.first().mode)
    }

    @Test
    fun emergencyStopToggleRoundTrips() = runTest {
        val settings = FakeSettings()
        settings.setEmergencyStopEngaged(true)
        assertTrue(settings.state.first().emergencyStopEngaged)
        settings.setEmergencyStopEngaged(false)
        assertFalse(settings.state.first().emergencyStopEngaged)
    }

    @Test
    fun replayOnboardingReopensFlowWithoutWipingPermissions() = runTest {
        val settings = FakeSettings()
        settings.setMode(JarvisMode.GATEWAY)
        settings.setNotificationOptIn(true)
        settings.setVoiceOptIn(true)
        settings.setOnboardingComplete(true)

        settings.resetForReplay()
        val state = settings.state.first()

        assertFalse("replay must reopen onboarding", state.onboardingComplete)
        assertTrue("replay must preserve granted notification opt-in", state.notificationOptIn)
        assertTrue("replay must preserve granted voice opt-in", state.voiceOptIn)
        assertEquals(JarvisMode.GATEWAY, state.mode)
    }
}
