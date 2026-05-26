package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.Clock
import com.jarvisprime.notifications.platform.EmergencyStopController
import com.jarvisprime.notifications.platform.EmergencyStopResult
import com.jarvisprime.notifications.platform.NavigationTarget
import com.jarvisprime.notifications.platform.Navigator
import com.jarvisprime.notifications.platform.NotificationPresenter
import com.jarvisprime.notifications.platform.PermissionGate
import com.jarvisprime.notifications.platform.PermissionState
import com.jarvisprime.notifications.platform.PresentationSpec

class FakeClock(var now: Long = 0L) : Clock {
    override fun nowMillis(): Long = now
    fun advance(ms: Long) {
        now += ms
    }
}

class FakeNavigator : Navigator {
    val calls = mutableListOf<Pair<NavigationTarget, NotificationEvent?>>()
    override fun navigateTo(target: NavigationTarget, event: NotificationEvent?) {
        calls.add(target to event)
    }
}

class FakePermissionGate(
    var state: PermissionState = PermissionState.NOT_DETERMINED,
    private val onRequest: (FakePermissionGate, (PermissionState) -> Unit) -> Unit = { gate, cb ->
        cb(gate.state)
    },
) : PermissionGate {
    var requestCount = 0
    override fun currentState(): PermissionState = state
    override fun requestPermission(onResult: (PermissionState) -> Unit) {
        requestCount += 1
        onRequest(this, onResult)
    }
}

class FakeEmergencyStop(
    private var active: Boolean = false,
    private val outcome: EmergencyStopResult = EmergencyStopResult.Triggered,
) : EmergencyStopController {
    val triggers = mutableListOf<String>()
    override fun isActive(): Boolean = active
    override fun trigger(reason: String): EmergencyStopResult {
        triggers.add(reason)
        return if (active) EmergencyStopResult.AlreadyActive else {
            active = true
            outcome
        }
    }
}

class RecordingPresenter : NotificationPresenter {
    val presented = mutableListOf<PresentationSpec>()
    val cancelled = mutableListOf<String>()
    override fun present(spec: PresentationSpec) {
        presented.add(spec)
    }
    override fun cancel(id: String) {
        cancelled.add(id)
    }
}

fun event(
    type: NotificationType,
    id: String = "evt-${type.name}",
    payload: Map<String, String> = emptyMap(),
) = NotificationEvent(
    id = id,
    type = type,
    title = "title for $type",
    body = "body for $type",
    payload = payload,
    timestamp = 0L,
)
