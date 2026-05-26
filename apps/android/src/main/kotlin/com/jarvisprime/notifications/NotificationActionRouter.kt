package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.EmergencyStopController
import com.jarvisprime.notifications.platform.EmergencyStopResult
import com.jarvisprime.notifications.platform.NavigationTarget
import com.jarvisprime.notifications.platform.Navigator
import com.jarvisprime.notifications.platform.NotificationPresenter

/**
 * Resolves a tap on a notification action into the safe in-app behaviour.
 *
 * Safety rules:
 *  - EMERGENCY_STOP is the only action that can mutate worker state from a
 *    notification tap. It MUST go through a confirmation step (either an
 *    in-app sheet that the user must accept, or a hold-to-confirm gesture).
 *  - All routes call the platform [Navigator] so deep links open the right
 *    screen even if the app was killed.
 *  - The notification is always cancelled after handling to keep the shade clean.
 */
class NotificationActionRouter(
    private val mapper: NotificationEventMapper,
    private val navigator: Navigator,
    private val emergencyStop: EmergencyStopController,
    private val presenter: NotificationPresenter,
    private val confirmation: EmergencyStopConfirmation = EmergencyStopConfirmation.RequireExplicit,
) {

    fun handle(action: NotificationAction, event: NotificationEvent): RouteResult {
        val result = when (action) {
            NotificationAction.OPEN_APPROVAL -> {
                navigator.navigateTo(NavigationTarget.APPROVALS, event)
                RouteResult.Navigated(NavigationTarget.APPROVALS)
            }
            NotificationAction.OPEN_TASK -> {
                navigator.navigateTo(NavigationTarget.TASKS, event)
                RouteResult.Navigated(NavigationTarget.TASKS)
            }
            NotificationAction.OPEN_AUDIT -> {
                navigator.navigateTo(NavigationTarget.AUDIT, event)
                RouteResult.Navigated(NavigationTarget.AUDIT)
            }
            NotificationAction.EMERGENCY_STOP -> triggerEmergencyStop(event)
            NotificationAction.DISMISS -> RouteResult.Dismissed
        }
        if (result !is RouteResult.NeedsConfirmation) {
            presenter.cancel(event.id)
        }
        return result
    }

    /**
     * Called after the user explicitly confirms the emergency-stop prompt
     * surfaced by [handle]. Bypassing this with a direct call defeats the
     * safety contract.
     */
    fun confirmEmergencyStop(event: NotificationEvent, reason: String): RouteResult {
        val outcome = emergencyStop.trigger(reason)
        navigator.navigateTo(NavigationTarget.EMERGENCY_STOP, event)
        presenter.cancel(event.id)
        return RouteResult.EmergencyStop(outcome)
    }

    private fun triggerEmergencyStop(event: NotificationEvent): RouteResult {
        return when (confirmation) {
            EmergencyStopConfirmation.RequireExplicit -> {
                navigator.navigateTo(NavigationTarget.EMERGENCY_STOP, event)
                RouteResult.NeedsConfirmation(event)
            }
            EmergencyStopConfirmation.HoldGesture -> {
                navigator.navigateTo(NavigationTarget.EMERGENCY_STOP, event)
                RouteResult.NeedsConfirmation(event)
            }
            EmergencyStopConfirmation.TestOnlyImmediate -> {
                val outcome = emergencyStop.trigger("notification-tap:${event.id}")
                RouteResult.EmergencyStop(outcome)
            }
        }
    }

    /** Convenience for clients that want the canonical target for a type. */
    fun targetFor(type: NotificationType): NavigationTarget = mapper.target(type)

    enum class EmergencyStopConfirmation {
        RequireExplicit,
        HoldGesture,
        TestOnlyImmediate,
    }
}

sealed class RouteResult {
    data class Navigated(val target: NavigationTarget) : RouteResult()
    data class NeedsConfirmation(val event: NotificationEvent) : RouteResult()
    data class EmergencyStop(val outcome: EmergencyStopResult) : RouteResult()
    object Dismissed : RouteResult()
}
