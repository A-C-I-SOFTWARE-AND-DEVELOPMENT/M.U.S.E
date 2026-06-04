package com.aci.hermes.ui.screens.model

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.LocalModelsStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Model Center — honest local-model (Gemma / Ollama) status from
 * `GET /v1/cockpit/models/local`, plus an explicit per-model smoke test. The
 * UI never fabricates readiness: an unreachable/unpaired backend degrades to a
 * clear hint, and "Smoke-tested" only appears after a smoke run succeeds.
 */
class ModelCenterViewModel(
    private val client: HermesCockpitClient,
) : ViewModel() {

    data class UiState(
        val loading: Boolean = true,
        val status: LocalModelsStatus? = null,
        /** Set when the backend is unreachable/unpaired (honest hint, no data). */
        val unavailable: String? = null,
        /** Models that passed a smoke test this session. */
        val smokeTested: Set<String> = emptySet(),
        /** Models whose smoke test failed this session → reason. */
        val smokeFailed: Map<String, String> = emptyMap(),
        val busyModel: String? = null,
        val message: String? = null,
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, message = null) }
            when (val r = client.localModels()) {
                is CockpitResult.Success ->
                    _state.update { it.copy(loading = false, status = r.value, unavailable = null) }
                is CockpitResult.Unreachable ->
                    _state.update { it.copy(loading = false, status = null, unavailable = r.message) }
                is CockpitResult.Failure ->
                    _state.update { it.copy(loading = false, status = null, unavailable = r.error.message) }
            }
        }
    }

    /** Run an explicit smoke test for [model] — the only path to "Smoke-tested". */
    fun smoke(model: String) {
        if (model.isBlank()) return
        viewModelScope.launch {
            _state.update { it.copy(busyModel = model, message = null) }
            try {
                when (val r = client.localModelSmoke(model)) {
                    is CockpitResult.Success -> {
                        val res = r.value
                        if (res.ok) {
                            _state.update {
                                it.copy(
                                    smokeTested = it.smokeTested + model,
                                    smokeFailed = it.smokeFailed - model,
                                    message = "Smoke test passed (${res.latencyMs} ms)",
                                )
                            }
                        } else {
                            _state.update {
                                it.copy(
                                    smokeFailed = it.smokeFailed + (model to (res.error ?: "no reply")),
                                    smokeTested = it.smokeTested - model,
                                    message = "Smoke test failed",
                                )
                            }
                        }
                    }
                    is CockpitResult.Unreachable ->
                        _state.update { it.copy(message = "Backend unreachable: ${r.message}") }
                    is CockpitResult.Failure ->
                        _state.update { it.copy(message = r.error.message) }
                }
            } finally {
                _state.update { it.copy(busyModel = null) }
            }
        }
    }

    fun clearMessage() = _state.update { it.copy(message = null) }
}
