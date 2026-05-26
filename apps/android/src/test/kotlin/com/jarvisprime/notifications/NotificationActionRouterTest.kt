package com.jarvisprime.notifications

import com.jarvisprime.notifications.NotificationActionRouter.EmergencyStopConfirmation
import com.jarvisprime.notifications.platform.EmergencyStopResult
import com.jarvisprime.notifications.platform.NavigationTarget
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class NotificationActionRouterTest {

    private val mapper = NotificationEventMapper()

    private fun router(
        confirmation: EmergencyStopConfirmation = EmergencyStopConfirmation.RequireExplicit,
    ): Quad {
        val navigator = FakeNavigator()
        val stop = FakeEmergencyStop()
        val presenter = RecordingPresenter()
        return Quad(
            NotificationActionRouter(mapper, navigator, stop, presenter, confirmation),
            navigator,
            stop,
            presenter,
        )
    }

    data class Quad(
        val router: NotificationActionRouter,
        val navigator: FakeNavigator,
        val stop: FakeEmergencyStop,
        val presenter: RecordingPresenter,
    )

    @Test
    fun `open approval routes to approvals screen`() {
        val (r, navigator, _, presenter) = router()
        val evt = event(NotificationType.APPROVAL_NEEDED)
        val result = r.handle(NotificationAction.OPEN_APPROVAL, evt)

        assertIs<RouteResult.Navigated>(result)
        assertEquals(NavigationTarget.APPROVALS, result.target)
        assertEquals(NavigationTarget.APPROVALS, navigator.calls.single().first)
        assertEquals(evt.id, presenter.cancelled.single())
    }

    @Test
    fun `open task routes to tasks screen`() {
        val (r, navigator, _, _) = router()
        val evt = event(NotificationType.TASK_COMPLETE)
        val result = r.handle(NotificationAction.OPEN_TASK, evt)

        assertIs<RouteResult.Navigated>(result)
        assertEquals(NavigationTarget.TASKS, result.target)
        assertEquals(NavigationTarget.TASKS, navigator.calls.single().first)
    }

    @Test
    fun `emergency stop requires explicit confirmation before triggering`() {
        val (r, navigator, stop, presenter) = router(EmergencyStopConfirmation.RequireExplicit)
        val evt = event(NotificationType.CRITICAL_ACTION_PENDING)

        val first = r.handle(NotificationAction.EMERGENCY_STOP, evt)
        assertIs<RouteResult.NeedsConfirmation>(first)
        assertTrue(stop.triggers.isEmpty(), "tap alone must not fire the stop")
        assertEquals(NavigationTarget.EMERGENCY_STOP, navigator.calls.single().first)
        assertTrue(presenter.cancelled.isEmpty(), "shade entry stays until confirmed")

        val confirmed = r.confirmEmergencyStop(evt, reason = "owner-confirmed")
        assertIs<RouteResult.EmergencyStop>(confirmed)
        assertEquals(EmergencyStopResult.Triggered, confirmed.outcome)
        assertEquals(listOf("owner-confirmed"), stop.triggers)
        assertEquals(evt.id, presenter.cancelled.single())
    }

    @Test
    fun `dismiss cancels the notification and does not navigate`() {
        val (r, navigator, _, presenter) = router()
        val evt = event(NotificationType.MEMORY_CORRECTED)
        val result = r.handle(NotificationAction.DISMISS, evt)

        assertEquals(RouteResult.Dismissed, result)
        assertTrue(navigator.calls.isEmpty())
        assertEquals(evt.id, presenter.cancelled.single())
    }

    @Test
    fun `open audit routes every type that exposes it`() {
        val (r, navigator, _, _) = router()
        r.handle(NotificationAction.OPEN_AUDIT, event(NotificationType.GATEWAY_DISCONNECTED))
        assertEquals(NavigationTarget.AUDIT, navigator.calls.single().first)
    }
}
