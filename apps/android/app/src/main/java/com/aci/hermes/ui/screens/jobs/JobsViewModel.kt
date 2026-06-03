package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.JobsSync
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Drives the cockpit Jobs screen off the canonical [CockpitJobsRepository]
 * (contract §4). Mirrors the cockpit-backed ViewModel pattern used by
 * [com.aci.hermes.ui.screens.audit.AuditViewModel]: expose the repository's
 * StateFlows, pull a live list on init, and run actions in [viewModelScope].
 *
 * There is no mock seed — an unpaired or unreachable gateway yields an empty
 * list plus an honest [JobsSync] state, never fabricated jobs.
 */
class JobsViewModel(
    private val repository: CockpitJobsRepository,
) : ViewModel() {

    val jobs: StateFlow<List<CockpitJob>> = repository.jobs
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = repository.jobs.value,
        )

    val sync: StateFlow<JobsSync> = repository.sync
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = repository.sync.value,
        )

    /**
     * One-shot reason for a failed cancel, surfaced as a snackbar by the
     * screen and cleared via [consumeMessage]. Kept as a plain reason string
     * (no Android resources here) so the ViewModel stays Context-free.
     */
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        refresh()
    }

    /** Pull the live job list (no-op-safe when unpaired → [JobsSync.NotPaired]). */
    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    /**
     * Cancel a job. Destructive, so the screen gates this behind a
     * confirmation dialog before calling. On success the repository refreshes
     * the list; on failure the reason is surfaced via [message] so the action
     * is never silently dropped (e.g. a 404 for an /orchestrate job not in the
     * JobQueue, or a 409 terminal-state conflict). A refresh is also kicked so
     * a now-terminal job reflects its real state.
     */
    fun cancel(id: String, reason: String? = null) {
        viewModelScope.launch {
            when (val res = repository.cancel(id, reason)) {
                is CockpitResult.Success -> Unit // repository already refreshed
                is CockpitResult.Failure -> {
                    _message.value = "${res.error.message} (${res.httpStatus})"
                    repository.refresh()
                }
                is CockpitResult.Unreachable -> _message.value = res.message
            }
        }
    }

    /** Clear the one-shot cancel-failure [message] after it has been shown. */
    fun consumeMessage() {
        _message.value = null
    }
}
