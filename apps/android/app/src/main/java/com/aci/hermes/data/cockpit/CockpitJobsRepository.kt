package com.aci.hermes.data.cockpit

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of the jobs list against the cockpit gateway. */
sealed interface JobsSync {
    data object Idle : JobsSync
    data object Loading : JobsSync
    /** No gateway paired — there is nothing real to show (no fake jobs). */
    data object NotPaired : JobsSync
    data class Loaded(val count: Int) : JobsSync
    data class Error(val message: String) : JobsSync
}

/**
 * Repository over the canonical cockpit Jobs API (contract §4): list,
 * dispatch, cancel, get — backed by the real `JobQueue` through
 * [HermesCockpitClient]. There is **no mock seed**: an unpaired or
 * unreachable gateway yields an empty list + an honest [sync] state, never
 * fabricated jobs.
 */
class CockpitJobsRepository(
    private val client: HermesCockpitClient,
) {
    private val _jobs = MutableStateFlow<List<CockpitJob>>(emptyList())
    val jobs: StateFlow<List<CockpitJob>> = _jobs.asStateFlow()

    private val _sync = MutableStateFlow<JobsSync>(JobsSync.Idle)
    val sync: StateFlow<JobsSync> = _sync.asStateFlow()

    suspend fun refresh() {
        if (!client.isPaired()) {
            _jobs.value = emptyList()
            _sync.value = JobsSync.NotPaired
            return
        }
        _sync.value = JobsSync.Loading
        when (val res = client.jobsList()) {
            is CockpitResult.Success -> {
                _jobs.value = res.value.jobs
                _sync.value = JobsSync.Loaded(res.value.jobs.size)
            }
            is CockpitResult.Failure ->
                _sync.value = JobsSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = JobsSync.Error(res.message)
        }
    }

    /** Dispatch a new job; refreshes the list on success. */
    suspend fun dispatch(
        title: String,
        workerId: String,
        prompt: String,
        workspacePath: String? = null,
        branchHint: String? = null,
    ): CockpitResult<CockpitJob> {
        val res = client.jobDispatch(
            DispatchJobRequest(
                title = title,
                workerId = workerId,
                prompt = prompt,
                workspacePath = workspacePath,
                branchHint = branchHint,
            ),
        )
        if (res is CockpitResult.Success) refresh()
        return res
    }

    /** Cancel a job; refreshes the list on success. */
    suspend fun cancel(id: String, reason: String? = null): CockpitResult<CockpitJob> {
        val res = client.jobCancel(id, reason)
        if (res is CockpitResult.Success) refresh()
        return res
    }

    suspend fun get(id: String): CockpitResult<CockpitJob> = client.jobGet(id)
}
