package com.aci.hermes.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.memory.MemoryNode
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.memory.MemoryTree
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MemoryUiState(
    val tree: MemoryTree = MemoryTree(),
    val query: String = "",
    val matches: List<MemoryNode> = emptyList(),
)

class MemoryViewModel(
    private val repo: MemoryRepository,
) : ViewModel() {

    private val query = MutableStateFlow("")

    private val _state = MutableStateFlow(MemoryUiState())
    val state: StateFlow<MemoryUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            combine(repo.tree, query) { tree, q ->
                MemoryUiState(
                    tree = tree,
                    query = q,
                    matches = if (q.isBlank()) emptyList() else tree.search(q),
                )
            }.collect { snapshot -> _state.value = snapshot }
        }
    }

    fun setQuery(q: String) = query.update { q }

    fun remember(topic: String, body: String, parentId: String? = null, tags: List<String> = emptyList()) {
        val trimmed = topic.trim()
        if (trimmed.isEmpty()) return
        repo.remember(
            MemoryNode(
                parentId = parentId,
                topic = trimmed,
                body = body.trim(),
                tags = tags.map { it.trim() }.filter { it.isNotEmpty() },
                provenance = MemoryNode.Provenance.MANUAL,
            )
        )
    }

    fun forget(id: String) = repo.forget(id)
}
