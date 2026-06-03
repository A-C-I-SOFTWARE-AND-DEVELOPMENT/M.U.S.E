package com.aci.hermes.notify

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure assertions over the channel registry data. The `register`/platform
 * path needs Android and is exercised on-device; here we lock the channel set
 * and the event→channel routing so a new event can't silently land on no
 * channel.
 */
class NotificationChannelsTest {

    @Test
    fun `three event channels are defined with sane importance`() {
        val ids = NotificationChannels.specs.map { it.id }.toSet()
        assertEquals(
            setOf(
                NotificationChannels.JOBS,
                NotificationChannels.APPROVALS,
                NotificationChannels.ALERTS,
            ),
            ids,
        )
        // Approvals + alerts must be HIGH so they surface promptly.
        val byId = NotificationChannels.specs.associateBy { it.id }
        assertEquals(NotificationChannels.Importance.HIGH, byId.getValue(NotificationChannels.APPROVALS).importance)
        assertEquals(NotificationChannels.Importance.HIGH, byId.getValue(NotificationChannels.ALERTS).importance)
        assertEquals(NotificationChannels.Importance.DEFAULT, byId.getValue(NotificationChannels.JOBS).importance)
    }

    @Test
    fun `every event maps to a defined channel`() {
        val defined = NotificationChannels.specs.map { it.id }.toSet()
        val events = listOf(
            WorkEvent.JobStarted("j", ""),
            WorkEvent.JobBlocked("j", ""),
            WorkEvent.ApprovalRequired("a", ""),
            WorkEvent.JobCompleted("j", ""),
            WorkEvent.JobFailed("j", ""),
            WorkEvent.WorkerNeedsAttention("w", ""),
            WorkEvent.ResearchComplete("j", ""),
            WorkEvent.TestsFailed("j", "", 1),
            WorkEvent.EmergencyStopTriggered(""),
        )
        events.forEach { assertTrue(NotificationChannels.channelFor(it) in defined) }
    }

    @Test
    fun `approvals route to the approvals channel, alerts to alerts`() {
        assertEquals(NotificationChannels.APPROVALS, NotificationChannels.channelFor(WorkEvent.JobBlocked("j", "")))
        assertEquals(NotificationChannels.APPROVALS, NotificationChannels.channelFor(WorkEvent.ApprovalRequired("a", "")))
        assertEquals(NotificationChannels.ALERTS, NotificationChannels.channelFor(WorkEvent.JobFailed("j", "")))
        assertEquals(NotificationChannels.ALERTS, NotificationChannels.channelFor(WorkEvent.EmergencyStopTriggered("")))
        assertEquals(NotificationChannels.JOBS, NotificationChannels.channelFor(WorkEvent.JobCompleted("j", "")))
    }
}
