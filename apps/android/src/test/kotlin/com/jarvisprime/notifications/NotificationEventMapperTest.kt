package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.NavigationTarget
import com.jarvisprime.notifications.platform.Priority
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class NotificationEventMapperTest {

    private val mapper = NotificationEventMapper()

    @Test
    fun `every notification type has a defined target`() {
        for (type in NotificationType.entries) {
            mapper.target(type)
        }
    }

    @Test
    fun `approval-class types share the approvals target and channel`() {
        val approvalTypes = listOf(
            NotificationType.APPROVAL_NEEDED,
            NotificationType.SERIOUS_ACTION_PENDING,
            NotificationType.CRITICAL_ACTION_PENDING,
        )
        for (type in approvalTypes) {
            assertEquals(NavigationTarget.APPROVALS, mapper.target(type))
            assertEquals(NotificationEventMapper.CHANNEL_APPROVALS, mapper.channelId(type))
        }
    }

    @Test
    fun `critical and emergency types are MAX priority`() {
        assertEquals(Priority.MAX, mapper.priority(NotificationType.CRITICAL_ACTION_PENDING))
        assertEquals(Priority.MAX, mapper.priority(NotificationType.EMERGENCY_STOP_ACTIVE))
    }

    @Test
    fun `only critical actions expose the emergency stop inline action`() {
        for (type in NotificationType.entries) {
            val hasStop = NotificationAction.EMERGENCY_STOP in mapper.actions(type)
            if (type == NotificationType.CRITICAL_ACTION_PENDING) {
                assertTrue(hasStop, "$type must offer emergency stop")
            } else {
                assertEquals(false, hasStop, "$type must not expose emergency stop inline")
            }
        }
    }
}
