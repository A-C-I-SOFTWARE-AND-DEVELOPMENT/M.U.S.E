package com.aci.hermes.ui.screens.modelroute

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitModelRoutesRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.ModelRouteDecision
import com.aci.hermes.data.cockpit.ModelRoutesSync
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ModelRouteUiState(
    val routes: List<ModelRouteDecision> = emptyList(),
    val paidEnabled: Boolean = false,
    val sync: ModelRoutesSync = ModelRoutesSync.Idle,
    /** Transient one-line result of the last override action (null when none). */
    val message: String? = null,
)

/**
 * Drives the Model Route screen: shows the evidence-backed route per task
 * class, lets the owner pin a model, and gates the paid-routing toggle behind
 * the exact owner authorization phrase (a money-spend gate kept on the server).
 */
class ModelRouteViewModel(
    private val repo: CockpitModelRoutesRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ModelRouteUiState())
    val state: StateFlow<ModelRouteUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch { observe() }
        refresh()
    }

    private suspend fun observe() {
        // Mirror the repository's truth into the UI state.
        kotlinx.coroutines.flow.combine(repo.routes, repo.sync) { routes, sync ->
            ModelRouteUiState(
                routes = routes.routes,
                paidEnabled = routes.paidEnabled,
                sync = sync,
                message = _state.value.message,
            )
        }.collect { next -> _state.value = next }
    }

    fun refresh() {
        viewModelScope.launch { repo.refresh() }
    }

    fun setOverride(taskClass: String, model: String?) {
        viewModelScope.launch {
            val res = repo.setOverride(taskClass, model)
            _state.update { it.copy(message = messageFor(res, "Override updated")) }
        }
    }

    fun clearOverride(taskClass: String) = setOverride(taskClass, null)

    /**
     * Flip paid routing. [authorization] MUST be [OWNER_AUTHORIZATION_PHRASE]
     * or the gateway refuses (403). Both enabling and disabling are gated.
     */
    fun setPaidEnabled(enabled: Boolean, authorization: String) {
        viewModelScope.launch {
            val res = repo.setPaidEnabled(enabled, authorization)
            val ok = if (enabled) "Paid routing enabled" else "Paid routing disabled"
            _state.update { it.copy(message = messageFor(res, ok)) }
        }
    }

    fun consumeMessage() = _state.update { it.copy(message = null) }

    private fun messageFor(res: CockpitResult<*>, okText: String): String = when (res) {
        is CockpitResult.Success -> okText
        is CockpitResult.Failure ->
            if (res.httpStatus == 403) {
                "Owner authorization required — paid routing unchanged."
            } else {
                "Gateway error ${res.httpStatus}: ${res.error.message}"
            }
        is CockpitResult.Unreachable -> res.message
    }

    companion object {
        /** Exact phrase the gateway requires to change paid routing. */
        const val OWNER_AUTHORIZATION_PHRASE: String = "Yes, with authorization."
    }
}
