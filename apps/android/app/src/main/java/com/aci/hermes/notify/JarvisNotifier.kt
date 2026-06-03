package com.aci.hermes.notify

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.aci.hermes.MainActivity
import com.aci.hermes.R
import com.aci.hermes.data.audit.SecretRedactor

/**
 * Posts [WorkEvent]s to the Android notification shade.
 *
 * Safety contract:
 *  - **Concise + structural text only.** Bodies are short and built from a
 *    job title or worker name — never a prompt, diff, token, or model
 *    reasoning. The label is still passed through [SecretRedactor] so a title
 *    that accidentally embeds a secret is scrubbed before display.
 *  - **Deterministic ids.** The notification id is the event [WorkEvent.key]'s
 *    hash, so re-posting the same logical event (e.g. emergency stop seen by
 *    both the immediate collector and the watcher tick) collapses onto one
 *    notification instead of stacking.
 *  - **Deep links, not actions.** Tapping opens the relevant screen via
 *    [DeepLink]; approvals open the owner-gated Approvals queue — this class
 *    never approves or executes anything.
 */
class JarvisNotifier(private val context: Context) : WorkNotifier {

    private val manager = NotificationManagerCompat.from(context)

    init {
        NotificationChannels.register(context)
    }

    // POST_NOTIFICATIONS is requested at app startup (MainActivity). Posting
    // is best-effort and wrapped in runCatching, so a denied permission drops
    // the notification rather than crashing.
    @SuppressLint("MissingPermission")
    override fun post(event: WorkEvent) {
        val label = SecretRedactor.redact(event.label)
        val title = context.getString(titleRes(event))
        val text = bodyText(event, label)
        val channel = NotificationChannels.channelFor(event)
        val id = event.key.hashCode()

        val builder = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(deepLinkIntent(event))

        if (event is WorkEvent.JobBlocked || event is WorkEvent.ApprovalRequired) {
            // Open the owner-gated Approvals queue — review, not one-tap approve.
            builder.addAction(
                0,
                context.getString(R.string.notify_action_review_approval),
                deepLinkIntent(event),
            )
        }

        runCatching { manager.notify(id, builder.build()) }
    }

    private fun deepLinkIntent(event: WorkEvent): PendingIntent {
        val route = DeepLink.routeFor(event)
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(DeepLink.EXTRA_NAV_ROUTE, route)
        }
        return PendingIntent.getActivity(
            context,
            event.key.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun titleRes(event: WorkEvent): Int = when (event) {
        is WorkEvent.JobStarted -> R.string.notify_job_started_title
        is WorkEvent.JobBlocked -> R.string.notify_job_blocked_title
        is WorkEvent.ApprovalRequired -> R.string.notify_approval_title
        is WorkEvent.JobCompleted -> R.string.notify_job_completed_title
        is WorkEvent.JobFailed -> R.string.notify_job_failed_title
        is WorkEvent.WorkerNeedsAttention -> R.string.notify_worker_title
        is WorkEvent.ResearchComplete -> R.string.notify_research_title
        is WorkEvent.TestsFailed -> R.string.notify_tests_failed_title
        is WorkEvent.EmergencyStopTriggered -> R.string.notify_emergency_title
    }

    private fun bodyText(event: WorkEvent, label: String): String = when (event) {
        is WorkEvent.JobStarted -> context.getString(R.string.notify_job_started_text, label)
        is WorkEvent.JobBlocked -> context.getString(R.string.notify_job_blocked_text, label)
        is WorkEvent.ApprovalRequired -> context.getString(R.string.notify_approval_text)
        is WorkEvent.JobCompleted -> context.getString(R.string.notify_job_completed_text, label)
        is WorkEvent.JobFailed -> context.getString(R.string.notify_job_failed_text, label)
        is WorkEvent.WorkerNeedsAttention -> context.getString(R.string.notify_worker_text, label)
        is WorkEvent.ResearchComplete -> context.getString(R.string.notify_research_text, label)
        is WorkEvent.TestsFailed ->
            context.resources.getQuantityString(
                R.plurals.notify_tests_failed_text,
                event.failures,
                label,
                event.failures,
            )
        is WorkEvent.EmergencyStopTriggered -> context.getString(R.string.notify_emergency_text)
    }
}
