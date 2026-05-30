package com.aci.hermes.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.memory.MemoryAction
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryRedactor
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.memory.MemorySync
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

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
)

class MemoryViewModel(
    private val repository: MemoryRepository,
    private val logBuffer: LogBuffer,
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
        refresh()
        sync()
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
