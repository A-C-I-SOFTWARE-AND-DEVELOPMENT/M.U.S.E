package com.aci.hermes.workers

import com.aci.hermes.data.cockpit.DetectedWorker

/**
 * Jarvis Prime Worker Execution Lane.
 *
 * Workers/tools run outside the UI process — Jarvis Prime never
 * executes destructive actions itself. This data class aggregates one
 * worker's state for the Operations screen and surfaces a single
 * [Health] indicator so the UI can collapse the worker list down to a
 * row of colored dots when space is tight.
 */
data class WorkerLane(
    val id: String,
    val displayName: String,
    val kind: String,
    val available: Boolean,
    val version: String? = null,
    val notes: String? = null,
    val runningJobs: Int = 0,
    val queuedJobs: Int = 0,
) {
    val health: Health
        get() = when {
            !available -> Health.OFFLINE
            runningJobs > 0 -> Health.WORKING
            queuedJobs > 0 -> Health.QUEUED
            else -> Health.IDLE
        }

    enum class Health { OFFLINE, IDLE, QUEUED, WORKING }

    companion object {
        fun fromDetected(worker: DetectedWorker, runningJobs: Int = 0, queuedJobs: Int = 0): WorkerLane =
            WorkerLane(
                id = worker.id,
                displayName = worker.displayName,
                kind = worker.kind,
                available = worker.available,
                version = worker.version,
                notes = worker.notes,
                runningJobs = runningJobs,
                queuedJobs = queuedJobs,
            )
    }
}
