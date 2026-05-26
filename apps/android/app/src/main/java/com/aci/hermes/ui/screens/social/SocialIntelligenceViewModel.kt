package com.aci.hermes.ui.screens.social

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.social.SocialIntelligenceRepository
import com.aci.hermes.data.model.SocialChannel
import com.aci.hermes.data.model.SocialSignal
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SocialUiState(val signals: List<SocialSignal> = emptyList())

class SocialIntelligenceViewModel(
    private val social: SocialIntelligenceRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SocialUiState())
    val state: StateFlow<SocialUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            social.signals.collect { list -> _state.update { it.copy(signals = list) } }
        }
    }

    fun record(name: String, summary: String, channel: SocialChannel = SocialChannel.NOTE) {
        if (name.isBlank() || summary.isBlank()) return
        social.record(name, channel, summary)
    }
}
