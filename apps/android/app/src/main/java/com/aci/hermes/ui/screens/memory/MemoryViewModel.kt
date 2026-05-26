package com.aci.hermes.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.MemoryCategory
import com.aci.hermes.data.model.PatternProvenance
import com.aci.hermes.data.model.ProvenanceKind
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.SocialPatternKind
import com.aci.hermes.data.social.PrivacyRedactor
import com.aci.hermes.data.social.SocialPatternRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class MemoryUiState(
    val selectedCategory: MemoryCategory = MemoryCategory.SOCIAL_SPEECH_PATTERN,
    val patterns: List<SocialPattern> = emptyList(),
    val snackbar: String? = null,
)

class MemoryViewModel(
    private val repository: SocialPatternRepository,
) : ViewModel() {

    private val selectedCategory = MutableStateFlow(MemoryCategory.SOCIAL_SPEECH_PATTERN)
    private val snackbar = MutableStateFlow<String?>(null)

    val state: StateFlow<MemoryUiState> = combine(
        selectedCategory,
        repository.patterns,
        snackbar,
    ) { category, patterns, snack ->
        MemoryUiState(
            selectedCategory = category,
            patterns = patterns.map(PrivacyRedactor::sanitize),
            snackbar = snack,
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, MemoryUiState())

    private val _detailState = MutableStateFlow<SocialPattern?>(null)
    val detailState: StateFlow<SocialPattern?> = _detailState.asStateFlow()

    fun selectCategory(category: MemoryCategory) {
        selectedCategory.value = category
    }

    fun selectPattern(id: String) {
        _detailState.value = repository.byId(id)
    }

    fun clearDetail() {
        _detailState.value = null
    }

    fun consumeSnackbar() {
        snackbar.value = null
    }

    fun delete(id: String) {
        viewModelScope.launch {
            repository.delete(id)
            _detailState.value = null
            snackbar.value = "Pattern deleted"
        }
    }

    fun correct(
        id: String,
        title: String,
        summary: String,
        safeUsage: String,
        unsafeUsage: String,
    ) {
        viewModelScope.launch {
            val updated = repository.correct(id, title, summary, safeUsage, unsafeUsage)
            _detailState.value = updated
            snackbar.value = if (updated == null) "Pattern not found" else "Pattern corrected"
        }
    }

    /**
     * Seed a single demo pattern so the screen is not empty on first
     * launch. The demo pattern is abstract and free of identity by
     * construction.
     */
    fun ensureSeed() {
        if (state.value.patterns.isNotEmpty()) return
        viewModelScope.launch {
            repository.upsert(
                SocialPattern(
                    title = "Engineers reply short on mobile",
                    kind = SocialPatternKind.MOBILE_REPLY,
                    summary = "On phones, technical responders often skip greeting, " +
                        "use lowercase, and drop punctuation. They favor short " +
                        "imperative sentences and link to a doc instead of explaining.",
                    safeUsage = "Match the brevity of a mobile responder when " +
                        "replying from your phone. Keep links to public docs.",
                    unsafeUsage = "Do not impersonate any specific person. Do not " +
                        "claim to be a colleague or insider when sending shorthand.",
                    provenance = listOf(
                        PatternProvenance(
                            sourceTitle = "Google developer style guide — voice and tone",
                            sourceUrl = "https://developers.google.com/style/tone",
                            sourceKind = ProvenanceKind.STYLE_GUIDE,
                            note = "Public style guide, no identity.",
                        ),
                    ),
                ),
            )
        }
    }
}
