package com.aci.hermes.ui.screens.skills

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.SkillDescriptor
import com.aci.hermes.data.skills.SkillsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SkillsUiState(
    val skills: List<SkillDescriptor> = emptyList(),
)

class SkillsViewModel(
    application: Application,
    private val skills: SkillsRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(SkillsUiState())
    val state: StateFlow<SkillsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            skills.items.collect { list ->
                _state.update { it.copy(skills = list) }
            }
        }
    }

    fun setEnabled(skill: SkillDescriptor, enabled: Boolean) {
        viewModelScope.launch { skills.setEnabled(skill.id, enabled) }
    }

    fun reset() {
        viewModelScope.launch { skills.reset() }
    }
}
