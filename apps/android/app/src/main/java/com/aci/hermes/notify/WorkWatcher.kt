package com.aci.hermes.notify

import com.aci.hermes.approval.state.CockpitApprovalsRepository
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.JobStatus
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Polls the live cockpit repositories, diffs against the previous snapshot
 * with the pure [WorkEventDetector], and posts any resulting [WorkEvent]s.
 *
 * Statefulness is limited to one field — [previous] — guarded by a [Mutex] so
 * the in-app foreground poller and the [com.aci.hermes.service.WorkWatchService]
 * background loop can share a single instance without racing. (Stable event
 * keys make any overlap idempotent in the shade anyway.)
 *
 * The watcher itself is transport-only: it owns no timers. Cadence, backoff,
 * and lifetime are the caller's job — honouring "poll only while there is
 * active work, never a permanent always-on poller."
 */
class WorkWatcher(
    private val jobsRepo: CockpitJobsRepository,
    private val approvalsRepo: CockpitApprovalsRepository,
    private val client: HermesCockpitClient,
    private val notifier: WorkNotifier,
    /** Live emergency-stop state (engaged = true). */
    private val emergencyActive: () -> Boolean,
    /** Owner's notification preference; ticks still run, posting is gated. */
    private val notificationsEnabled: suspend () -> Boolean,
) {

    private val mutex = Mutex()

    @Volatile
    private var previous: WorkSnapshot? = null

    data class TickResult(
        val hasActiveWork: Boolean,
        val error: Boolean = false,
    )

    /**
     * Refresh the world once, emit transitions, and report whether active work
     * remains (so the caller can decide to keep polling or stand down).
     */
    suspend fun tick(): TickResult = mutex.withLock {
        if (!client.isPaired()) {
            // Nothing real to watch; drop the baseline so re-pairing starts fresh.
            previous = null
            return TickResult(hasActiveWork = false)
        }

        val snapshot = runCatching { buildSnapshot() }.getOrElse {
            return TickResult(hasActiveWork = previous?.let(WorkEventDetector::hasActiveWork) ?: false, error = true)
        }

        val events = WorkEventDetector.detect(previous, snapshot)
        previous = snapshot

        if (events.isNotEmpty() && notificationsEnabled()) {
            events.forEach(notifier::post)
        }

        TickResult(hasActiveWork = WorkEventDetector.hasActiveWork(snapshot))
    }

    /** Reset the baseline (e.g. on unpair) so the next tick re-establishes it. */
    suspend fun reset() = mutex.withLock { previous = null }

    private suspend fun buildSnapshot(): WorkSnapshot {
        jobsRepo.refresh()
        approvalsRepo.refresh()
        val workers = when (val r = client.runtimeWorkers()) {
            is CockpitResult.Success -> r.value.workers.map {
                WorkerSnap(id = it.id, displayName = it.displayName, available = it.available)
            }
            else -> emptyList()
        }
        return WorkSnapshot(
            jobs = jobsRepo.jobs.value.map { it.toSnap() },
            approvalIds = approvalsRepo.cards.value.map { it.id }.toSet(),
            workers = workers,
            emergencyActive = emergencyActive(),
        )
    }

    companion object {
        /** A job is a research run if its worker or title says so (vault heuristic). */
        fun isResearch(job: CockpitJob): Boolean =
            job.workerId.contains("research", ignoreCase = true) ||
                job.title.contains("research", ignoreCase = true)

        private fun CockpitJob.toSnap(): JobSnap = JobSnap(
            id = id,
            title = title,
            status = JobStatus.fromWire(status),
            testsFailed = validationSummary?.fail ?: 0,
            isResearch = isResearch(this),
        )
    }
}
