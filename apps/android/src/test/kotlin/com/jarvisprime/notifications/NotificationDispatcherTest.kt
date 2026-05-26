package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.NavigationTarget
import com.jarvisprime.notifications.platform.PermissionState
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class NotificationDispatcherTest {

    private val mapper = NotificationEventMapper()

    private fun newDispatcher(
        clock: FakeClock = FakeClock(),
        permission: PermissionState = PermissionState.GRANTED,
        settings: NotificationSettings = NotificationSettings(),
    ): Quadruple {
        val store = InMemoryNotificationSettingsStore(settings)
        val gate = FakePermissionGate(permission)
        val presenter = RecordingPresenter()
        val guard = NotificationSpamGuard(clock, windowMillis = 1_000L)
        return Quadruple(
            NotificationDispatcher(mapper, store, gate, guard, presenter),
            store,
            presenter,
            guard,
        )
    }

    data class Quadruple(
        val dispatcher: NotificationDispatcher,
        val store: InMemoryNotificationSettingsStore,
        val presenter: RecordingPresenter,
        val guard: NotificationSpamGuard,
    )

    @Test
    fun `permission denied falls back to in-app banner instead of system notification`() {
        val (dispatcher, _, presenter, _) = newDispatcher(permission = PermissionState.DENIED)
        val result = dispatcher.onEvent(event(NotificationType.TASK_COMPLETE))

        assertIs<DispatchResult.InAppFallback>(result)
        assertEquals(NavigationTarget.TASKS, result.target)
        assertTrue(presenter.presented.isEmpty(), "no system notification should post when denied")
    }

    @Test
    fun `approval notification routes to approvals screen target`() {
        val (dispatcher, _, presenter, _) = newDispatcher()
        val result = dispatcher.onEvent(event(NotificationType.APPROVAL_NEEDED))

        assertIs<DispatchResult.Presented>(result)
        assertEquals(NavigationTarget.APPROVALS, result.spec.target)
        assertEquals(1, presenter.presented.size)
        assertTrue(NotificationAction.OPEN_APPROVAL in result.spec.actions)
    }

    @Test
    fun `task notification routes to tasks screen target`() {
        val (dispatcher, _, presenter, _) = newDispatcher()
        val result = dispatcher.onEvent(event(NotificationType.TASK_COMPLETE))

        assertIs<DispatchResult.Presented>(result)
        assertEquals(NavigationTarget.TASKS, result.spec.target)
        assertEquals(NotificationEventMapper.CHANNEL_TASKS, result.spec.channelId)
        assertTrue(NotificationAction.OPEN_TASK in presenter.presented.single().actions)
    }

    @Test
    fun `duplicate events inside the spam window are suppressed`() {
        val clock = FakeClock(0L)
        val (dispatcher, _, presenter, _) = newDispatcher(clock = clock)

        dispatcher.onEvent(event(NotificationType.TASK_COMPLETE, id = "task-1"))
        val second = dispatcher.onEvent(event(NotificationType.TASK_COMPLETE, id = "task-1"))

        assertIs<DispatchResult.SuppressedAsDuplicate>(second)
        assertEquals(1, presenter.presented.size, "only one notification should reach the presenter")
    }

    @Test
    fun `events after the spam window are presented again`() {
        val clock = FakeClock(0L)
        val (dispatcher, _, presenter, _) = newDispatcher(clock = clock)

        dispatcher.onEvent(event(NotificationType.TASK_COMPLETE, id = "task-1"))
        clock.advance(1_500L)
        val second = dispatcher.onEvent(event(NotificationType.TASK_COMPLETE, id = "task-1"))

        assertIs<DispatchResult.Presented>(second)
        assertEquals(2, presenter.presented.size)
    }

    @Test
    fun `disabling a type via settings suppresses dispatch`() {
        val (dispatcher, store, presenter, _) = newDispatcher()
        store.save(
            NotificationSettings().withType(NotificationType.MEMORY_CORRECTED, enabled = false),
        )

        val result = dispatcher.onEvent(event(NotificationType.MEMORY_CORRECTED))
        assertIs<DispatchResult.SuppressedByUser>(result)
        assertTrue(presenter.presented.isEmpty())
    }

    @Test
    fun `emergency stop always presents even when master toggle is off`() {
        val (dispatcher, store, presenter, _) = newDispatcher()
        store.save(NotificationSettings().withMaster(false))

        val result = dispatcher.onEvent(event(NotificationType.EMERGENCY_STOP_ACTIVE))
        assertIs<DispatchResult.Presented>(result)
        assertEquals(1, presenter.presented.size)
    }
}
