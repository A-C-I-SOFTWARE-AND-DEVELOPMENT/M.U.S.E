package com.aci.hermes.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.memory.MemoryAction
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryRedactor
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.social.SocialPatternRepository
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
)

class MemoryViewModel(
    private val repository: MemoryRepository,
    private val logBuffer: LogBuffer,
    private val socialPatterns: SocialPatternRepository? = null,
) : ViewModel() {

    private val _state = MutableStateFlow(MemoryUiState())
    val state: StateFlow<MemoryUiState> = _state.asStateFlow()

    private val _detailState = MutableStateFlow<SocialPattern?>(null)
    /**
     * Currently-selected social pattern, surfaced to
     * [com.aci.hermes.ui.screens.memory.SocialPatternDetail]. `null`
     * means no pattern is selected (or the selected id was not found).
     */
    val detailState: StateFlow<SocialPattern?> = _detailState.asStateFlow()

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
        socialPatterns?.let { repo ->
            viewModelScope.launch {
                repo.patterns.collect { _ ->
                    val current = _detailState.value?.id ?: return@collect
                    _detailState.value = repo.byId(current)
                }
            }
        }
        refresh()
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

    // ─── Social-pattern detail ────────────────────────────────────────

    /**
     * Load the [SocialPattern] with [patternId] into [detailState]. If
     * the repository is not wired or the id is unknown, [detailState]
     * is cleared to `null`. Safe to call repeatedly (e.g. inside a
     * `LaunchedEffect`).
     */
    fun selectPattern(patternId: String) {
        _detailState.value = socialPatterns?.byId(patternId)
    }

    /**
     * Apply an owner correction to the selected social pattern.
     * Delegates to [SocialPatternRepository.correct] which re-runs
     * the privacy redactor before persisting.
     */
    fun correct(
        id: String,
        title: String,
        summary: String,
        safeUsage: String,
        unsafeUsage: String,
    ) {
        val repo = socialPatterns ?: return
        viewModelScope.launch {
            val updated = repo.correct(
                id = id,
                title = title,
                summary = summary,
                safeUsage = safeUsage,
                unsafeUsage = unsafeUsage,
            )
            if (updated != null) _detailState.value = updated
            logBuffer.info(TAG, "Social pattern corrected: $id")
        }
    }

    /** Delete the social pattern with the given id. */
    fun delete(patternId: String) {
        val repo = socialPatterns ?: return
        viewModelScope.launch {
            repo.delete(patternId)
            if (_detailState.value?.id == patternId) _detailState.value = null
            logBuffer.warn(TAG, "Social pattern deleted: $patternId")
        }
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
