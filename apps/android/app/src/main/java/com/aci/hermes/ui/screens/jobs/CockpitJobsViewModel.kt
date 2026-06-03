package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.DetectedWorker
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
 * Wraps the already-tested [CockpitJobsRepository] — the real `JobQueue`
 * through the cockpit gateway — and the detected worker lanes used by the
 * dispatch picker. There is **no mock**: an unpaired/unreachable gateway
 * yields an empty list + an honest [JobsSync] state, never fabricated jobs.
 *
 * The owner gate is preserved end-to-end: [runRequiresAuthorization] tells the
 * UI when a worker is an execute lane that needs the exact owner phrase, and
 * the gateway re-checks the phrase server-side (and refuses on a non-loopback
 * cockpit), so the gate is never bypassed from the app.
 */
data class JobsUiState(
    val jobs: List<CockpitJob> = emptyList(),
    val sync: JobsSync = JobsSync.Idle,
    val workers: List<DetectedWorker> = emptyList(),
    val snackbar: String? = null,
)

class CockpitJobsViewModel(
    private val repo: CockpitJobsRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _ui = MutableStateFlow(JobsUiState())
    val ui: StateFlow<JobsUiState> = _ui.asStateFlow()

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
            when (val w = repo.workers()) {
                is CockpitResult.Success ->
                    _ui.update { it.copy(workers = w.value.workers.filter { dw -> dw.available }) }
                else -> Unit // keep the last-known worker list; jobs sync carries the error
            }
        }
    }

    fun dispatch(title: String, prompt: String, workerId: String, workspacePath: String? = null) {
        if (title.isBlank() || prompt.isBlank()) {
            _ui.update { it.copy(snackbar = "Title and prompt are required") }
            return
        }
        viewModelScope.launch {
            when (val res = repo.dispatch(title, workerId, prompt, workspacePath)) {
                is CockpitResult.Success -> {
                    logBuffer.info(TAG, "Dispatched job ${res.value.id} (${res.value.title})")
                    _ui.update { it.copy(snackbar = "Queued: ${res.value.title}") }
                }
                is CockpitResult.Failure ->
                    _ui.update { it.copy(snackbar = "Dispatch failed: ${res.error.message}") }
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
         * True when [worker] is an execute lane — the UI must collect the owner
         * phrase before [run]. Detection is conservative: anything but the
         * read-only local planner / handoff lanes is treated as gated, matching
         * the server's `requires_approval` default of True.
         */
        fun runRequiresAuthorization(worker: DetectedWorker?): Boolean {
            val id = worker?.id?.lowercase().orEmpty()
            val nonGated = id.contains("planner") || id.contains("handoff")
            return !nonGated
        }
    }
}
