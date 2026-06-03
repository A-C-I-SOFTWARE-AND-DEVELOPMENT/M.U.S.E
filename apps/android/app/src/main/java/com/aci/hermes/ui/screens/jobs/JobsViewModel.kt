package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.JobsSync
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
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

    init {
        refresh()
    }

    /** Pull the live job list (no-op-safe when unpaired → [JobsSync.NotPaired]). */
    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    /**
     * Cancel a job. Destructive, so the screen gates this behind a
     * confirmation dialog before calling. The repository refreshes the list
     * on success.
     */
    fun cancel(id: String, reason: String? = null) {
        viewModelScope.launch { repository.cancel(id, reason) }
    }
}
