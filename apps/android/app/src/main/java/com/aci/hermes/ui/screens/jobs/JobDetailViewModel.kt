package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitNavigation
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.DiffSnapshot
import com.aci.hermes.data.cockpit.JobDetail
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.cockpit.ValidationSnapshot
import com.aci.hermes.ui.components.JobUiState
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class JobDetailUiState(
    val loading: Boolean = true,
    val detail: JobDetail? = null,
    val error: String? = null,
    val patch: DiffSnapshot? = null,
    val patchLoading: Boolean = false,
    val verification: ValidationSnapshot? = null,
    val verifying: Boolean = false,
    val navigation: CockpitNavigation? = null,
    val navLoading: Boolean = false,
    val navLoaded: Boolean = false,
    val snackbar: String? = null,
) {
    val uiState: JobUiState
        get() = when {
            verifying -> JobUiState.VERIFYING
            else -> JobUiState.from(JobStatus.fromWire(detail?.status))
        }
}

/**
 * Owns one job's detail surface: the read-only ledger timeline plus the full
 * control set (pause/resume/cancel/approve/rerun, "open patch", "run
 * verification"). Refreshes the detail off [CockpitJobsRepository.detail] and
 * polls with the same lifecycle-aware back-off as the list while the job is
 * active.
 */
class JobDetailViewModel(
    private val repo: CockpitJobsRepository,
    private val jobId: String,
) : ViewModel() {

    private val _state = MutableStateFlow(JobDetailUiState())
    val state: StateFlow<JobDetailUiState> = _state.asStateFlow()

    private var pollJob: Job? = null
    private var visible = false

    init {
        load()
    }

    fun onVisibilityChanged(nowVisible: Boolean) {
        visible = nowVisible
        if (nowVisible) startPolling()
    }

    fun load() {
        viewModelScope.launch { refreshOnce() }
    }

    private fun startPolling() {
        if (pollJob?.isActive == true) return
        pollJob = viewModelScope.launch {
            var errors = 0
            var idle = 0
            while (isActive) {
                val ok = refreshOnce()
                val active = _state.value.detail?.let {
                    JobUiState.from(JobStatus.fromWire(it.status)).let { s -> s.isActive || s.needsAttention }
                } ?: false
                errors = if (ok) 0 else errors + 1
                idle = if (active) 0 else idle + 1
                val next = JobsPolling.nextDelayMs(active, visible, errors, idle)
                if (next == JobsPolling.STOP) break
                delay(next)
            }
        }
    }

    private suspend fun refreshOnce(): Boolean =
        when (val res = repo.detail(jobId)) {
            is CockpitResult.Success -> {
                _state.update { it.copy(loading = false, detail = res.value, error = null) }
                true
            }
            is CockpitResult.Failure -> {
                _state.update { it.copy(loading = false, error = res.error.message) }
                false
            }
            is CockpitResult.Unreachable -> {
                _state.update { it.copy(loading = false, error = res.message) }
                false
            }
        }

    // ── controls ──────────────────────────────────────────────────────────

    fun pause() = control("Paused") { repo.pause(jobId) }
    fun resume() = control("Resumed") { repo.resume(jobId) }
    fun cancel() = control("Cancelled") { repo.cancel(jobId) }
    fun rerun(workerId: String? = null) = control("Rerunning step") { repo.rerun(jobId, workerId) }
    fun approve(authorization: String, phase: String = "execute") =
        control("Approved") { repo.approve(jobId, phase, authorization) }

    /** "Open patch" — load the working-tree diff. */
    fun openPatch() {
        _state.update { it.copy(patchLoading = true) }
        viewModelScope.launch {
            when (val res = repo.diff(jobId)) {
                is CockpitResult.Success ->
                    _state.update { it.copy(patch = res.value, patchLoading = false) }
                is CockpitResult.Failure ->
                    _state.update { it.copy(patchLoading = false, snackbar = res.error.message) }
                is CockpitResult.Unreachable ->
                    _state.update { it.copy(patchLoading = false, snackbar = res.message) }
            }
        }
    }

    /** "Run verification" — execute the workspace's validation gates. */
    fun runVerification() {
        _state.update { it.copy(verifying = true) }
        viewModelScope.launch {
            when (val res = repo.validate(jobId)) {
                is CockpitResult.Success ->
                    _state.update { it.copy(verification = res.value, verifying = false) }
                is CockpitResult.Failure ->
                    _state.update { it.copy(verifying = false, snackbar = res.error.message) }
                is CockpitResult.Unreachable ->
                    _state.update { it.copy(verifying = false, snackbar = res.message) }
            }
            refreshOnce()
        }
    }

    /** "Navigation" — load the HyperAgent pre-dispatch decision for this job. */
    fun loadNavigation() {
        _state.update { it.copy(navLoading = true) }
        viewModelScope.launch {
            when (val res = repo.navigation(jobId)) {
                is CockpitResult.Success ->
                    _state.update { it.copy(navigation = res.value, navLoading = false, navLoaded = true) }
                is CockpitResult.Failure ->
                    _state.update { it.copy(navLoading = false, navLoaded = true, snackbar = res.error.message) }
                is CockpitResult.Unreachable ->
                    _state.update { it.copy(navLoading = false, navLoaded = true, snackbar = res.message) }
            }
        }
    }

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
            refreshOnce()
        }
    }

    fun consumeSnackbar() = _state.update { it.copy(snackbar = null) }

    override fun onCleared() {
        pollJob?.cancel()
        super.onCleared()
    }
}
