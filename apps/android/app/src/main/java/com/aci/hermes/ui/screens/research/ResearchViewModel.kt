package com.aci.hermes.ui.screens.research

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.ResearchReport
import com.aci.hermes.data.research.PromoteOutcome
import com.aci.hermes.data.research.ResearchRepository
import com.aci.hermes.data.research.ResearchSync
import com.aci.hermes.data.research.TaskOutcome
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ResearchUiState(
    val query: String = "",
    val report: ResearchReport? = null,
    val sync: ResearchSync = ResearchSync.Idle,
    val promotingCardId: String? = null,
    val creatingTask: Boolean = false,
    val snackbar: String? = null,
    /** Card ids already promoted to memory this session (for the UI checkmark). */
    val promotedCardIds: Set<String> = emptySet(),
    /** Id of a task just created — the screen navigates to it then clears this. */
    val createdTaskId: String? = null,
)

/**
 * Drives the Research screen against [ResearchRepository]. Every result is
 * source-backed or honestly empty — the ViewModel never synthesizes findings.
 */
class ResearchViewModel(
    private val repository: ResearchRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(ResearchUiState())
    val state: StateFlow<ResearchUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.report.collect { report ->
                _state.update { it.copy(report = report) }
            }
        }
        viewModelScope.launch {
            repository.sync.collect { sync ->
                _state.update { it.copy(sync = sync) }
            }
        }
    }

    fun setQuery(q: String) {
        _state.update { it.copy(query = q) }
    }

    /** Run the research pipeline for the current query. */
    fun run() {
        val query = _state.value.query.trim()
        if (query.isEmpty()) {
            _state.update { it.copy(snackbar = "Enter a question to research") }
            return
        }
        _state.update { it.copy(promotedCardIds = emptySet()) }
        viewModelScope.launch {
            logBuffer.info(TAG, "research run: $query")
            repository.run(query)
        }
    }

    /** Promote one evidence card to the Memory Tree through the gateway gate. */
    fun promote(cardId: String) {
        _state.update { it.copy(promotingCardId = cardId) }
        viewModelScope.launch {
            val outcome = repository.promote(cardId)
            _state.update { st ->
                when (outcome) {
                    is PromoteOutcome.Stored -> st.copy(
                        promotingCardId = null,
                        promotedCardIds = st.promotedCardIds + cardId,
                        snackbar = "Saved to memory",
                    )
                    is PromoteOutcome.Rejected -> st.copy(
                        promotingCardId = null,
                        snackbar = "Not saved — ${outcome.reason}",
                    )
                    is PromoteOutcome.Failed -> st.copy(
                        promotingCardId = null,
                        snackbar = outcome.message,
                    )
                }
            }
        }
    }

    /** Turn the current report into a queued coding task. */
    fun createTask() {
        _state.update { it.copy(creatingTask = true) }
        viewModelScope.launch {
            val outcome = repository.createTask()
            _state.update { st ->
                when (outcome) {
                    is TaskOutcome.Created -> st.copy(
                        creatingTask = false,
                        createdTaskId = outcome.job.id,
                        snackbar = "Coding task queued",
                    )
                    is TaskOutcome.Failed -> st.copy(creatingTask = false, snackbar = outcome.message)
                    is TaskOutcome.Unpaired -> st.copy(
                        creatingTask = false,
                        snackbar = "Pair a gateway to create tasks",
                    )
                }
            }
        }
    }

    fun consumeCreatedTask() {
        _state.update { it.copy(createdTaskId = null) }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    companion object {
        const val TAG = "Research"
    }
}
