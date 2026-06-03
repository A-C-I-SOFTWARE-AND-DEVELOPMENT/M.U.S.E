package com.aci.hermes.notify

import com.aci.hermes.data.cockpit.JobStatus

/**
 * A point-in-time view of everything the notification watcher cares about,
 * reduced to the minimum needed to diff. Built by [WorkWatcher] from the live
 * cockpit repositories, then handed to the pure [WorkEventDetector].
 *
 * Deliberately decoupled from the wire models ([com.aci.hermes.data.cockpit.CockpitJob],
 * [com.aci.hermes.approval.model.ApprovalCard], …) so the detector — and its
 * tests — stay tiny and free of serialization/Android concerns.
 */
data class WorkSnapshot(
    val jobs: List<JobSnap> = emptyList(),
    val approvalIds: Set<String> = emptySet(),
    val workers: List<WorkerSnap> = emptyList(),
    val emergencyActive: Boolean = false,
) {
    private val jobsById: Map<String, JobSnap> by lazy { jobs.associateBy { it.id } }

    fun job(id: String): JobSnap? = jobsById[id]
}

/** One job, reduced to the fields the detector branches on. */
data class JobSnap(
    val id: String,
    val title: String,
    val status: JobStatus?,
    /** `validation_summary.fail` (0 when absent). */
    val testsFailed: Int = 0,
    /** True when this job is a research run (vault heuristic — see detector). */
    val isResearch: Boolean = false,
)

/** One detected worker, reduced to availability. */
data class WorkerSnap(
    val id: String,
    val displayName: String,
    val available: Boolean,
)
