package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.PermissionGate
import com.jarvisprime.notifications.platform.PermissionState

/**
 * State machine for the "education before request" flow.
 *
 * Contract:
 *  1. On first launch the OS prompt MUST NOT be triggered.
 *  2. The education screen MUST be shown before the OS prompt is invoked.
 *  3. If the user dismisses education or denies the OS prompt, the app keeps
 *     working — settings can still be adjusted, in-app banners are used for
 *     emergencies, and we never re-prompt automatically.
 *  4. A user who taps "Enable notifications" inside the education screen is
 *     the only path that calls [PermissionGate.requestPermission].
 */
class NotificationPermissionEducation(
    private val store: EducationStore,
    private val gate: PermissionGate,
) {

    enum class Step {
        SHOW_EDUCATION,
        REQUEST_PERMISSION,
        NOTHING_TO_DO,
        OFFER_SETTINGS_DEEP_LINK,
    }

    fun nextStep(): Step {
        val osState = gate.currentState()
        val state = store.load()
        return when {
            osState == PermissionState.GRANTED -> Step.NOTHING_TO_DO
            osState == PermissionState.DENIED -> Step.OFFER_SETTINGS_DEEP_LINK
            !state.educationShown -> Step.SHOW_EDUCATION
            state.userDismissed -> Step.NOTHING_TO_DO
            else -> Step.REQUEST_PERMISSION
        }
    }

    fun onEducationShown() {
        store.save(store.load().copy(educationShown = true))
    }

    fun onUserAcceptedEducation(onResult: (PermissionState) -> Unit) {
        store.save(store.load().copy(educationShown = true, userAccepted = true, userDismissed = false))
        gate.requestPermission { state ->
            if (state == PermissionState.DENIED) {
                store.save(store.load().copy(lastDeniedAt = System.currentTimeMillis()))
            }
            onResult(state)
        }
    }

    fun onUserDismissedEducation() {
        store.save(store.load().copy(educationShown = true, userDismissed = true))
    }

    fun hasUserOptedOut(): Boolean = store.load().userDismissed
}

data class EducationState(
    val educationShown: Boolean = false,
    val userAccepted: Boolean = false,
    val userDismissed: Boolean = false,
    val lastDeniedAt: Long? = null,
)

interface EducationStore {
    fun load(): EducationState
    fun save(state: EducationState)
}

class InMemoryEducationStore(initial: EducationState = EducationState()) : EducationStore {
    private var current: EducationState = initial
    override fun load(): EducationState = current
    override fun save(state: EducationState) {
        current = state
    }
}
