package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.JobLane
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Backend orchestration jobs (cockpit contract §4) for the Tasks tab.
 *
 * Wraps the already-tested [CockpitJobsRepository] — the real orchestrator
 * jobs through the cockpit gateway — and the **runnable** worker lanes used by
 * the dispatch/run picker. There is **no mock**: an unpaired/unreachable
 * gateway yields an empty list + an honest [JobsSync] state, never fabricated
 * jobs.
 *
 * The owner gate is preserved end-to-end: each [JobLane] carries
 * `requiresApproval` (from the gateway), so the UI prompts for the exact owner
 * phrase before running an execute lane, and the gateway re-checks the phrase
 * server-side (refusing on a non-loopback cockpit). The gate is never bypassed.
 *
 * "New backend job" creates a runnable **orchestrator** job ([orchestrate]) —
 * not a JobQueue entry — so a job created here can actually be [run]; only such
 * orchestrator jobs (`orc-` ids) expose Run, since `job_run` operates on them.
 */
data class CockpitJobsUiState(
    val jobs: List<CockpitJob> = emptyList(),
    val sync: JobsSync = JobsSync.Idle,
    val lanes: List<JobLane> = emptyList(),
    val snackbar: String? = null,
)

class CockpitJobsViewModel(
    private val repo: CockpitJobsRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _ui = MutableStateFlow(CockpitJobsUiState())
    val ui: StateFlow<CockpitJobsUiState> = _ui.asStateFlow()

    init {
        viewModelScope.launch {
            combine(repo.jobs, repo.sync) { jobs, sync -> jobs to sync }
                .collect { (jobs, sync) -> _ui.update { it.copy(jobs = jobs, sync = sync) } }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            repo.refresh()
            when (val l = repo.lanes()) {
                is CockpitResult.Success -> _ui.update { it.copy(lanes = l.value.lanes) }
                else -> Unit // keep the last-known lanes; jobs sync carries the error
            }
        }
    }

    /** Create a runnable orchestrator job from a goal/prompt. */
    fun dispatch(prompt: String) {
        if (prompt.isBlank()) {
            _ui.update { it.copy(snackbar = "A goal / prompt is required") }
            return
        }
        viewModelScope.launch {
            when (val res = repo.orchestrate(prompt.trim())) {
                is CockpitResult.Success -> {
                    logBuffer.info(TAG, "Created orchestrator job ${res.value.id}")
                    _ui.update { it.copy(snackbar = "Created: ${res.value.title}") }
                }
                is CockpitResult.Failure ->
                    _ui.update { it.copy(snackbar = "Create failed: ${res.error.message}") }
                is CockpitResult.Unreachable ->
                    _ui.update { it.copy(snackbar = res.message) }
            }
        }
    }

    /**
     * Run a job on [workerId]. [authorization] must be the exact owner phrase
     * for an execute lane; the gateway enforces it. A `403` surfaces the
     * gateway's hint (e.g. the required phrase) so the owner can correct it.
     */
    fun run(id: String, workerId: String, authorization: String? = null) {
        viewModelScope.launch {
            when (val res = repo.run(id, workerId, authorization)) {
                is CockpitResult.Success -> {
                    val status = res.value.job?.status?.let { " ($it)" } ?: ""
                    logBuffer.info(TAG, "Ran job $id on $workerId$status")
                    _ui.update { it.copy(snackbar = "Running on $workerId$status") }
                }
                is CockpitResult.Failure -> {
                    val hint = res.error.details?.get("hint")
                    val msg = res.error.message + (hint?.let { " — $it" } ?: "")
                    _ui.update { it.copy(snackbar = msg) }
                }
                is CockpitResult.Unreachable ->
                    _ui.update { it.copy(snackbar = res.message) }
            }
        }
    }

    fun cancel(id: String, reason: String? = null) {
        viewModelScope.launch {
            when (val res = repo.cancel(id, reason)) {
                is CockpitResult.Success -> _ui.update { it.copy(snackbar = "Cancelled") }
                is CockpitResult.Failure ->
                    _ui.update { it.copy(snackbar = "Cancel failed: ${res.error.message}") }
                is CockpitResult.Unreachable ->
                    _ui.update { it.copy(snackbar = res.message) }
            }
        }
    }

    fun consumeSnackbar() {
        _ui.update { it.copy(snackbar = null) }
    }

    companion object {
        const val TAG = "JobsVm"

        /**
         * True when [lane] needs the owner phrase before [run]. Sourced from the
         * gateway's `requires_approval` (execute lanes True; planner/handoff
         * False) — null defaults to required (fail safe).
         */
        fun runRequiresAuthorization(lane: JobLane?): Boolean = lane?.requiresApproval ?: true

        /** Only orchestrator jobs (`orc-` ids) are runnable by `job_run`. */
        fun isRunnable(job: CockpitJob): Boolean = job.id.startsWith("orc-")
    }
}
