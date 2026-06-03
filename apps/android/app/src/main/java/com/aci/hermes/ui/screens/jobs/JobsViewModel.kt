package com.aci.hermes.ui.screens.jobs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * The Jobs surface — submit an orchestration job, watch it appear, and run it
 * on a worker through the orchestrator's gated 5-step contract. Execute lanes
 * (Codex/Claude) require the owner authorization phrase; the gateway enforces
 * the gate (this UI just carries the phrase through).
 */
class JobsViewModel(
    private val client: HermesCockpitClient,
) : ViewModel() {

    data class UiState(
        val jobs: List<CockpitJob> = emptyList(),
        val loading: Boolean = false,
        val busy: Boolean = false,
        val message: String = "",
        val notPaired: Boolean = false,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            when (val r = client.jobsList()) {
                is CockpitResult.Success -> _state.update {
                    it.copy(jobs = r.value.jobs, loading = false, notPaired = false)
                }
                is CockpitResult.Failure -> _state.update {
                    it.copy(loading = false, message = "Couldn't load jobs (HTTP ${r.httpStatus}).")
                }
                is CockpitResult.Unreachable -> _state.update {
                    it.copy(loading = false, notPaired = true, jobs = emptyList())
                }
            }
        }
    }

    fun submit(prompt: String) {
        val p = prompt.trim()
        if (p.isBlank()) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true, message = "") }
            when (val r = client.orchestrateSubmit(p)) {
                is CockpitResult.Success -> {
                    _state.update { it.copy(busy = false, message = "Submitted: ${r.value.title}") }
                    refresh()
                }
                is CockpitResult.Failure -> _state.update {
                    it.copy(busy = false, message = "Submit failed (HTTP ${r.httpStatus}).")
                }
                is CockpitResult.Unreachable -> _state.update {
                    it.copy(busy = false, notPaired = true, message = "Not connected — pair first.")
                }
            }
        }
    }

    /** Run a job on a worker. [authorization] is the owner phrase for execute lanes. */
    fun run(jobId: String, workerId: String, authorization: String?) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, message = "") }
            when (val r = client.jobRun(jobId, workerId, authorization)) {
                is CockpitResult.Success -> {
                    val st = r.value.job.status
                    _state.update { it.copy(busy = false, message = "$workerId → ${st.ifBlank { "ran" }}") }
                    refresh()
                }
                is CockpitResult.Failure -> _state.update {
                    it.copy(
                        busy = false,
                        message = if (r.httpStatus == 403) {
                            "Owner approval required — type the exact phrase."
                        } else {
                            "Run failed (HTTP ${r.httpStatus})."
                        },
                    )
                }
                is CockpitResult.Unreachable -> _state.update {
                    it.copy(busy = false, notPaired = true, message = "Not connected — pair first.")
                }
            }
        }
    }
}
