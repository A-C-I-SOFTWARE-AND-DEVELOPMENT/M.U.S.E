package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.service.JobNotifier
import com.aci.hermes.ui.components.JobUiState
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** The five list sections the Jobs cockpit renders (contract §4 lifecycle). */
data class JobsUiState(
    val sync: JobsSync = JobsSync.Idle,
    val active: List<CockpitJob> = emptyList(),
    val blocked: List<CockpitJob> = emptyList(),
    val completed: List<CockpitJob> = emptyList(),
    val failed: List<CockpitJob> = emptyList(),
    val cancelled: List<CockpitJob> = emptyList(),
    val snackbar: String? = null,
) {
    val isEmpty: Boolean
        get() = active.isEmpty() && blocked.isEmpty() && completed.isEmpty() &&
            failed.isEmpty() && cancelled.isEmpty()

    val hasActiveWork: Boolean
        get() = active.isNotEmpty() || blocked.isNotEmpty()
}

/**
 * Drives the Jobs list off the real [CockpitJobsRepository] (no fake jobs).
 * Buckets jobs into the canonical sections, keeps owner-started jobs visible
 * via [JobNotifier], and polls with a lifecycle-aware back-off ([JobsPolling])
 * — fast while visible with active work, slower when idle, stopped when there
 * is nothing active and the screen is hidden.
 */
class JobsViewModel(
    private val repo: CockpitJobsRepository,
    private val notifier: JobNotifier? = null,
) : ViewModel() {

    private val _state = MutableStateFlow(JobsUiState())
    val state: StateFlow<JobsUiState> = _state.asStateFlow()

    private var pollJob: Job? = null
    private var visible = false

    init {
        viewModelScope.launch {
            combine(repo.jobs, repo.sync) { jobs, sync -> jobs to sync }.collect { (jobs, sync) ->
                _state.update { it.copy(sync = sync).withSections(jobs) }
                notifier?.sync(jobs)
            }
        }
    }

    /** Called when the Jobs screen enters/leaves the resumed state. */
    fun onVisibilityChanged(nowVisible: Boolean) {
        visible = nowVisible
        if (nowVisible) startPolling()
    }

    fun startPolling() {
        if (pollJob?.isActive == true) return
        pollJob = viewModelScope.launch {
            var consecutiveErrors = 0
            var idleCycles = 0
            while (isActive) {
                val ok = refreshOnce()
                val hasActive = _state.value.hasActiveWork
                consecutiveErrors = if (ok) 0 else consecutiveErrors + 1
                idleCycles = if (hasActive) 0 else idleCycles + 1
                val next = JobsPolling.nextDelayMs(hasActive, visible, consecutiveErrors, idleCycles)
                if (next == JobsPolling.STOP) break
                delay(next)
            }
        }
    }

    fun stopPolling() {
        pollJob?.cancel()
        pollJob = null
    }

    /** One refresh tick. Returns false on a sync error so the loop backs off. */
    private suspend fun refreshOnce(): Boolean {
        repo.refresh()
        return _state.value.sync !is JobsSync.Error
    }

    // ── controls ──────────────────────────────────────────────────────────

    fun pause(id: String) = control("Paused") { repo.pause(id) }
    fun resume(id: String) = control("Resumed") { repo.resume(id) }
    fun cancel(id: String) = control("Cancelled") { repo.cancel(id) }
    fun rerun(id: String) = control("Rerunning failed step") { repo.rerun(id) }

    /** Approve a gated phase. Requires the exact owner phrase (gateway-enforced). */
    fun approve(id: String, authorization: String, phase: String = "execute") =
        control("Approved") { repo.approve(id, phase, authorization) }

    private fun control(
        successLabel: String,
        action: suspend () -> CockpitResult<CockpitJob>,
    ) {
        viewModelScope.launch {
            val message = when (val res = action()) {
                is CockpitResult.Success -> successLabel
                is CockpitResult.Failure -> res.error.message
                is CockpitResult.Unreachable -> res.message
            }
            _state.update { it.copy(snackbar = message) }
        }
    }

    fun consumeSnackbar() = _state.update { it.copy(snackbar = null) }

    override fun onCleared() {
        stopPolling()
        super.onCleared()
    }
}

/** Re-bucket a job list into the canonical sections, newest-first preserved. */
private fun JobsUiState.withSections(jobs: List<CockpitJob>): JobsUiState {
    val active = ArrayList<CockpitJob>()
    val blocked = ArrayList<CockpitJob>()
    val completed = ArrayList<CockpitJob>()
    val failed = ArrayList<CockpitJob>()
    val cancelled = ArrayList<CockpitJob>()
    for (job in jobs) {
        when (sectionOf(job)) {
            JobSection.ACTIVE -> active
            JobSection.BLOCKED -> blocked
            JobSection.COMPLETED -> completed
            JobSection.FAILED -> failed
            JobSection.CANCELLED -> cancelled
        }.add(job)
    }
    return copy(
        active = active,
        blocked = blocked,
        completed = completed,
        failed = failed,
        cancelled = cancelled,
    )
}

enum class JobSection { ACTIVE, BLOCKED, COMPLETED, FAILED, CANCELLED }

/** Classify a job into exactly one list section from its wire status. */
fun sectionOf(job: CockpitJob): JobSection {
    val state = JobUiState.from(JobStatus.fromWire(job.status))
    return when {
        state.needsAttention -> JobSection.BLOCKED
        state == JobUiState.FAILED -> JobSection.FAILED
        state == JobUiState.CANCELLED -> JobSection.CANCELLED
        state == JobUiState.COMPLETED || state == JobUiState.PUBLISHED -> JobSection.COMPLETED
        else -> JobSection.ACTIVE // queued/running/paused/publishing/unknown
    }
}
