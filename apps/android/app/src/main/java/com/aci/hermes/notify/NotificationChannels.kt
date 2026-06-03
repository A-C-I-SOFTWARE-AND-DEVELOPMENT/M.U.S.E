package com.aci.hermes.notify

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

/**
 * Central registry for the event-notification channels JARVIS uses to report
 * long-running work. The three *ongoing* foreground-service channels
 * (`hermes_orchestrator`, `jarvis_voice`, and the overlay presence channel)
 * stay owned by their services — this registry adds the event channels that
 * carry transient, user-actionable updates.
 *
 * [specs] is plain data (no Android types) so the channel set can be asserted
 * in a pure JVM unit test; [register] maps it onto the platform once, idempotently.
 */
object NotificationChannels {

    const val JOBS = "jarvis_jobs"
    const val APPROVALS = "jarvis_approvals"
    const val ALERTS = "jarvis_alerts"

    /** Importance, kept Android-free so [specs] stays unit-testable. */
    enum class Importance { LOW, DEFAULT, HIGH }

    data class ChannelSpec(
        val id: String,
        val name: String,
        val description: String,
        val importance: Importance,
    )

    val specs: List<ChannelSpec> = listOf(
        ChannelSpec(
            JOBS,
            "Job updates",
            "Jobs starting and completing, and research finishing.",
            Importance.DEFAULT,
        ),
        ChannelSpec(
            APPROVALS,
            "Approvals needed",
            "Work paused waiting for your approval.",
            Importance.HIGH,
        ),
        ChannelSpec(
            ALERTS,
            "Alerts",
            "Failures, failing tests, workers needing attention, and emergency stop.",
            Importance.HIGH,
        ),
    )

    /** The channel an event belongs to. */
    fun channelFor(event: WorkEvent): String = when (event) {
        is WorkEvent.JobStarted,
        is WorkEvent.JobCompleted,
        is WorkEvent.ResearchComplete,
        -> JOBS

        is WorkEvent.JobBlocked,
        is WorkEvent.ApprovalRequired,
        -> APPROVALS

        is WorkEvent.JobFailed,
        is WorkEvent.TestsFailed,
        is WorkEvent.WorkerNeedsAttention,
        is WorkEvent.EmergencyStopTriggered,
        -> ALERTS
    }

    /** Create any missing channels. Safe to call repeatedly. */
    fun register(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        for (spec in specs) {
            if (manager.getNotificationChannel(spec.id) != null) continue
            manager.createNotificationChannel(
                NotificationChannel(spec.id, spec.name, spec.importance.toPlatform()).apply {
                    description = spec.description
                },
            )
        }
    }

    private fun Importance.toPlatform(): Int = when (this) {
        Importance.LOW -> NotificationManager.IMPORTANCE_LOW
        Importance.DEFAULT -> NotificationManager.IMPORTANCE_DEFAULT
        Importance.HIGH -> NotificationManager.IMPORTANCE_HIGH
    }
}
