package com.aci.hermes.notify

import com.aci.hermes.data.cockpit.JobStatus

/**
 * Pure diff engine: given the [previous] and [current] [WorkSnapshot]s,
 * returns the [WorkEvent]s that just happened. No Android, no I/O — mirrors
 * the `VoiceLoop` / `IconStateMapper` "decisions live in a testable unit,
 * effects live in the service" split used across this module.
 *
 * Design rules that keep notifications calm:
 *  - **Baseline first.** The caller seeds the very first snapshot with no
 *    events (pass `previous = null`); we only ever notify on a *transition*.
 *    Opening the app with a job already mid-flight does not spam the shade.
 *  - **Edge-triggered.** Each rule fires on a change (status moved, fail count
 *    crossed 0, worker flipped to unavailable, emergency engaged), never on a
 *    steady state — so re-polling an unchanged world yields nothing.
 */
object WorkEventDetector {

    /** Statuses that mean a job is finished and should never re-notify. */
    private val TERMINAL = setOf(
        JobStatus.COMPLETED, JobStatus.PUBLISHED, JobStatus.FAILED, JobStatus.CANCELLED,
    )

    private val BLOCKED = setOf(JobStatus.WAITING_FOR_APPROVAL, JobStatus.BLOCKED)
    private val SUCCESS = setOf(JobStatus.COMPLETED, JobStatus.PUBLISHED)
    private val NEEDS_ATTENTION = setOf(JobStatus.DISCONNECTED, JobStatus.PAUSED)

    fun detect(previous: WorkSnapshot?, current: WorkSnapshot): List<WorkEvent> {
        val events = mutableListOf<WorkEvent>()

        // Emergency stop: inactive -> engaged.
        if (current.emergencyActive && previous?.emergencyActive != true) {
            events += WorkEvent.EmergencyStopTriggered(label = "")
        }

        // Baseline tick: record state, emit nothing job/approval/worker-wise.
        if (previous == null) return events

        // ── Jobs ──────────────────────────────────────────────────────────
        for (job in current.jobs) {
            val before = previous.job(job.id)
            val prevStatus = before?.status
            val curStatus = job.status

            if (before == null) {
                // Newly observed job. Only "started" for live work — a job that
                // first appears already terminal is history, not an event.
                if (curStatus != null && curStatus !in TERMINAL) {
                    events += WorkEvent.JobStarted(job.id, job.title)
                }
            } else if (curStatus != null && curStatus != prevStatus && prevStatus !in TERMINAL) {
                when (curStatus) {
                    in BLOCKED -> events += WorkEvent.JobBlocked(job.id, job.title)
                    in SUCCESS ->
                        events += if (job.isResearch) {
                            WorkEvent.ResearchComplete(job.id, job.title)
                        } else {
                            WorkEvent.JobCompleted(job.id, job.title)
                        }
                    JobStatus.FAILED -> events += WorkEvent.JobFailed(job.id, job.title)
                    in NEEDS_ATTENTION ->
                        events += WorkEvent.WorkerNeedsAttention(job.id, job.title)
                    else -> Unit
                }
            }

            // Tests crossed from clean (or unknown) to failing.
            val failedBefore = before?.testsFailed ?: 0
            if (job.testsFailed > 0 && failedBefore == 0) {
                events += WorkEvent.TestsFailed(job.id, job.title, job.testsFailed)
            }
        }

        // ── Approvals: a card id we hadn't seen before ─────────────────────
        for (card in current.approvalIds) {
            if (card !in previous.approvalIds) {
                events += WorkEvent.ApprovalRequired(card, label = "")
            }
        }

        // ── Workers: available -> unavailable (or newly seen unavailable) ──
        val prevWorkers = previous.workers.associateBy { it.id }
        for (worker in current.workers) {
            if (worker.available) continue
            val wasAvailable = prevWorkers[worker.id]?.available ?: true
            if (wasAvailable) {
                events += WorkEvent.WorkerNeedsAttention(worker.id, worker.displayName)
            }
        }

        return events
    }

    /**
     * Whether there is active long-running work worth polling for. Drives the
     * foreground watcher's lifetime: when this is false the service may stand
     * down (no permanent always-on poller). Active = any non-terminal job or
     * any pending approval.
     */
    fun hasActiveWork(snapshot: WorkSnapshot): Boolean =
        snapshot.approvalIds.isNotEmpty() ||
            snapshot.jobs.any { it.status != null && it.status !in TERMINAL }
}
