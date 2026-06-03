package com.aci.hermes.notify

/**
 * A user-facing signal that long-running JARVIS work changed state.
 *
 * Events are *pure data* — no Android, no strings.xml, no network. The
 * [WorkEventDetector] produces them by diffing two [WorkSnapshot]s; the
 * Android [JarvisNotifier] turns them into channel-routed notifications and
 * [DeepLink] maps each to the screen it should open.
 *
 * Every event carries a stable [key] so the notifier can use a deterministic
 * notification id — re-posting the same event collapses onto the existing
 * notification instead of stacking duplicates.
 *
 * [label] is the only free-form text and is always a short, structural value
 * (a job title or a worker name) — never a prompt, diff, token, or model
 * reasoning. The notifier still routes it through `SecretRedactor` before it
 * reaches the shade, so a title that accidentally embeds a secret is scrubbed.
 */
sealed interface WorkEvent {

    /** Stable identity for the notification id and for de-duplication. */
    val key: String

    /** Short structural label (job title / worker name). Redacted before display. */
    val label: String

    /** A job entered the queue or began running. */
    data class JobStarted(val jobId: String, override val label: String) : WorkEvent {
        override val key: String get() = "job_started:$jobId"
    }

    /** A job paused waiting on an owner decision. */
    data class JobBlocked(val jobId: String, override val label: String) : WorkEvent {
        override val key: String get() = "job_blocked:$jobId"
    }

    /** A new owner-approval card appeared in the queue. */
    data class ApprovalRequired(val approvalId: String, override val label: String) : WorkEvent {
        override val key: String get() = "approval:$approvalId"
    }

    /** A job reached a successful terminal state. */
    data class JobCompleted(val jobId: String, override val label: String) : WorkEvent {
        override val key: String get() = "job_completed:$jobId"
    }

    /** A job failed. */
    data class JobFailed(val jobId: String, override val label: String) : WorkEvent {
        override val key: String get() = "job_failed:$jobId"
    }

    /**
     * A worker (or a job's worker) needs attention — a detected worker went
     * unavailable, or a job disconnected / stalled. [attentionKey] keys the
     * notification (worker id or job id).
     */
    data class WorkerNeedsAttention(val attentionKey: String, override val label: String) : WorkEvent {
        override val key: String get() = "worker_attention:$attentionKey"
    }

    /** A research job finished (the research-vault heuristic; see detector). */
    data class ResearchComplete(val jobId: String, override val label: String) : WorkEvent {
        override val key: String get() = "research_complete:$jobId"
    }

    /** A job's validation gate reported failing tests. */
    data class TestsFailed(
        val jobId: String,
        override val label: String,
        val failures: Int,
    ) : WorkEvent {
        override val key: String get() = "tests_failed:$jobId"
    }

    /** The emergency stop went from inactive to engaged. */
    data class EmergencyStopTriggered(override val label: String) : WorkEvent {
        override val key: String get() = "emergency_stop"
    }
}
