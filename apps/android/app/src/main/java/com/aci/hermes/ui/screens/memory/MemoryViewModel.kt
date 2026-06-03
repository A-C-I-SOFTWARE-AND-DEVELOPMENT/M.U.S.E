package com.aci.hermes.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.memory.DecisionOutcome
import com.aci.hermes.data.memory.MemoryAction
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryContradiction
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryNode
import com.aci.hermes.data.memory.MemoryRedactor
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.memory.MemorySync
import com.aci.hermes.data.memory.MemoryTreeRepository
import com.aci.hermes.data.memory.TreeSync
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Which Memory surface the screen is showing. */
enum class MemoryTab(val display: String) {
    STORED("Memory"),
    INBOX("Inbox"),
    CONTRADICTIONS("Conflicts"),
    FRESHNESS("Review"),
}

data class MemoryUiState(
    val query: String = "",
    val activeCategory: MemoryCategory? = null,
    val allItems: List<MemoryItem> = emptyList(),
    val visibleItems: List<MemoryItem> = emptyList(),
    val selectedItem: MemoryItem? = null,
    val correctingItem: MemoryItem? = null,
    val deletingItem: MemoryItem? = null,
    val snackbar: String? = null,
    val sync: MemorySync = MemorySync.Idle,
    // Memory Tree (MEM-2) surfaces.
    val tab: MemoryTab = MemoryTab.STORED,
    val proposed: List<MemoryNode> = emptyList(),
    val contradictions: List<MemoryContradiction> = emptyList(),
    val freshness: List<MemoryNode> = emptyList(),
    val treeSync: TreeSync = TreeSync.Idle,
)

class MemoryViewModel(
    private val repository: MemoryRepository,
    private val logBuffer: LogBuffer,
    private val treeRepository: MemoryTreeRepository? = null,
) : ViewModel() {

    private val _state = MutableStateFlow(MemoryUiState())
    val state: StateFlow<MemoryUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.items.collect { _ ->
                refresh()
            }
        }
        viewModelScope.launch {
            repository.actions.collect { action ->
                logBuffer.info(TAG, describe(action))
            }
        }
        viewModelScope.launch {
            repository.sync.collect { sync ->
                _state.update { it.copy(sync = sync) }
            }
        }
        treeRepository?.let { tree ->
            viewModelScope.launch {
                tree.proposed.collect { nodes -> _state.update { it.copy(proposed = nodes) } }
            }
            viewModelScope.launch {
                tree.contradictions.collect { c -> _state.update { it.copy(contradictions = c) } }
            }
            viewModelScope.launch {
                tree.freshness.collect { f -> _state.update { it.copy(freshness = f) } }
            }
            viewModelScope.launch {
                tree.sync.collect { s -> _state.update { it.copy(treeSync = s) } }
            }
        }
        refresh()
        sync()
    }

    fun selectTab(tab: MemoryTab) {
        _state.update { it.copy(tab = tab) }
        when (tab) {
            MemoryTab.STORED -> sync()
            MemoryTab.INBOX -> viewModelScope.launch { treeRepository?.refreshProposed() }
            MemoryTab.CONTRADICTIONS -> viewModelScope.launch { treeRepository?.refreshContradictions() }
            MemoryTab.FRESHNESS -> viewModelScope.launch { treeRepository?.refreshFreshness() }
        }
    }

    fun approveProposed(id: String) = decide { it.approve(id) }

    fun rejectProposed(id: String, reason: String? = null) = decide { it.reject(id, reason) }

    fun supersedeProposed(id: String, supersedesId: String, note: String? = null) =
        decide { it.supersede(id, supersedesId, note) }

    fun resolveContradiction(id: String, winnerId: String, note: String? = null) {
        val tree = treeRepository ?: return
        viewModelScope.launch {
            val outcome = tree.resolveContradiction(id, winnerId, note)
            _state.update { it.copy(snackbar = describeOutcome(outcome, "Contradiction resolved")) }
        }
    }

    private fun decide(block: suspend (MemoryTreeRepository) -> DecisionOutcome) {
        val tree = treeRepository ?: return
        viewModelScope.launch {
            val outcome = block(tree)
            _state.update { it.copy(snackbar = describeOutcome(outcome, "Memory updated")) }
        }
    }

    private fun describeOutcome(outcome: DecisionOutcome, okMessage: String): String =
        when (outcome) {
            is DecisionOutcome.Ok -> okMessage
            is DecisionOutcome.Unpaired -> "Pair a gateway to manage memory"
            is DecisionOutcome.Conflict ->
                "Approved, but it conflicts with an existing fact — resolve in Conflicts"
            is DecisionOutcome.Error -> outcome.message
        }

    /** Pull the live memory list from the gateway (no-op when unpaired). */
    fun sync() {
        viewModelScope.launch { repository.refresh() }
    }

    fun setQuery(q: String) {
        _state.update { it.copy(query = q) }
        refresh()
    }

    fun setCategory(category: MemoryCategory?) {
        _state.update { it.copy(activeCategory = category) }
        refresh()
    }

    fun open(item: MemoryItem) {
        _state.update { it.copy(selectedItem = item) }
    }

    fun closeDetail() {
        _state.update { it.copy(selectedItem = null) }
    }

    fun beginCorrect(item: MemoryItem) {
        _state.update { it.copy(correctingItem = item) }
    }

    fun cancelCorrect() {
        _state.update { it.copy(correctingItem = null) }
    }

    fun confirmCorrect(newContent: String, reason: String?) {
        val target = _state.value.correctingItem ?: return
        viewModelScope.launch {
            repository.correct(target.id, newContent, reason)
            _state.update {
                it.copy(
                    correctingItem = null,
                    selectedItem = null,
                    snackbar = "Memory corrected",
                )
            }
        }
    }

    fun beginDelete(item: MemoryItem) {
        _state.update { it.copy(deletingItem = item) }
    }

    fun cancelDelete() {
        _state.update { it.copy(deletingItem = null) }
    }

    fun confirmDelete(reason: String?) {
        val target = _state.value.deletingItem ?: return
        viewModelScope.launch {
            repository.delete(target.id, reason)
            _state.update {
                it.copy(
                    deletingItem = null,
                    selectedItem = null,
                    snackbar = "Memory deleted",
                )
            }
        }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    private fun refresh() {
        val sanitized = MemoryRedactor.sanitizeAll(repository.items.value)
            .filterNot { it.hidden }
        val filtered = applyFilters(sanitized, _state.value.query, _state.value.activeCategory)
        _state.update {
            it.copy(
                allItems = sanitized,
                visibleItems = filtered,
            )
        }
    }

    private fun describe(action: MemoryAction): String = when (action) {
        is MemoryAction.Correct -> "Correct ${action.itemId}: ${action.reason ?: "no reason"}"
        is MemoryAction.Delete -> "Delete ${action.itemId}: ${action.reason ?: "no reason"}"
        is MemoryAction.Hide -> "Hide ${action.itemId}"
        is MemoryAction.Reveal -> "Reveal ${action.itemId}"
    }

    companion object {
        private const val TAG = "Memory"

        fun applyFilters(
            items: List<MemoryItem>,
            query: String,
            category: MemoryCategory?,
        ): List<MemoryItem> {
            val byCategory = if (category == null) items else items.filter { it.category == category }
            val q = query.trim().lowercase()
            if (q.isEmpty()) return byCategory
            return byCategory.filter { item ->
                item.title.lowercase().contains(q) ||
                    item.content.lowercase().contains(q) ||
                    item.tags.any { it.lowercase().contains(q) } ||
                    item.category.display.lowercase().contains(q)
            }
        }
    }
}
