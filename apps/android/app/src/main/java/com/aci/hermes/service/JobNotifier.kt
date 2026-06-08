package com.aci.hermes.service

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.aci.hermes.MainActivity
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.ui.components.JobUiState

/**
 * Foreground-persistent notifications for active, owner-started jobs.
 *
 * The Hermes foreground service already holds the process at foreground
 * priority, so a long-running job survives the app being backgrounded; this
 * notifier keeps a per-job notification visible (and tappable) the whole time
 * so the owner can jump straight back into the exact Job Detail — or the
 * Approvals queue when the job is blocked on an owner gate.
 *
 * Owner-started only: we notify for jobs the user dispatched/approved (active
 * or attention-needing states), never for terminal jobs, and we clear a
 * notification the moment a job leaves the active set. Posting is permission-
 * safe: a denied POST_NOTIFICATIONS just no-ops rather than crashing.
 */
class JobNotifier(private val context: Context) {

    private val tracked = mutableSetOf<String>()

    /**
     * Reconcile the visible notifications against the current job list. Posts/
     * updates a notification for each active or attention-needing job and
     * cancels notifications for jobs that have gone terminal or disappeared.
     */
    // Lint can't see that posting is gated on canPostNotifications() below;
    // that explicit POST_NOTIFICATIONS check is the real guard, and the
    // runCatching keeps any late SecurityException from crashing.
    @SuppressLint("MissingPermission")
    fun sync(jobs: List<CockpitJob>) {
        ensureChannel()
        val manager = NotificationManagerCompat.from(context)
        val live = jobs.filter { shouldNotify(it) }
        val liveIds = live.map { it.id }.toSet()

        (tracked - liveIds).forEach { id ->
            runCatching { manager.cancel(notificationId(id)) }
        }
        if (canPostNotifications()) {
            live.forEach { job ->
                runCatching { manager.notify(notificationId(job.id), build(job)) }
            }
        }
        tracked.clear()
        tracked.addAll(liveIds)
    }

    /** True when notifications can be posted (auto-granted below API 33). */
    private fun canPostNotifications(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    /** Drop every job notification (e.g. on unpair / emergency stop). */
    fun clearAll() {
        val manager = NotificationManagerCompat.from(context)
        tracked.forEach { id -> runCatching { manager.cancel(notificationId(id)) } }
        tracked.clear()
    }

    private fun shouldNotify(job: CockpitJob): Boolean {
        val state = JobUiState.from(JobStatus.fromWire(job.status))
        return state.isActive || state.needsAttention
    }

    private fun build(job: CockpitJob): android.app.Notification {
        val state = JobUiState.from(JobStatus.fromWire(job.status))
        val dest = destinationFor(job.status)
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(EXTRA_JOB_ID, job.id)
            putExtra(EXTRA_DEST, dest)
        }
        val pending = PendingIntent.getActivity(
            context,
            notificationId(job.id),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(job.title)
            .setContentText(state.label)
            .setContentIntent(pending)
            .setOnlyAlertOnce(true)
            .setOngoing(state.isActive)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun ensureChannel() {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_LOW).apply {
                description = "Progress for running MUSE jobs"
                setShowBadge(false)
            },
        )
    }

    /** Stable, collision-resistant per-job notification id (kept away from #1001). */
    private fun notificationId(jobId: String): Int = NOTIFICATION_BASE + (jobId.hashCode() and 0xFFFF)

    companion object {
        const val CHANNEL_ID = "hermes_jobs"
        private const val CHANNEL_NAME = "MUSE jobs"
        private const val NOTIFICATION_BASE = 2_000

        const val EXTRA_JOB_ID = "hermes_job_id"
        const val EXTRA_DEST = "hermes_jobs_dest"
        const val DEST_DETAIL = "detail"
        const val DEST_APPROVALS = "approvals"
        const val DEST_DIAGNOSTICS = "diagnostics"

        /**
         * The deep-link destination for a job's notification: always that
         * job's own Job Detail — including when it's blocked on an owner gate,
         * because the job-phase approve control (POST /jobs/{id}/approve) lives
         * on Job Detail. The Approvals tab is the separate JARVIS *proposal*
         * queue (/v1/cockpit/approvals); it carries no job-id context and can't
         * approve a job phase, so routing a blocked job there is a dead end.
         * Takes [status] so callers can pass it uniformly; pure and
         * unit-testable without an Android [Intent].
         */
        @Suppress("UNUSED_PARAMETER")
        fun destinationFor(status: String?): String = DEST_DETAIL

        /** Parse a launch intent into a [DeepLink], or null when it carries none. */
        fun parseDeepLink(intent: Intent?): DeepLink? {
            val dest = intent?.getStringExtra(EXTRA_DEST) ?: return null
            return DeepLink(jobId = intent.getStringExtra(EXTRA_JOB_ID), destination = dest)
        }
    }

    /**
     * A notification deep-link target parsed from a launch [Intent]. Declared
     * directly on [JobNotifier] (not inside the companion) so callers reference
     * it as `JobNotifier.DeepLink`.
     */
    data class DeepLink(val jobId: String?, val destination: String)
}
