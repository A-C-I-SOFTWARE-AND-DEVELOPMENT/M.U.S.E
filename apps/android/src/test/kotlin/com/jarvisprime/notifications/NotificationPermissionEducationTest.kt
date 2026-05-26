package com.jarvisprime.notifications

import com.jarvisprime.notifications.NotificationPermissionEducation.Step
import com.jarvisprime.notifications.platform.PermissionState
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class NotificationPermissionEducationTest {

    @Test
    fun `first launch shows education before requesting permission`() {
        val gate = FakePermissionGate(state = PermissionState.NOT_DETERMINED)
        val education = NotificationPermissionEducation(InMemoryEducationStore(), gate)

        assertEquals(Step.SHOW_EDUCATION, education.nextStep())
        assertEquals(0, gate.requestCount, "OS prompt must not fire before education")
    }

    @Test
    fun `request is only triggered after the user accepts education`() {
        val gate = FakePermissionGate(state = PermissionState.NOT_DETERMINED)
        val store = InMemoryEducationStore()
        val education = NotificationPermissionEducation(store, gate)

        education.onEducationShown()
        assertEquals(Step.REQUEST_PERMISSION, education.nextStep())
        assertEquals(0, gate.requestCount, "showing education alone must not trigger OS prompt")

        var result: PermissionState? = null
        gate.state = PermissionState.GRANTED
        education.onUserAcceptedEducation { result = it }

        assertEquals(1, gate.requestCount)
        assertEquals(PermissionState.GRANTED, result)
    }

    @Test
    fun `dismissing education locks app into in-app-only mode without re-prompting`() {
        val gate = FakePermissionGate(state = PermissionState.NOT_DETERMINED)
        val store = InMemoryEducationStore()
        val education = NotificationPermissionEducation(store, gate)

        education.onEducationShown()
        education.onUserDismissedEducation()

        assertEquals(Step.NOTHING_TO_DO, education.nextStep())
        assertTrue(education.hasUserOptedOut())
        assertEquals(0, gate.requestCount)
    }

    @Test
    fun `denied permission records timestamp and offers settings deep link`() {
        val gate = FakePermissionGate(
            state = PermissionState.NOT_DETERMINED,
            onRequest = { g, cb ->
                g.state = PermissionState.DENIED
                cb(PermissionState.DENIED)
            },
        )
        val store = InMemoryEducationStore()
        val education = NotificationPermissionEducation(store, gate)

        education.onEducationShown()
        education.onUserAcceptedEducation { /* ignored */ }

        assertEquals(Step.OFFER_SETTINGS_DEEP_LINK, education.nextStep())
        val state = store.load()
        assertTrue(state.userAccepted)
        assertFalse(state.lastDeniedAt == null, "denial timestamp must be recorded")
    }

    @Test
    fun `granted permission yields nothing to do`() {
        val gate = FakePermissionGate(state = PermissionState.GRANTED)
        val education = NotificationPermissionEducation(InMemoryEducationStore(), gate)
        assertEquals(Step.NOTHING_TO_DO, education.nextStep())
    }
}
