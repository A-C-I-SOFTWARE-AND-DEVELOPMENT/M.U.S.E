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
    suspend fun cancel(id: String, reason: String? = null): CockpitResult<CockpitJob> =
        mutating { client.jobCancel(id, reason) }

    /** Pause a running/queued job; refreshes on success. */
    suspend fun pause(id: String, reason: String? = null): CockpitResult<CockpitJob> =
        mutating { client.jobPause(id, reason) }

    /** Resume a paused/blocked job — the unblock action; refreshes on success. */
    suspend fun resume(id: String, reason: String? = null): CockpitResult<CockpitJob> =
        mutating { client.jobResume(id, reason) }

    /** Rerun a failed/blocked worker; refreshes on success. */
    suspend fun rerun(id: String, workerId: String? = null): CockpitResult<CockpitJob> =
        mutating { client.jobRerun(id, workerId) }

    /** Approve a gated phase (owner phrase required); refreshes on success. */
    suspend fun approve(
        id: String,
        phase: String = "execute",
        authorization: String? = null,
    ): CockpitResult<CockpitJob> = mutating { client.jobApprove(id, phase, authorization) }

    suspend fun get(id: String): CockpitResult<CockpitJob> = client.jobGet(id)

    /** Read-only detail + ledger timeline for the Job Detail screen. */
    suspend fun detail(id: String): CockpitResult<JobDetail> = client.jobLedger(id)

    /** Working-tree diff ("open patch"). */
    suspend fun diff(id: String): CockpitResult<DiffSnapshot> = client.jobDiff(id)

    /** Run verification gates ("run verification"). */
    suspend fun validate(id: String): CockpitResult<ValidationSnapshot> = client.jobValidate(id)

    private suspend fun mutating(
        action: suspend () -> CockpitResult<CockpitJob>,
    ): CockpitResult<CockpitJob> {
        val res = action()
        if (res is CockpitResult.Success) refresh()
        return res
    }

    /**
     * Run a job on a worker. Execute lanes require the owner [authorization]
     * phrase (the gateway returns `403` otherwise); the gate is enforced
     * server-side and never bypassed here. Refreshes the list on success.
     */
    suspend fun run(
        id: String,
        workerId: String,
        authorization: String? = null,
    ): CockpitResult<RunJobResult> {
        val res = client.jobRun(id, workerId, authorization)
        if (res is CockpitResult.Success) refresh()
        return res
    }

    /** Detected worker lanes the gateway offers (informational; see [lanes]). */
    suspend fun workers(): CockpitResult<WorkerDetectionList> = client.runtimeWorkers()

    /** The **runnable** worker lanes `job_run` accepts (dispatch/run picker source). */
    suspend fun lanes(): CockpitResult<JobLaneList> = client.jobLanes()

    /**
     * Create a runnable orchestrator job from [prompt]; refreshes the list on
     * success. This is what the app's "new backend job" uses (so a created job
     * can then be run), unlike [dispatch] which enqueues a JobQueue entry.
     */
    suspend fun orchestrate(prompt: String): CockpitResult<CockpitJob> {
        val res = client.orchestrate(prompt)
        if (res is CockpitResult.Success) refresh()
        return res
    }
}
