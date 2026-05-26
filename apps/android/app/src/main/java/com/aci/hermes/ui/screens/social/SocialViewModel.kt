package com.aci.hermes.ui.screens.social

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.social.SocialPatternRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SocialUiState(
    val patterns: List<SocialPattern> = emptyList(),
)

class SocialViewModel(
    application: Application,
    private val social: SocialPatternRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(SocialUiState())
    val state: StateFlow<SocialUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            social.items.collect { list ->
                _state.update { it.copy(patterns = list.filterNot { p -> p.dismissed }) }
            }
        }
    }

    fun acknowledge(pattern: SocialPattern) {
        viewModelScope.launch { social.acknowledge(pattern.id) }
    }

    fun dismiss(pattern: SocialPattern) {
        viewModelScope.launch { social.dismiss(pattern.id) }
    }
}
