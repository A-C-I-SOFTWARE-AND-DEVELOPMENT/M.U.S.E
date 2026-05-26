package com.jarvisprime.notifications

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class NotificationSettingsTest {

    @Test
    fun `default settings allow every type`() {
        val s = NotificationSettings()
        for (type in NotificationType.entries) {
            assertTrue(s.isAllowed(type), "$type should be allowed by default")
        }
    }

    @Test
    fun `master toggle off suppresses all non-safety types`() {
        val s = NotificationSettings().withMaster(false)
        assertFalse(s.isAllowed(NotificationType.TASK_COMPLETE))
        assertFalse(s.isAllowed(NotificationType.WORKER_FAILED))
        assertTrue(s.isAllowed(NotificationType.EMERGENCY_STOP_ACTIVE))
    }

    @Test
    fun `emergency stop cannot be disabled`() {
        val s = NotificationSettings().withType(NotificationType.EMERGENCY_STOP_ACTIVE, enabled = false)
        assertTrue(s.isAllowed(NotificationType.EMERGENCY_STOP_ACTIVE))
    }

    @Test
    fun `per-type disable is honoured`() {
        val s = NotificationSettings().withType(NotificationType.MEMORY_CORRECTED, enabled = false)
        assertFalse(s.isAllowed(NotificationType.MEMORY_CORRECTED))
        assertTrue(s.isAllowed(NotificationType.TASK_COMPLETE))
    }
}
