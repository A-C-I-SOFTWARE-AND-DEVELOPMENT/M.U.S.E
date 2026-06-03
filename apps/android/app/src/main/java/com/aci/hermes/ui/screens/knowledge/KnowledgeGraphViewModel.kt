package com.aci.hermes.ui.screens.knowledge

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitGraphRepository
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.GraphAnswer
import com.aci.hermes.data.cockpit.GraphBuildResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** UI state for the Knowledge Graph screen. */
data class KnowledgeGraphUiState(
    val paired: Boolean = true,
    val query: String = "",
    val mode: String = "coding",
    val loading: Boolean = false,
    val answer: GraphAnswer? = null,
    val build: GraphBuildResult? = null,
    val message: String? = null,
)

/** Valid query modes, surfaced for the mode selector. */
val GRAPH_QUERY_MODES = listOf("coding", "local", "global")

/**
 * Drives the dedicated Knowledge Graph screen: run a GraphRAG query in one of
 * the three modes, or rebuild the cache — all over the real
 * [CockpitGraphRepository]. There is no mock data: an unpaired or unreachable
 * gateway yields an honest message, never fabricated nodes.
 */
class KnowledgeGraphViewModel(
    private val repository: CockpitGraphRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(KnowledgeGraphUiState(paired = repository.isPaired()))
    val state: StateFlow<KnowledgeGraphUiState> = _state.asStateFlow()

    fun onQueryChange(value: String) {
        _state.value = _state.value.copy(query = value)
    }

    fun onModeChange(mode: String) {
        if (mode in GRAPH_QUERY_MODES) _state.value = _state.value.copy(mode = mode)
    }

    fun runQuery() {
        val s = _state.value
        if (s.query.isBlank() || s.loading) return
        if (!repository.isPaired()) {
            _state.value = s.copy(paired = false, message = "Pair a gateway to query the graph.")
            return
        }
        _state.value = s.copy(loading = true, message = null)
        viewModelScope.launch {
            when (val res = repository.query(s.query, s.mode)) {
                is CockpitResult.Success ->
                    _state.value = _state.value.copy(loading = false, answer = res.value, message = null)
                is CockpitResult.Failure ->
                    _state.value = _state.value.copy(loading = false, message = "Gateway error ${res.httpStatus}: ${res.error.message}")
                is CockpitResult.Unreachable ->
                    _state.value = _state.value.copy(loading = false, message = res.message)
            }
        }
    }

    fun rebuild() {
        if (_state.value.loading) return
        if (!repository.isPaired()) {
            _state.value = _state.value.copy(paired = false, message = "Pair a gateway to build the graph.")
            return
        }
        _state.value = _state.value.copy(loading = true, message = "Building knowledge graph…")
        viewModelScope.launch {
            when (val res = repository.build()) {
                is CockpitResult.Success ->
                    _state.value = _state.value.copy(
                        loading = false,
                        build = res.value,
                        message = "Built ${res.value.nodes} nodes, ${res.value.edges} edges.",
                    )
                is CockpitResult.Failure ->
                    _state.value = _state.value.copy(loading = false, message = "Gateway error ${res.httpStatus}: ${res.error.message}")
                is CockpitResult.Unreachable ->
                    _state.value = _state.value.copy(loading = false, message = res.message)
            }
        }
    }
}
