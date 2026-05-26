package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.NotificationPresenter
import com.jarvisprime.notifications.platform.PermissionGate
import com.jarvisprime.notifications.platform.PermissionState
import com.jarvisprime.notifications.platform.PresentationSpec

/**
 * Top-level orchestrator that takes an incoming [NotificationEvent] from the
 * Jarvis Prime gateway and decides what — if anything — to surface to the user.
 *
 * Order of checks:
 *  1. EMERGENCY_STOP_ACTIVE is always presented (subject to OS permission).
 *  2. Master toggle and per-type toggle must allow the type.
 *  3. The spam guard must allow the event.
 *  4. OS permission must be GRANTED. If DENIED, we route to an in-app banner
 *     fallback handled by the caller via [DispatchResult.InAppFallback].
 */
class NotificationDispatcher(
    private val mapper: NotificationEventMapper,
    private val settingsStore: NotificationSettingsStore,
    private val permissionGate: PermissionGate,
    private val spamGuard: NotificationSpamGuard,
    private val presenter: NotificationPresenter,
) {

    fun onEvent(event: NotificationEvent): DispatchResult {
        val settings = settingsStore.load()
        if (!settings.isAllowed(event.type)) {
            return DispatchResult.SuppressedByUser(event.type)
        }
        if (!spamGuard.allow(event)) {
            return DispatchResult.SuppressedAsDuplicate(event.id)
        }
        when (permissionGate.currentState()) {
            PermissionState.GRANTED -> Unit
            PermissionState.DENIED,
            PermissionState.NOT_DETERMINED -> return DispatchResult.InAppFallback(
                event,
                mapper.target(event.type),
            )
        }
        val spec = PresentationSpec(
            event = event,
            channelId = mapper.channelId(event.type),
            priority = mapper.priority(event.type),
            actions = mapper.actions(event.type),
            target = mapper.target(event.type),
        )
        presenter.present(spec)
        return DispatchResult.Presented(spec)
    }
}

sealed class DispatchResult {
    data class Presented(val spec: PresentationSpec) : DispatchResult()
    data class SuppressedByUser(val type: NotificationType) : DispatchResult()
    data class SuppressedAsDuplicate(val eventId: String) : DispatchResult()
    data class InAppFallback(
        val event: NotificationEvent,
        val target: com.jarvisprime.notifications.platform.NavigationTarget,
    ) : DispatchResult()
}
